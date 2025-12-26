"""
Greenlight Batch Processor

Batches similar LLM requests for efficiency.
Reduces API calls by grouping frame prompts and similar operations.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import LLMFunction

logger = get_logger("pipelines.batch")


class BatchType(Enum):
    """Types of batchable operations."""
    FRAME_PROMPTS = "frame_prompts"
    TAG_VALIDATION = "tag_validation"
    SCENE_ANALYSIS = "scene_analysis"


@dataclass
class BatchItem:
    """A single item in a batch."""
    id: str
    data: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BatchResult:
    """Result from batch processing."""
    items: List[BatchItem]
    batch_count: int
    total_items: int
    success_count: int
    error_count: int
    tokens_saved_estimate: int = 0


class BatchProcessor:
    """
    Batches similar LLM requests for efficiency.

    Features:
    - Groups similar requests into batches
    - Single LLM call per batch (up to batch_size items)
    - Automatic result parsing and distribution
    - Error handling per item
    """

    def __init__(
        self,
        llm_caller: Callable[..., Awaitable[str]],
        batch_size: int = 5,
        max_concurrent_batches: int = 3
    ):
        """
        Initialize the batch processor.

        Args:
            llm_caller: Async function to call LLM
            batch_size: Max items per batch (default 5)
            max_concurrent_batches: Max parallel batch calls
        """
        self.llm_caller = llm_caller
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent_batches
        self._semaphore = asyncio.Semaphore(max_concurrent_batches)

    async def batch_frame_prompts(
        self,
        frames: List[Dict[str, Any]],
        world_config: Dict[str, Any],
        visual_style: str = "",
        scene_num: int = 1
    ) -> BatchResult:
        """
        Generate frame prompts in batches.

        Instead of one LLM call per frame, groups frames into batches
        and generates multiple prompts per call.

        Args:
            frames: List of frame data dicts with boundaries
            world_config: World configuration for context
            visual_style: Visual style description
            scene_num: Scene number for notation

        Returns:
            BatchResult with generated prompts
        """
        # Create batch items
        items = [
            BatchItem(id=f"frame_{i}", data=frame)
            for i, frame in enumerate(frames)
        ]

        # Split into batches
        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        logger.info(
            f"Batching {len(items)} frames into {len(batches)} batches "
            f"(batch_size={self.batch_size})"
        )

        # Process batches (with concurrency limit)
        tasks = [
            self._process_frame_batch(batch, world_config, visual_style, scene_num)
            for batch in batches
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_items = []
        success_count = 0
        error_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Mark all items in batch as failed
                for item in batches[i]:
                    item.error = str(result)
                    all_items.append(item)
                    error_count += 1
            else:
                all_items.extend(result)
                success_count += sum(1 for item in result if item.result)
                error_count += sum(1 for item in result if item.error)

        # Estimate tokens saved (overhead per call ~500 tokens)
        tokens_saved = (len(items) - len(batches)) * 500

        return BatchResult(
            items=all_items,
            batch_count=len(batches),
            total_items=len(items),
            success_count=success_count,
            error_count=error_count,
            tokens_saved_estimate=tokens_saved
        )

    async def _process_frame_batch(
        self,
        batch: List[BatchItem],
        world_config: Dict[str, Any],
        visual_style: str,
        scene_num: int
    ) -> List[BatchItem]:
        """Process a single batch of frames."""
        async with self._semaphore:
            # Build batch prompt
            prompt = self._build_batch_frame_prompt(
                batch, world_config, visual_style, scene_num
            )

            try:
                response = await self.llm_caller(
                    prompt=prompt,
                    system_prompt=self._get_batch_system_prompt(),
                    function=LLMFunction.DIRECTOR
                )

                # Parse response into individual frame results
                return self._parse_batch_frame_response(response, batch, scene_num)

            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                for item in batch:
                    item.error = str(e)
                return batch

    def _build_batch_frame_prompt(
        self,
        batch: List[BatchItem],
        world_config: Dict[str, Any],
        visual_style: str,
        scene_num: int
    ) -> str:
        """Build a prompt for batch frame generation."""
        # Format character tags
        characters = world_config.get("characters", [])
        char_section = "\n".join([
            f"  [{c.get('tag', '')}]: {c.get('visual_description', c.get('appearance', ''))[:100]}..."
            for c in characters if c.get('tag')
        ][:10])  # Limit to 10 chars for token efficiency

        # Format location tags
        locations = world_config.get("locations", [])
        loc_section = "\n".join([
            f"  [{l.get('tag', '')}]: {l.get('description', '')[:100]}..."
            for l in locations if l.get('tag')
        ][:10])

        # Format prop tags
        props = world_config.get("props", [])
        prop_section = "\n".join([
            f"  [{p.get('tag', '')}]: {p.get('description', '')[:100]}..."
            for p in props if p.get('tag')
        ][:10])

        # Build frames section
        frames_section = ""
        for i, item in enumerate(batch):
            frame_data = item.data
            frame_num = i + 1
            boundary = frame_data.get("boundary", {})

            frames_section += f"""
=== FRAME {frame_num} ===
FRAME ID: {item.id}
SCENE.FRAME: {scene_num}.{frame_num}
START: "{boundary.get('start_text', '')[:50]}"
END: "{boundary.get('end_text', '')[:50]}"
CAPTURES: {boundary.get('captures', 'Action moment')}
"""

        prompt = f"""Generate visual prompts for {len(batch)} frames in a SINGLE response.

VISUAL STYLE: {visual_style}

AVAILABLE TAGS:
CHARACTERS:
{char_section if char_section else "  (none specified)"}

LOCATIONS:
{loc_section if loc_section else "  (none specified)"}

PROPS:
{prop_section if prop_section else "  (none specified)"}

FRAMES TO GENERATE:
{frames_section}

OUTPUT FORMAT (generate ALL {len(batch)} frames):

For each frame, output EXACTLY this format:

---FRAME_START:{item.id}---
[{scene_num}.X.cA] (Shot Type)
TAGS: [TAG1], [TAG2], ...
LOCATION_DIRECTION: NORTH|EAST|SOUTH|WEST
PROMPT: Your 200-word-max visual description using [TAGS] in brackets...
---FRAME_END---

REQUIREMENTS:
1. Generate ALL {len(batch)} frames in order
2. Use [TAG] notation for ALL characters, locations, props
3. Each prompt should be 150-200 words max
4. Include TAGS line listing all tags used
5. Include LOCATION_DIRECTION (NORTH/EAST/SOUTH/WEST)

Generate all frames now:"""

        return prompt

    def _get_batch_system_prompt(self) -> str:
        """Get system prompt for batch processing."""
        return """You are a visual prompt writer for cinematic storyboarding.

When generating batch frame prompts:
1. Use explicit [TAG] notation for ALL characters, locations, and props
2. Generate ALL requested frames in a single response
3. Follow the exact output format with ---FRAME_START:id--- and ---FRAME_END--- markers
4. Keep each prompt to 150-200 words maximum
5. Include shot type, tags list, and location direction for each frame"""

    def _parse_batch_frame_response(
        self,
        response: str,
        batch: List[BatchItem],
        scene_num: int
    ) -> List[BatchItem]:
        """Parse batch response into individual frame results."""
        # Pattern to extract individual frames
        frame_pattern = r'---FRAME_START:(\w+)---\s*(.+?)\s*---FRAME_END---'
        matches = re.findall(frame_pattern, response, re.DOTALL)

        # Create lookup by ID
        id_to_item = {item.id: item for item in batch}

        # Parse each match
        for frame_id, content in matches:
            if frame_id in id_to_item:
                id_to_item[frame_id].result = content.strip()

        # For any items without results, try positional parsing
        items_without_results = [
            item for item in batch if item.result is None
        ]

        if items_without_results:
            # Fallback: parse by scene.frame notation
            notation_pattern = r'\[(\d+)\.(\d+)\.c([A-Z])\]\s*\(([^)]+)\)\s*(?:TAGS:[^\n]+\s*)?(?:LOCATION_DIRECTION:[^\n]+\s*)?(?:PROMPT:\s*)?(.+?)(?=\[\d+\.\d+\.c[A-Z]\]|---FRAME_|$)'
            fallback_matches = re.findall(notation_pattern, response, re.DOTALL)

            for i, match in enumerate(fallback_matches):
                if i < len(items_without_results):
                    item = items_without_results[i]
                    # Reconstruct the full frame content
                    scene_n, frame_n, camera, shot_type, prompt_text = match
                    item.result = f"[{scene_n}.{frame_n}.c{camera}] ({shot_type})\n{prompt_text.strip()}"

        # Mark remaining items as errors
        for item in batch:
            if item.result is None and item.error is None:
                item.error = "Failed to parse frame from batch response"
                logger.warning(f"Could not parse result for {item.id}")

        return batch

    async def batch_tag_validation(
        self,
        tags: List[str],
        context: str = ""
    ) -> BatchResult:
        """
        Validate multiple tags in batches.

        Args:
            tags: List of tags to validate
            context: Context for validation

        Returns:
            BatchResult with validation results
        """
        items = [
            BatchItem(id=tag, data={"tag": tag})
            for tag in tags
        ]

        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        tasks = [
            self._process_tag_batch(batch, context)
            for batch in batches
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        success_count = 0
        error_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                for item in batches[i]:
                    item.error = str(result)
                    all_items.append(item)
                    error_count += 1
            else:
                all_items.extend(result)
                success_count += sum(1 for item in result if item.result)
                error_count += sum(1 for item in result if item.error)

        return BatchResult(
            items=all_items,
            batch_count=len(batches),
            total_items=len(items),
            success_count=success_count,
            error_count=error_count
        )

    async def _process_tag_batch(
        self,
        batch: List[BatchItem],
        context: str
    ) -> List[BatchItem]:
        """Process a batch of tags for validation."""
        async with self._semaphore:
            tags_list = [item.data["tag"] for item in batch]

            prompt = f"""Validate these tags for consistency and format:

TAGS TO VALIDATE:
{json.dumps(tags_list, indent=2)}

CONTEXT:
{context}

For each tag, output:
TAG: [TAG_NAME]
VALID: true/false
ISSUES: Any issues found (or "none")
SUGGESTION: Corrected tag if invalid (or "N/A")

---"""

            try:
                response = await self.llm_caller(
                    prompt=prompt,
                    system_prompt="You are a tag validation specialist. Validate tag format and consistency.",
                    function=LLMFunction.TAG_VALIDATION
                )

                # Parse response
                for item in batch:
                    tag = item.data["tag"]
                    # Look for this tag in response
                    tag_pattern = rf'TAG:\s*\[?{re.escape(tag)}\]?\s*VALID:\s*(true|false)'
                    match = re.search(tag_pattern, response, re.IGNORECASE)
                    if match:
                        item.result = "valid" if match.group(1).lower() == "true" else "invalid"
                    else:
                        item.result = "unknown"

                return batch

            except Exception as e:
                for item in batch:
                    item.error = str(e)
                return batch


# Convenience function
def create_batch_processor(
    llm_caller: Callable[..., Awaitable[str]],
    batch_size: int = 5
) -> BatchProcessor:
    """Create a batch processor with the given LLM caller."""
    return BatchProcessor(llm_caller, batch_size)

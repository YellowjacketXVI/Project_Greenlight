"""
Frame Evaluation Agent

Uses Gemini to analyze generated frames against expected output and context,
producing prioritized fix tasks for targeted image editing.

Evaluation Categories:
1. Scene/Environment - setting, props, time of day, weather
2. Composition/Framing - camera angle, shot type, framing
3. Pose/Positioning - character placement, body language, gestures
4. Character Consistency - face, clothing, age, features vs reference
5. Cinematic Quality - lighting, mood, atmosphere, color grading
6. Continuity - consistency with adjacent frames (N-1, N+1)
"""

import json
import base64
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from greenlight.llm.api_clients import GeminiClient


class FixPriority(Enum):
    CRITICAL = 1  # Must fix - completely wrong
    MAJOR = 2     # Should fix - significant deviation
    MINOR = 3     # Could fix - polish/enhancement
    COSMETIC = 4  # Optional - minor tweaks


class FixCategory(Enum):
    SCENE_ENVIRONMENT = "scene_environment"
    COMPOSITION_FRAMING = "composition_framing"
    POSE_POSITIONING = "pose_positioning"
    CHARACTER_CONSISTENCY = "character_consistency"
    CINEMATIC_QUALITY = "cinematic_quality"
    CONTINUITY = "continuity"


@dataclass
class FixTask:
    """A specific fix to apply to the image."""
    category: FixCategory
    priority: FixPriority
    issue: str  # What's wrong
    fix_instruction: str  # How to fix it
    preserve_elements: list[str] = field(default_factory=list)  # What NOT to change


@dataclass
class FrameEvaluation:
    """Complete evaluation of a generated frame."""
    frame_id: str
    overall_score: float  # 0-10
    needs_regeneration: bool  # Too broken to edit, regenerate instead
    fix_tasks: list[FixTask] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    raw_analysis: str = ""


@dataclass
class FrameContext:
    """Context for evaluating a frame."""
    frame_id: str
    generated_image_path: Path
    original_prompt: str
    visual_description: str

    # Adjacent frames for continuity
    prev_frame_path: Optional[Path] = None
    prev_frame_description: Optional[str] = None
    next_frame_path: Optional[Path] = None
    next_frame_description: Optional[str] = None

    # Reference images
    character_refs: list[Path] = field(default_factory=list)
    location_refs: list[Path] = field(default_factory=list)

    # Scene metadata
    scene_id: str = ""
    time_of_day: str = ""
    location_name: str = ""
    characters_in_frame: list[str] = field(default_factory=list)


class FrameEvaluationAgent:
    """
    Evaluates generated frames against expected output using Gemini vision.
    Produces prioritized, categorized fix tasks for targeted editing.
    """

    EVALUATION_PROMPT = '''You are a professional film director and cinematographer evaluating a generated storyboard frame.

## FRAME CONTEXT
Frame ID: {frame_id}
Scene: {scene_id}
Location: {location_name}
Time of Day: {time_of_day}
Characters Expected: {characters}

## ORIGINAL PROMPT (What was requested)
{original_prompt}

## VISUAL DESCRIPTION (Expected outcome)
{visual_description}

## YOUR TASK
Analyze the GENERATED IMAGE (Image 1) and compare it against:
- The original prompt and visual description above
- Character reference sheets (if provided)
- Location references (if provided)
- Adjacent frames for continuity (if provided)

## EVALUATION CATEGORIES

Rate each category 1-10 and identify specific issues:

### 1. SCENE/ENVIRONMENT (Setting accuracy)
- Is the location correct?
- Are required props present?
- Is time of day correct (lighting matches dawn/dusk/night/day)?
- Weather/atmosphere correct?

### 2. COMPOSITION/FRAMING (Camera work)
- Is the shot type correct (close-up, medium, wide, etc.)?
- Is the camera angle right?
- Is the subject properly framed?

### 3. POSE/POSITIONING (Character placement)
- Is the character in the right position?
- Is body language/gesture correct?
- Are hands/arms positioned as described?

### 4. CHARACTER CONSISTENCY (vs reference)
- Does the face match the character reference?
- Is clothing correct for this character/scene?
- Age/gender/ethnicity correct?
- Hair style/color correct?

### 5. CINEMATIC QUALITY (Production value)
- Lighting quality and mood?
- Color grading appropriate?
- Professional look or CGI/artificial?
- Atmosphere and emotion conveyed?

### 6. CONTINUITY (vs adjacent frames)
- Does it flow from the previous frame?
- Will it flow into the next frame?
- Any jarring inconsistencies?

## OUTPUT FORMAT

Respond with valid JSON only:
```json
{{
    "overall_score": 7.5,
    "needs_regeneration": false,
    "strengths": [
        "Good lighting mood",
        "Correct location"
    ],
    "fix_tasks": [
        {{
            "category": "character_consistency",
            "priority": "CRITICAL",
            "issue": "Character wearing modern sweater instead of silk robe",
            "fix_instruction": "Change clothing to champagne pink silk sleeping robe with flowing fabric",
            "preserve_elements": ["pose", "camera_angle", "background", "lighting"]
        }},
        {{
            "category": "pose_positioning",
            "priority": "MAJOR",
            "issue": "Character is seated when should be standing at railing",
            "fix_instruction": "Change pose to standing at railing, hands resting on carved wood, gazing down at street",
            "preserve_elements": ["clothing_after_fix", "lighting", "background"]
        }}
    ]
}}
```

Priority levels:
- CRITICAL: Completely wrong, must fix (wrong character, wrong location, wrong time)
- MAJOR: Significant deviation from prompt (wrong pose, wrong clothing)
- MINOR: Small issues (lighting could be better, minor prop missing)
- COSMETIC: Polish only (slight color adjustment, minor enhancement)

If overall_score < 4, set needs_regeneration: true (too broken to edit).

NOW EVALUATE THE PROVIDED IMAGE:'''

    def __init__(self):
        self.client = GeminiClient()

    def evaluate_frame(self, context: FrameContext) -> FrameEvaluation:
        """
        Evaluate a generated frame against its expected output and context.
        Returns prioritized fix tasks.
        """
        # Build the evaluation prompt
        prompt = self.EVALUATION_PROMPT.format(
            frame_id=context.frame_id,
            scene_id=context.scene_id or "Unknown",
            location_name=context.location_name or "Unknown",
            time_of_day=context.time_of_day or "Unknown",
            characters=", ".join(context.characters_in_frame) or "Unknown",
            original_prompt=context.original_prompt,
            visual_description=context.visual_description
        )

        # Collect all images for the evaluation
        images = []
        image_descriptions = []

        # Main generated image (required)
        images.append(context.generated_image_path)
        image_descriptions.append("Image 1: GENERATED IMAGE (evaluate this)")

        # Character references
        for i, ref in enumerate(context.character_refs[:2]):  # Max 2 char refs
            images.append(ref)
            image_descriptions.append(f"Image {len(images)}: Character reference sheet")

        # Location references
        for i, ref in enumerate(context.location_refs[:1]):  # Max 1 loc ref
            images.append(ref)
            image_descriptions.append(f"Image {len(images)}: Location reference")

        # Previous frame for continuity
        if context.prev_frame_path and context.prev_frame_path.exists():
            images.append(context.prev_frame_path)
            image_descriptions.append(f"Image {len(images)}: PREVIOUS FRAME ({context.frame_id} - 1) - {context.prev_frame_description or 'No description'}")

        # Next frame for continuity
        if context.next_frame_path and context.next_frame_path.exists():
            images.append(context.next_frame_path)
            image_descriptions.append(f"Image {len(images)}: NEXT FRAME ({context.frame_id} + 1) - {context.next_frame_description or 'No description'}")

        # Add image descriptions to prompt
        full_prompt = prompt + "\n\n## IMAGES PROVIDED\n" + "\n".join(image_descriptions)

        # Call Gemini with vision
        response = self._call_gemini_vision(full_prompt, images)

        # Parse the response
        return self._parse_evaluation(context.frame_id, response)

    def _call_gemini_vision(self, prompt: str, image_paths: list[Path]) -> str:
        """Call Gemini with multiple images for evaluation."""
        import httpx
        import os

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not set")

        # Build content parts - images first, then text
        parts = []

        for img_path in image_paths:
            if img_path.exists():
                with open(img_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")

                # Determine mime type
                suffix = img_path.suffix.lower()
                mime_type = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp"
                }.get(suffix, "image/png")

                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": img_data
                    }
                })

        # Add text prompt last
        parts.append({"text": prompt})

        # Build request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096
            }
        }

        # Make request
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
            result = response.json()

        # Extract text
        text = ""
        candidates = result.get("candidates", [])
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]

        return text

    def _parse_evaluation(self, frame_id: str, response: str) -> FrameEvaluation:
        """Parse Gemini's JSON response into FrameEvaluation."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            # Parse fix tasks
            fix_tasks = []
            for task_data in data.get("fix_tasks", []):
                fix_tasks.append(FixTask(
                    category=FixCategory(task_data["category"]),
                    priority=FixPriority[task_data["priority"]],
                    issue=task_data["issue"],
                    fix_instruction=task_data["fix_instruction"],
                    preserve_elements=task_data.get("preserve_elements", [])
                ))

            # Sort by priority
            fix_tasks.sort(key=lambda t: t.priority.value)

            return FrameEvaluation(
                frame_id=frame_id,
                overall_score=data.get("overall_score", 5.0),
                needs_regeneration=data.get("needs_regeneration", False),
                fix_tasks=fix_tasks,
                strengths=data.get("strengths", []),
                raw_analysis=response
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return a default evaluation if parsing fails
            return FrameEvaluation(
                frame_id=frame_id,
                overall_score=5.0,
                needs_regeneration=False,
                fix_tasks=[],
                strengths=[],
                raw_analysis=f"Parse error: {e}\n\nRaw response:\n{response}"
            )

    def generate_edit_prompt(self, evaluation: FrameEvaluation, max_fixes: int = 3) -> str:
        """
        Generate an optimized edit prompt from the evaluation.
        Combines top priority fixes into a single coherent edit instruction.
        """
        if not evaluation.fix_tasks:
            return ""

        # Take top N fixes by priority
        top_fixes = evaluation.fix_tasks[:max_fixes]

        # Collect all preserve elements
        all_preserve = set()
        for fix in top_fixes:
            all_preserve.update(fix.preserve_elements)

        # Build the edit prompt
        changes = []
        for fix in top_fixes:
            changes.append(f"- {fix.fix_instruction}")

        preserve_list = ", ".join(all_preserve) if all_preserve else "overall composition and lighting"

        prompt = f'''APPLY THESE SPECIFIC FIXES:
{chr(10).join(changes)}

PRESERVE EXACTLY: {preserve_list}

Do not change anything not mentioned in the fixes above.'''

        return prompt


# Convenience function for quick evaluation
def quick_evaluate_frame(
    generated_image: Path,
    original_prompt: str,
    visual_description: str,
    frame_id: str = "1.1",
    character_refs: list[Path] = None,
    prev_frame: Path = None,
    next_frame: Path = None
) -> FrameEvaluation:
    """Quick evaluation of a single frame."""
    agent = FrameEvaluationAgent()

    context = FrameContext(
        frame_id=frame_id,
        generated_image_path=generated_image,
        original_prompt=original_prompt,
        visual_description=visual_description,
        character_refs=character_refs or [],
        prev_frame_path=prev_frame,
        next_frame_path=next_frame
    )

    return agent.evaluate_frame(context)

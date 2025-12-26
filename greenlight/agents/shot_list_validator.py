"""
Greenlight Shot List Validator Agent

Single-pass AI agent that validates shot list format and content:
- Validates all required fields are present
- Checks notation format compliance
- Injects missed shots from visual script
- Fixes improper formatting
- Cross-checks with context engine for consistency

Uses strict system prompt to ensure format adherence.
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Set, TYPE_CHECKING
from datetime import datetime

from greenlight.agents.base_agent import BaseAgent, AgentConfig, AgentResponse
from greenlight.core.constants import LLMFunction
from greenlight.core.logging_config import get_logger
from greenlight.config.notation_patterns import REGEX_PATTERNS

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from greenlight.context.context_engine import ContextEngine, ContextQuery

logger = get_logger("agents.shot_list_validator")


# =============================================================================
# VALIDATION RESULT TYPES
# =============================================================================

@dataclass
class ValidationIssue:
    """A single validation issue found."""
    shot_id: str
    issue_type: str  # 'missing_field', 'format_error', 'missing_shot', 'inconsistency'
    field: str
    message: str
    severity: str = "warning"  # 'error', 'warning', 'info'
    auto_fixed: bool = False
    fix_applied: str = ""


@dataclass
class ValidationResult:
    """Result of shot list validation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    shots_validated: int = 0
    shots_fixed: int = 0
    shots_injected: int = 0
    corrected_shot_list: Dict[str, Any] = field(default_factory=dict)
    validation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [
                {
                    "shot_id": i.shot_id,
                    "issue_type": i.issue_type,
                    "field": i.field,
                    "message": i.message,
                    "severity": i.severity,
                    "auto_fixed": i.auto_fixed,
                    "fix_applied": i.fix_applied
                }
                for i in self.issues
            ],
            "shots_validated": self.shots_validated,
            "shots_fixed": self.shots_fixed,
            "shots_injected": self.shots_injected,
            "validation_timestamp": self.validation_timestamp
        }


# =============================================================================
# STRICT SYSTEM PROMPT
# =============================================================================

VALIDATOR_SYSTEM_PROMPT = """You are a STRICT Shot List Format Validator for cinematic storyboard generation.

Your role is to ensure ABSOLUTE COMPLIANCE with the shot list format specification.

## REQUIRED FIELDS FOR EACH SHOT:
1. shot_id: Format "X.Y" where X=scene number, Y=frame number (e.g., "1.3", "2.1")
2. scene_number: Integer >= 1
3. frame_number: Integer >= 1
4. prompt: Non-empty string, max 250 words
5. camera: Camera instruction in format "[CAM: <instruction>]"
6. position: Character positioning in format "[POS: <positions>]"
7. lighting: Lighting instruction in format "[LIGHT: <instruction>]"

## NOTATION FORMAT REQUIREMENTS:
- Camera: [CAM: Shot type, angle, movement, lens] e.g., [CAM: Medium close-up, eye level, static, 50mm]
- Position: [POS: TAG position, TAG position] e.g., [POS: CHAR_MEI center, CHAR_LIN screen right]
- Lighting: [LIGHT: Key description, fill, atmosphere] e.g., [LIGHT: High key, soft fill, warm atmosphere]

## TAG FORMAT REQUIREMENTS (6 Canonical Prefixes):
Tags are literal identifiers wrapped in brackets [PREFIX_NAME]:
- Character tags: [CHAR_NAME] e.g., [CHAR_MEI], [CHAR_THE_GENERAL]
- Location tags: [LOC_NAME] e.g., [LOC_FLOWER_SHOP], [LOC_PALACE]
- Prop tags: [PROP_NAME] e.g., [PROP_SWORD], [PROP_JADE_HAIRPIN]
- Concept tags: [CONCEPT_NAME] e.g., [CONCEPT_HONOR], [CONCEPT_FREEDOM]
- Event tags: [EVENT_NAME] e.g., [EVENT_WEDDING], [EVENT_BATTLE]
- Environment tags: [ENV_NAME] e.g., [ENV_RAIN], [ENV_NIGHT]

## VALIDATION RULES:
1. NO empty or null required fields
2. NO malformed notation brackets
3. NO missing scene/frame numbers
4. NO duplicate shot_ids
5. ALL tags must be uppercase with underscores
6. Prompts must be descriptive and actionable

## YOUR TASK:
Analyze the shot list and:
1. IDENTIFY all format violations
2. DETECT missing shots (gaps in sequence)
3. FIX formatting issues where possible
4. INJECT placeholder shots for gaps
5. REPORT all issues with severity levels

Be STRICT. Be PRECISE. No exceptions."""


# =============================================================================
# SHOT LIST VALIDATOR AGENT
# =============================================================================

class ShotListValidatorAgent(BaseAgent):
    """
    Single-pass validator agent for shot list format compliance.
    
    Uses context engine to cross-check:
    - Visual script for missing shots
    - World config for valid tags
    - Tag registry for reference consistency
    """
    
    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        context_engine: Optional["ContextEngine"] = None
    ):
        config = AgentConfig(
            name="ShotListValidator",
            description="Validates and corrects shot list format",
            llm_function=LLMFunction.QUALITY_CHECK,
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            temperature=0.1,  # Low temperature for strict validation
            max_tokens=8000
        )
        super().__init__(config, llm_caller)
        self.context_engine = context_engine
        
        # Compiled patterns for validation
        self.patterns = {
            "shot_id": re.compile(r'^(\d+)\.(\d+)$'),
            "camera": re.compile(REGEX_PATTERNS["camera"]),
            "position": re.compile(REGEX_PATTERNS["position"]),
            "lighting": re.compile(REGEX_PATTERNS["lighting"]),
            "char_tag": re.compile(r'^CHAR_[A-Z][A-Z0-9_]*$'),
            "loc_tag": re.compile(r'^LOC_[A-Z][A-Z0-9_]*$'),
            "prop_tag": re.compile(r'^PROP_[A-Z][A-Z0-9_]*$'),
        }

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Execute shot list validation.

        Args:
            input_data: {
                'shot_list': Dict with scenes/shots structure,
                'visual_script': Optional str for cross-checking,
                'world_config': Optional Dict for tag validation
            }

        Returns:
            AgentResponse with ValidationResult
        """
        shot_list = input_data.get('shot_list', {})
        visual_script = input_data.get('visual_script', '')
        world_config = input_data.get('world_config', {})

        logger.info("Starting shot list validation")

        # Phase 1: Local validation (no LLM)
        result = self._validate_structure(shot_list)

        # Phase 2: Cross-check with context engine
        if self.context_engine:
            context_issues = await self._cross_check_context(shot_list)
            result.issues.extend(context_issues)

        # Phase 3: Detect missing shots from visual script
        if visual_script:
            missing = self._detect_missing_shots(shot_list, visual_script)
            result.issues.extend(missing)
            result.shots_injected = len([i for i in missing if i.issue_type == 'missing_shot'])

        # Phase 4: LLM-assisted format correction
        if result.issues and self.llm_caller:
            corrected = await self._llm_correct_issues(shot_list, result.issues)
            result.corrected_shot_list = corrected
            result.shots_fixed = len([i for i in result.issues if i.auto_fixed])
        else:
            result.corrected_shot_list = shot_list

        # Determine overall validity
        error_count = len([i for i in result.issues if i.severity == 'error' and not i.auto_fixed])
        result.is_valid = error_count == 0

        logger.info(f"Validation complete: {result.shots_validated} shots, "
                   f"{len(result.issues)} issues, {result.shots_fixed} fixed")

        return AgentResponse.success_response(
            content=result.to_dict(),
            raw_response=json.dumps(result.to_dict(), indent=2)
        )

    def parse_response(self, raw_response: str) -> Any:
        """Parse LLM response for corrections."""
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            return {"raw": raw_response}

    def _validate_structure(self, shot_list: Dict[str, Any]) -> ValidationResult:
        """Validate shot list structure and format."""
        result = ValidationResult(is_valid=True)
        seen_ids: Set[str] = set()

        scenes = shot_list.get('scenes', [])

        for scene in scenes:
            scene_num = scene.get('scene_number', 0)
            shots = scene.get('shots', [])

            for shot in shots:
                result.shots_validated += 1
                shot_id = shot.get('shot_id', '')

                # Check shot_id format
                if not shot_id:
                    result.issues.append(ValidationIssue(
                        shot_id=f"scene_{scene_num}_unknown",
                        issue_type="missing_field",
                        field="shot_id",
                        message="Missing shot_id",
                        severity="error"
                    ))
                elif not self.patterns["shot_id"].match(shot_id):
                    result.issues.append(ValidationIssue(
                        shot_id=shot_id,
                        issue_type="format_error",
                        field="shot_id",
                        message=f"Invalid shot_id format: {shot_id}. Expected X.Y",
                        severity="error"
                    ))
                elif shot_id in seen_ids:
                    result.issues.append(ValidationIssue(
                        shot_id=shot_id,
                        issue_type="format_error",
                        field="shot_id",
                        message=f"Duplicate shot_id: {shot_id}",
                        severity="error"
                    ))
                else:
                    seen_ids.add(shot_id)

                # Check required fields
                self._validate_required_fields(shot, shot_id, result)

                # Check notation formats
                self._validate_notations(shot, shot_id, result)

                # Check tag formats
                self._validate_tags(shot, shot_id, result)

        return result

    def _validate_required_fields(
        self,
        shot: Dict,
        shot_id: str,
        result: ValidationResult
    ) -> None:
        """Validate required fields are present."""
        required = ['scene_number', 'frame_number', 'prompt']

        for field in required:
            value = shot.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                result.issues.append(ValidationIssue(
                    shot_id=shot_id,
                    issue_type="missing_field",
                    field=field,
                    message=f"Missing or empty required field: {field}",
                    severity="error"
                ))

        # Check prompt length
        prompt = shot.get('prompt', '')
        if prompt:
            word_count = len(prompt.split())
            if word_count > 250:
                result.issues.append(ValidationIssue(
                    shot_id=shot_id,
                    issue_type="format_error",
                    field="prompt",
                    message=f"Prompt exceeds 250 word limit ({word_count} words)",
                    severity="warning"
                ))

    def _validate_notations(
        self,
        shot: Dict,
        shot_id: str,
        result: ValidationResult
    ) -> None:
        """Validate notation formats."""
        notation_fields = [
            ('camera', 'camera', '[CAM: instruction]'),
            ('position', 'position', '[POS: positions]'),
            ('lighting', 'lighting', '[LIGHT: instruction]'),
        ]

        for field, pattern_key, expected_format in notation_fields:
            value = shot.get(field, '')
            if value:
                # Check if it's wrapped in brackets or just the content
                if value.startswith('['):
                    if not self.patterns[pattern_key].match(value):
                        result.issues.append(ValidationIssue(
                            shot_id=shot_id,
                            issue_type="format_error",
                            field=field,
                            message=f"Invalid {field} format. Expected: {expected_format}",
                            severity="warning"
                        ))

    def _validate_tags(
        self,
        shot: Dict,
        shot_id: str,
        result: ValidationResult
    ) -> None:
        """Validate tag formats (all 6 canonical prefixes)."""
        tag_fields = [
            ('character_tags', 'char_tag', '[CHAR_MEI]'),
            ('location_tags', 'loc_tag', '[LOC_PALACE]'),
            ('prop_tags', 'prop_tag', '[PROP_SWORD]'),
            ('concept_tags', 'concept_tag', '[CONCEPT_HONOR]'),
            ('event_tags', 'event_tag', '[EVENT_BATTLE]'),
            ('env_tags', 'env_tag', '[ENV_RAIN]'),
        ]

        for field, pattern_key, expected_format in tag_fields:
            tags = shot.get(field, [])
            for tag in tags:
                # Clean tag if it has brackets
                clean_tag = tag.strip('[]')
                if pattern_key in self.patterns and not self.patterns[pattern_key].match(clean_tag):
                    result.issues.append(ValidationIssue(
                        shot_id=shot_id,
                        issue_type="format_error",
                        field=field,
                        message=f"Invalid tag format: {tag}. Expected format like: {expected_format}",
                        severity="warning"
                    ))

    async def _cross_check_context(
        self,
        shot_list: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Cross-check shot list with context engine."""
        issues = []

        if not self.context_engine:
            return issues

        # Get all tags from shot list
        all_tags = set()
        for scene in shot_list.get('scenes', []):
            for shot in scene.get('shots', []):
                all_tags.update(shot.get('character_tags', []))
                all_tags.update(shot.get('location_tags', []))
                all_tags.update(shot.get('prop_tags', []))

        # Check each tag against registry
        for tag in all_tags:
            clean_tag = tag.strip('[]')
            if not self.context_engine.tag_registry.get(clean_tag):
                issues.append(ValidationIssue(
                    shot_id="global",
                    issue_type="inconsistency",
                    field="tags",
                    message=f"Tag '{clean_tag}' not found in tag registry",
                    severity="warning"
                ))

        # Check world config consistency
        world_config = self.context_engine.get_world_config()
        if world_config:
            registered_chars = set(world_config.get('characters', {}).keys())
            registered_locs = set(world_config.get('locations', {}).keys())

            for tag in all_tags:
                clean_tag = tag.strip('[]')
                if clean_tag.startswith('CHAR_') and clean_tag not in registered_chars:
                    issues.append(ValidationIssue(
                        shot_id="global",
                        issue_type="inconsistency",
                        field="character_tags",
                        message=f"Character '{clean_tag}' not in world config",
                        severity="info"
                    ))
                elif clean_tag.startswith('LOC_') and clean_tag not in registered_locs:
                    issues.append(ValidationIssue(
                        shot_id="global",
                        issue_type="inconsistency",
                        field="location_tags",
                        message=f"Location '{clean_tag}' not in world config",
                        severity="info"
                    ))

        return issues

    def _detect_missing_shots(
        self,
        shot_list: Dict[str, Any],
        visual_script: str
    ) -> List[ValidationIssue]:
        """Detect missing shots by comparing with visual script."""
        issues = []

        # Extract frame IDs from visual script using scene.frame.camera notation
        # Primary pattern: [1.2.cA] (camera block header format)
        new_frame_pattern = re.compile(r'\[(\d+)\.(\d+)\.c[A-Z]\]')
        # Legacy pattern: {frame_1.2} (for backwards compatibility)
        legacy_frame_pattern = re.compile(r'\{frame_(\d+)\.(\d+)\}')

        script_frames = set()
        # Try new format first
        for match in new_frame_pattern.finditer(visual_script):
            scene_num = int(match.group(1))
            frame_num = int(match.group(2))
            script_frames.add((scene_num, frame_num))

        # Also check legacy format for backwards compatibility
        for match in legacy_frame_pattern.finditer(visual_script):
            scene_num = int(match.group(1))
            frame_num = int(match.group(2))
            script_frames.add((scene_num, frame_num))

        # Get existing shot IDs
        existing_shots = set()
        for scene in shot_list.get('scenes', []):
            for shot in scene.get('shots', []):
                shot_id = shot.get('shot_id', '')
                if self.patterns["shot_id"].match(shot_id):
                    parts = shot_id.split('.')
                    existing_shots.add((int(parts[0]), int(parts[1])))

        # Find missing shots
        missing = script_frames - existing_shots
        for scene_num, frame_num in sorted(missing):
            issues.append(ValidationIssue(
                shot_id=f"{scene_num}.{frame_num}",
                issue_type="missing_shot",
                field="shot",
                message=f"Shot {scene_num}.{frame_num} found in visual script but missing from shot list",
                severity="error"
            ))

        # Check for sequence gaps within scenes
        scenes_in_list = {}
        for scene in shot_list.get('scenes', []):
            scene_num = scene.get('scene_number', 0)
            frames = []
            for shot in scene.get('shots', []):
                frames.append(shot.get('frame_number', 0))
            if frames:
                scenes_in_list[scene_num] = sorted(frames)

        for scene_num, frames in scenes_in_list.items():
            if frames:
                expected = list(range(1, max(frames) + 1))
                gaps = set(expected) - set(frames)
                for gap in sorted(gaps):
                    issues.append(ValidationIssue(
                        shot_id=f"{scene_num}.{gap}",
                        issue_type="missing_shot",
                        field="sequence",
                        message=f"Gap in frame sequence: missing frame {gap} in scene {scene_num}",
                        severity="warning"
                    ))

        return issues

    async def _llm_correct_issues(
        self,
        shot_list: Dict[str, Any],
        issues: List[ValidationIssue]
    ) -> Dict[str, Any]:
        """Use LLM to correct format issues."""
        if not self.llm_caller:
            return shot_list

        # Filter correctable issues
        correctable = [i for i in issues if i.issue_type in ('format_error', 'missing_field')]

        if not correctable:
            return shot_list

        # Build correction prompt
        issues_text = "\n".join([
            f"- Shot {i.shot_id}: {i.field} - {i.message}"
            for i in correctable[:20]  # Limit to 20 issues
        ])

        prompt = f"""Correct the following shot list format issues.

ISSUES FOUND:
{issues_text}

CURRENT SHOT LIST (partial):
{json.dumps(shot_list.get('scenes', [])[:3], indent=2)}

For each issue:
1. Identify the correct format
2. Provide the corrected value

Return a JSON object with corrections:
{{
    "corrections": [
        {{"shot_id": "X.Y", "field": "field_name", "corrected_value": "value"}}
    ]
}}

Be STRICT about format compliance."""

        try:
            response = await self.call_llm(prompt)
            corrections = self.parse_response(response)

            # Apply corrections
            corrected_list = self._apply_corrections(shot_list, corrections, issues)
            return corrected_list

        except Exception as e:
            logger.error(f"LLM correction failed: {e}")
            return shot_list

    def _apply_corrections(
        self,
        shot_list: Dict[str, Any],
        corrections: Dict[str, Any],
        issues: List[ValidationIssue]
    ) -> Dict[str, Any]:
        """Apply LLM corrections to shot list."""
        import copy
        corrected = copy.deepcopy(shot_list)

        correction_list = corrections.get('corrections', [])

        for correction in correction_list:
            shot_id = correction.get('shot_id', '')
            field = correction.get('field', '')
            value = correction.get('corrected_value', '')

            if not shot_id or not field:
                continue

            # Find and update the shot
            for scene in corrected.get('scenes', []):
                for shot in scene.get('shots', []):
                    if shot.get('shot_id') == shot_id:
                        shot[field] = value

                        # Mark issue as fixed
                        for issue in issues:
                            if issue.shot_id == shot_id and issue.field == field:
                                issue.auto_fixed = True
                                issue.fix_applied = value
                        break

        return corrected

    def inject_missing_shots(
        self,
        shot_list: Dict[str, Any],
        visual_script: str
    ) -> Dict[str, Any]:
        """Inject placeholder shots for missing frames."""
        import copy
        result = copy.deepcopy(shot_list)

        # Detect missing shots
        issues = self._detect_missing_shots(shot_list, visual_script)
        missing_shots = [i for i in issues if i.issue_type == 'missing_shot']

        for issue in missing_shots:
            parts = issue.shot_id.split('.')
            if len(parts) != 2:
                continue

            scene_num = int(parts[0])
            frame_num = int(parts[1])

            # Create placeholder shot
            placeholder = {
                "shot_id": issue.shot_id,
                "scene_number": scene_num,
                "frame_number": frame_num,
                "prompt": f"[PLACEHOLDER] Frame {frame_num} of Scene {scene_num} - needs content",
                "camera": "[CAM: Medium shot, eye level, static]",
                "position": "[POS: Center frame]",
                "lighting": "[LIGHT: Natural lighting]",
                "character_tags": [],
                "location_tags": [],
                "prop_tags": [],
                "all_tags": [],
                "reference_images": {},
                "_injected": True
            }

            # Find or create scene
            scene_found = False
            for scene in result.get('scenes', []):
                if scene.get('scene_number') == scene_num:
                    scene['shots'].append(placeholder)
                    scene['shots'].sort(key=lambda s: s.get('frame_number', 0))
                    scene_found = True
                    break

            if not scene_found:
                result.setdefault('scenes', []).append({
                    "scene_number": scene_num,
                    "scene_title": f"Scene {scene_num}",
                    "location": "",
                    "shots": [placeholder]
                })

        # Sort scenes
        result['scenes'] = sorted(result.get('scenes', []), key=lambda s: s.get('scene_number', 0))

        return result


"""
Greenlight Early Validation Checkpoints

Validates content during generation to catch issues early.
Prevents full pipeline re-runs by fixing problems incrementally.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple

from greenlight.core.logging_config import get_logger
from greenlight.core.constants import LLMFunction
from greenlight.llm import TaskComplexity

logger = get_logger("pipelines.validation")


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Should be fixed but not blocking
    ERROR = "error"         # Must be fixed before continuing
    CRITICAL = "critical"   # Blocks pipeline, requires re-generation


@dataclass
class ValidationIssue:
    """A single validation issue."""
    code: str
    message: str
    severity: ValidationSeverity
    location: str = ""      # e.g., "scene_3", "frame_2.1"
    suggested_fix: str = ""
    auto_fixable: bool = False


@dataclass
class ValidationResult:
    """Result from validation check."""
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    fixes_applied: int = 0
    original_content: str = ""
    fixed_content: str = ""

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL))

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)


class EarlyValidator:
    """
    Validates generated content during pipeline execution.

    Features:
    - Tag format validation
    - Scene structure validation
    - Continuity quick checks
    - Auto-fix for common issues
    - LLM-assisted fixes for complex issues
    """

    def __init__(
        self,
        llm_caller: Optional[Callable[..., Awaitable[str]]] = None,
        strict_mode: bool = False
    ):
        """
        Initialize the validator.

        Args:
            llm_caller: Optional LLM caller for complex fixes
            strict_mode: If True, warnings are treated as errors
        """
        self.llm_caller = llm_caller
        self.strict_mode = strict_mode
        self._fix_count = 0
        self._validation_count = 0

    async def validate_scene(
        self,
        scene_content: str,
        scene_number: int,
        expected_tags: List[str] = None,
        auto_fix: bool = True
    ) -> ValidationResult:
        """
        Validate a generated scene.

        Checks:
        - Tag format (brackets, prefixes, uppercase)
        - Scene header format
        - Minimum content length
        - Expected tags present

        Args:
            scene_content: The scene content to validate
            scene_number: Scene number for context
            expected_tags: Tags that should appear in scene
            auto_fix: Whether to auto-fix issues

        Returns:
            ValidationResult with issues and optionally fixed content
        """
        self._validation_count += 1
        issues = []
        fixed_content = scene_content
        fixes_applied = 0

        # Check 1: Scene header format
        header_pattern = rf'##\s*Scene\s*{scene_number}:'
        if not re.search(header_pattern, scene_content, re.IGNORECASE):
            issues.append(ValidationIssue(
                code="MISSING_SCENE_HEADER",
                message=f"Scene {scene_number} missing proper header (## Scene {scene_number}:)",
                severity=ValidationSeverity.WARNING,
                location=f"scene_{scene_number}",
                suggested_fix=f"Add '## Scene {scene_number}:' header",
                auto_fixable=True
            ))
            if auto_fix:
                # Add header at start if missing
                if not re.search(r'##\s*Scene', scene_content):
                    fixed_content = f"## Scene {scene_number}:\n\n{fixed_content}"
                    fixes_applied += 1

        # Check 2: Tag format - find malformed tags
        malformed_tags = self._find_malformed_tags(scene_content)
        for bad_tag, suggestion in malformed_tags:
            issues.append(ValidationIssue(
                code="MALFORMED_TAG",
                message=f"Malformed tag: '{bad_tag}'",
                severity=ValidationSeverity.ERROR,
                location=f"scene_{scene_number}",
                suggested_fix=f"Use: {suggestion}",
                auto_fixable=True
            ))
            if auto_fix:
                fixed_content = fixed_content.replace(bad_tag, suggestion)
                fixes_applied += 1

        # Check 3: Missing brackets on known tags
        unbracketed = self._find_unbracketed_tags(fixed_content, expected_tags or [])
        for tag in unbracketed:
            issues.append(ValidationIssue(
                code="UNBRACKETED_TAG",
                message=f"Tag missing brackets: {tag}",
                severity=ValidationSeverity.WARNING,
                location=f"scene_{scene_number}",
                suggested_fix=f"Use: [{tag}]",
                auto_fixable=True
            ))
            if auto_fix:
                # Add brackets - be careful not to double-bracket
                pattern = rf'(?<!\[){re.escape(tag)}(?!\])'
                fixed_content = re.sub(pattern, f"[{tag}]", fixed_content)
                fixes_applied += 1

        # Check 4: Minimum content length
        content_without_header = re.sub(r'##\s*Scene\s*\d+:.*?\n', '', fixed_content)
        word_count = len(content_without_header.split())
        if word_count < 50:
            issues.append(ValidationIssue(
                code="CONTENT_TOO_SHORT",
                message=f"Scene content too short: {word_count} words (minimum 50)",
                severity=ValidationSeverity.ERROR,
                location=f"scene_{scene_number}",
                suggested_fix="Expand scene content",
                auto_fixable=False  # Requires LLM
            ))

        # Check 5: Expected tags present
        if expected_tags:
            missing_tags = self._find_missing_tags(fixed_content, expected_tags)
            if missing_tags:
                issues.append(ValidationIssue(
                    code="MISSING_EXPECTED_TAGS",
                    message=f"Expected tags not found: {', '.join(missing_tags)}",
                    severity=ValidationSeverity.WARNING,
                    location=f"scene_{scene_number}",
                    suggested_fix="Include expected tags in scene content",
                    auto_fixable=False
                ))

        # Determine if passed
        if self.strict_mode:
            passed = len(issues) == 0
        else:
            passed = all(
                i.severity not in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
                for i in issues
            )

        self._fix_count += fixes_applied

        return ValidationResult(
            passed=passed,
            issues=issues,
            fixes_applied=fixes_applied,
            original_content=scene_content,
            fixed_content=fixed_content
        )

    async def validate_frame(
        self,
        frame_content: str,
        scene_number: int,
        frame_number: int,
        auto_fix: bool = True
    ) -> ValidationResult:
        """
        Validate a generated frame prompt.

        Checks:
        - Frame notation format (scene.frame.camera)
        - Tag format in prompt
        - Shot type present
        - TAGS line present

        Args:
            frame_content: The frame content to validate
            scene_number: Scene number
            frame_number: Frame number
            auto_fix: Whether to auto-fix issues

        Returns:
            ValidationResult with issues and optionally fixed content
        """
        self._validation_count += 1
        issues = []
        fixed_content = frame_content
        fixes_applied = 0

        # Check 1: Frame notation format
        notation_pattern = rf'\[{scene_number}\.{frame_number}\.c[A-Z]\]'
        if not re.search(notation_pattern, frame_content):
            issues.append(ValidationIssue(
                code="MISSING_FRAME_NOTATION",
                message=f"Missing proper frame notation [{scene_number}.{frame_number}.cX]",
                severity=ValidationSeverity.ERROR,
                location=f"frame_{scene_number}.{frame_number}",
                suggested_fix=f"Add [{scene_number}.{frame_number}.cA] notation",
                auto_fixable=True
            ))
            if auto_fix and not re.search(r'\[\d+\.\d+\.c[A-Z]\]', frame_content):
                fixed_content = f"[{scene_number}.{frame_number}.cA] (Medium)\n{fixed_content}"
                fixes_applied += 1

        # Check 2: Shot type present
        shot_type_pattern = r'\([^)]+\)'
        if not re.search(shot_type_pattern, frame_content):
            issues.append(ValidationIssue(
                code="MISSING_SHOT_TYPE",
                message="Missing shot type (e.g., 'Wide', 'Close-up')",
                severity=ValidationSeverity.WARNING,
                location=f"frame_{scene_number}.{frame_number}",
                suggested_fix="Add shot type in parentheses",
                auto_fixable=False
            ))

        # Check 3: TAGS line present
        if "TAGS:" not in frame_content:
            issues.append(ValidationIssue(
                code="MISSING_TAGS_LINE",
                message="Missing TAGS: line",
                severity=ValidationSeverity.WARNING,
                location=f"frame_{scene_number}.{frame_number}",
                suggested_fix="Add TAGS: line with all tags in frame",
                auto_fixable=False
            ))

        # Check 4: Malformed tags in content
        malformed = self._find_malformed_tags(frame_content)
        for bad_tag, suggestion in malformed:
            issues.append(ValidationIssue(
                code="MALFORMED_TAG",
                message=f"Malformed tag: '{bad_tag}'",
                severity=ValidationSeverity.ERROR,
                location=f"frame_{scene_number}.{frame_number}",
                suggested_fix=f"Use: {suggestion}",
                auto_fixable=True
            ))
            if auto_fix:
                fixed_content = fixed_content.replace(bad_tag, suggestion)
                fixes_applied += 1

        passed = all(
            i.severity not in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
            for i in issues
        )

        return ValidationResult(
            passed=passed,
            issues=issues,
            fixes_applied=fixes_applied,
            original_content=frame_content,
            fixed_content=fixed_content
        )

    async def quick_continuity_check(
        self,
        current_scene: str,
        prior_scenes: str,
        scene_number: int
    ) -> ValidationResult:
        """
        Quick continuity check between current and prior scenes.

        Uses pattern matching for fast checks, not LLM.

        Checks:
        - Character consistency (same tags)
        - Location consistency
        - Time progression markers

        Args:
            current_scene: Current scene content
            prior_scenes: Prior scenes content
            scene_number: Current scene number

        Returns:
            ValidationResult with continuity issues
        """
        issues = []

        # Extract tags from both
        current_char_tags = set(re.findall(r'\[CHAR_[A-Z_]+\]', current_scene))
        prior_char_tags = set(re.findall(r'\[CHAR_[A-Z_]+\]', prior_scenes))

        # Check for character references to characters not established
        if scene_number > 1:
            new_chars = current_char_tags - prior_char_tags
            # New characters in later scenes should be introduced
            if new_chars and scene_number > 3:
                issues.append(ValidationIssue(
                    code="NEW_CHARACTER_LATE",
                    message=f"New characters introduced late: {', '.join(new_chars)}",
                    severity=ValidationSeverity.WARNING,
                    location=f"scene_{scene_number}",
                    suggested_fix="Ensure new characters are properly introduced",
                    auto_fixable=False
                ))

        # Check location tags
        current_loc_tags = set(re.findall(r'\[LOC_[A-Z_]+\]', current_scene))
        if not current_loc_tags:
            issues.append(ValidationIssue(
                code="MISSING_LOCATION",
                message="Scene has no location tags",
                severity=ValidationSeverity.WARNING,
                location=f"scene_{scene_number}",
                suggested_fix="Add location tag [LOC_*]",
                auto_fixable=False
            ))

        passed = all(i.severity != ValidationSeverity.ERROR for i in issues)

        return ValidationResult(
            passed=passed,
            issues=issues,
            original_content=current_scene,
            fixed_content=current_scene
        )

    async def fix_with_llm(
        self,
        content: str,
        issues: List[ValidationIssue],
        context: str = ""
    ) -> str:
        """
        Use LLM to fix validation issues that can't be auto-fixed.

        Args:
            content: Content to fix
            issues: List of issues to address
            context: Additional context

        Returns:
            Fixed content
        """
        if not self.llm_caller:
            logger.warning("No LLM caller available for fixes")
            return content

        if not issues:
            return content

        issues_text = "\n".join([
            f"- {i.code}: {i.message} (Fix: {i.suggested_fix})"
            for i in issues if not i.auto_fixable
        ])

        prompt = f"""Fix the following content issues:

ISSUES TO FIX:
{issues_text}

CONTENT:
{content}

CONTEXT:
{context}

Return the FIXED content only. Preserve all valid formatting and structure.
Do not add explanations - just return the corrected content."""

        try:
            # Use low complexity for simple fixes
            fixed = await self.llm_caller(
                prompt=prompt,
                system_prompt="You are a content fixer. Fix the specified issues while preserving valid content.",
                function=LLMFunction.TAG_VALIDATION,
                complexity_override=TaskComplexity.LOW
            )
            self._fix_count += len(issues)
            return fixed

        except Exception as e:
            logger.error(f"LLM fix failed: {e}")
            return content

    def _find_malformed_tags(self, text: str) -> List[tuple]:
        """Find malformed tags and suggest corrections."""
        malformed = []

        # Pattern 1: Tags without brackets (e.g., CHAR_MEI)
        no_bracket_pattern = r'(?<!\[)(CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)([A-Z][A-Z0-9_]*)(?!\])'
        for match in re.finditer(no_bracket_pattern, text):
            bad = match.group(0)
            suggestion = f"[{bad}]"
            malformed.append((bad, suggestion))

        # Pattern 2: Lowercase tags (e.g., [char_mei])
        lower_pattern = r'\[(char_|loc_|prop_|concept_|event_|env_)([a-z0-9_]+)\]'
        for match in re.finditer(lower_pattern, text, re.IGNORECASE):
            bad = match.group(0)
            suggestion = bad.upper()
            if bad != suggestion:
                malformed.append((bad, suggestion))

        # Pattern 3: Missing prefix (e.g., [MEI] instead of [CHAR_MEI])
        # This is harder to detect without context, so we skip for now

        return malformed

    def _find_unbracketed_tags(self, text: str, known_tags: List[str]) -> List[str]:
        """Find known tags that appear without brackets."""
        unbracketed = []
        for tag in known_tags:
            # Check if tag appears without brackets
            pattern = rf'(?<!\[){re.escape(tag)}(?!\])'
            if re.search(pattern, text):
                # Verify it's not already bracketed elsewhere
                bracketed = f"[{tag}]"
                if bracketed not in text:
                    unbracketed.append(tag)
        return unbracketed

    def _find_missing_tags(self, text: str, expected_tags: List[str]) -> List[str]:
        """Find expected tags not present in text."""
        missing = []
        for tag in expected_tags:
            bracketed = f"[{tag}]"
            if bracketed not in text:
                missing.append(tag)
        return missing

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return {
            "validations_run": self._validation_count,
            "fixes_applied": self._fix_count,
            "strict_mode": self.strict_mode
        }


# Convenience functions
def create_validator(
    llm_caller: Optional[Callable] = None,
    strict: bool = False
) -> EarlyValidator:
    """Create a validator instance."""
    return EarlyValidator(llm_caller, strict)


async def validate_scene(
    scene_content: str,
    scene_number: int,
    expected_tags: List[str] = None,
    auto_fix: bool = True
) -> ValidationResult:
    """Quick scene validation without LLM."""
    validator = EarlyValidator()
    return await validator.validate_scene(
        scene_content, scene_number, expected_tags, auto_fix
    )


async def validate_frame(
    frame_content: str,
    scene_number: int,
    frame_number: int,
    auto_fix: bool = True
) -> ValidationResult:
    """Quick frame validation without LLM."""
    validator = EarlyValidator()
    return await validator.validate_frame(
        frame_content, scene_number, frame_number, auto_fix
    )


# =============================================================================
# PROMPT QUALITY VALIDATOR
# =============================================================================

class PromptQualityValidator:
    """
    Validates frame prompts for quality and consistency issues BEFORE image generation.

    Catches issues that would result in poor/impossible image outputs:
    - Time-of-day inconsistencies (script says morning, prompt says night)
    - Physical impossibilities (sun and moon visible simultaneously)
    - Missing script elements (lighting direction not matching prompt)
    - Composition issues (multiple incompatible perspectives)
    """

    # Time-of-day keywords for detection
    TIME_KEYWORDS = {
        "dawn": ["dawn", "sunrise", "first light", "early morning light", "golden morning"],
        "morning": ["morning", "morning light", "soft morning", "bright morning", "daylight"],
        "noon": ["noon", "midday", "high sun", "harsh overhead", "direct sunlight"],
        "afternoon": ["afternoon", "afternoon light", "warm afternoon"],
        "golden_hour": ["golden hour", "sunset", "dusk", "dying light", "evening glow", "warm sunset"],
        "evening": ["evening", "twilight", "dimming light"],
        "night": ["night", "moonlight", "darkness", "lantern light", "candlelight", "starlight", "moon"]
    }

    # Celestial body patterns
    CELESTIAL_PATTERNS = {
        "sun": [r'\bsun\b', r'\bsunlight\b', r'\bsunrise\b', r'\bsunset\b', r'\bdaylight\b'],
        "moon": [r'\bmoon\b', r'\bmoonlight\b', r'\bmoonrise\b', r'\bfull moon\b', r'\bcrescent\b']
    }

    # Physical impossibility rules
    IMPOSSIBLE_COMBINATIONS = [
        {
            "elements": ["sun", "moon"],
            "issue": "Sun and moon cannot be prominently visible at equal brightness",
            "exception_pattern": r"(setting sun.*rising moon|sunrise.*fading moon)",
            "severity": ValidationSeverity.ERROR
        },
        {
            "elements": ["bright daylight", "starlight"],
            "issue": "Stars are not visible in bright daylight",
            "exception_pattern": None,
            "severity": ValidationSeverity.ERROR
        },
        {
            "elements": ["harsh noon sun", "long shadows"],
            "issue": "Noon sun creates minimal shadows, not long shadows",
            "exception_pattern": None,
            "severity": ValidationSeverity.WARNING
        }
    ]

    def __init__(self, world_config: Dict[str, Any] = None):
        """
        Initialize the prompt quality validator.

        Args:
            world_config: World configuration with visual_style, locations, etc.
        """
        self.world_config = world_config or {}
        self._issues_found = []

    def validate_prompt(
        self,
        prompt: str,
        frame_id: str,
        scene_metadata: Dict[str, Any] = None,
        lighting_notation: str = ""
    ) -> ValidationResult:
        """
        Validate a single frame prompt for quality issues.

        Args:
            prompt: The frame prompt text
            frame_id: Frame identifier (e.g., "1.2.cA")
            scene_metadata: Scene metadata including time, location from script
            lighting_notation: The [LIGHT: ...] notation for this frame

        Returns:
            ValidationResult with issues found
        """
        issues = []
        scene_metadata = scene_metadata or {}

        # 1. Time-of-day consistency check
        time_issues = self._check_time_consistency(
            prompt,
            scene_metadata.get("time", ""),
            lighting_notation,
            frame_id
        )
        issues.extend(time_issues)

        # 2. Physical reality check
        reality_issues = self._check_physical_reality(prompt, frame_id)
        issues.extend(reality_issues)

        # 3. Lighting-prompt alignment check
        lighting_issues = self._check_lighting_alignment(
            prompt,
            lighting_notation,
            frame_id
        )
        issues.extend(lighting_issues)

        # 4. Composition sanity check
        composition_issues = self._check_composition(prompt, frame_id)
        issues.extend(composition_issues)

        # Determine pass/fail
        has_errors = any(
            i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
            for i in issues
        )

        return ValidationResult(
            passed=not has_errors,
            issues=issues,
            original_content=prompt,
            fixed_content=prompt  # Will be updated if auto-fix applied
        )

    def _check_time_consistency(
        self,
        prompt: str,
        script_time: str,
        lighting_notation: str,
        frame_id: str
    ) -> List[ValidationIssue]:
        """Check that prompt time-of-day matches script/lighting direction."""
        issues = []
        prompt_lower = prompt.lower()
        lighting_lower = lighting_notation.lower()
        script_time_lower = script_time.lower()

        # Detect time-of-day in prompt
        prompt_time = self._detect_time_of_day(prompt_lower)

        # Detect time-of-day from script metadata
        script_time_detected = None
        if script_time_lower:
            for time_period, keywords in self.TIME_KEYWORDS.items():
                if any(kw in script_time_lower for kw in keywords):
                    script_time_detected = time_period
                    break

        # Detect time-of-day from lighting notation
        lighting_time = self._detect_time_of_day(lighting_lower)

        # Check for conflicts
        if script_time_detected and prompt_time:
            if not self._times_compatible(script_time_detected, prompt_time):
                issues.append(ValidationIssue(
                    code="TIME_MISMATCH_SCRIPT",
                    message=f"Prompt time ({prompt_time}) conflicts with script time ({script_time_detected})",
                    severity=ValidationSeverity.ERROR,
                    location=frame_id,
                    suggested_fix=f"Adjust prompt to match {script_time_detected} lighting",
                    auto_fixable=True
                ))

        if lighting_time and prompt_time:
            if not self._times_compatible(lighting_time, prompt_time):
                issues.append(ValidationIssue(
                    code="TIME_MISMATCH_LIGHTING",
                    message=f"Prompt time ({prompt_time}) conflicts with lighting notation ({lighting_time})",
                    severity=ValidationSeverity.WARNING,
                    location=frame_id,
                    suggested_fix=f"Align prompt with [LIGHT:] notation",
                    auto_fixable=True
                ))

        return issues

    def _detect_time_of_day(self, text: str) -> Optional[str]:
        """Detect time-of-day from text keywords."""
        text_lower = text.lower()
        for time_period, keywords in self.TIME_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return time_period
        return None

    def _times_compatible(self, time1: str, time2: str) -> bool:
        """Check if two time periods are compatible (adjacent or same)."""
        time_order = ["dawn", "morning", "noon", "afternoon", "golden_hour", "evening", "night"]

        try:
            idx1 = time_order.index(time1)
            idx2 = time_order.index(time2)
            # Compatible if same or adjacent
            return abs(idx1 - idx2) <= 1
        except ValueError:
            return True  # Unknown time, assume compatible

    def _check_physical_reality(self, prompt: str, frame_id: str) -> List[ValidationIssue]:
        """Check for physical impossibilities in the prompt."""
        issues = []
        prompt_lower = prompt.lower()

        # Check celestial bodies
        has_sun = any(
            re.search(pattern, prompt_lower)
            for pattern in self.CELESTIAL_PATTERNS["sun"]
        )
        has_moon = any(
            re.search(pattern, prompt_lower)
            for pattern in self.CELESTIAL_PATTERNS["moon"]
        )

        # Sun and moon both prominently visible is usually impossible
        if has_sun and has_moon:
            # Check for exception patterns (e.g., transition scenes)
            exception = r"(setting sun.*rising moon|sunrise.*fading moon|dawn.*pale moon|dusk.*sun)"
            if not re.search(exception, prompt_lower):
                issues.append(ValidationIssue(
                    code="PHYSICAL_IMPOSSIBILITY",
                    message="Sun and moon cannot be prominently visible simultaneously",
                    severity=ValidationSeverity.ERROR,
                    location=frame_id,
                    suggested_fix="Remove one celestial body or describe a transition scene",
                    auto_fixable=True
                ))

        # Check for other impossible combinations
        for combo in self.IMPOSSIBLE_COMBINATIONS:
            elements_found = all(
                any(kw in prompt_lower for kw in [combo["elements"][i]])
                for i in range(len(combo["elements"]))
            )
            if elements_found:
                if combo.get("exception_pattern"):
                    if re.search(combo["exception_pattern"], prompt_lower):
                        continue
                issues.append(ValidationIssue(
                    code="PHYSICAL_IMPOSSIBILITY",
                    message=combo["issue"],
                    severity=combo["severity"],
                    location=frame_id,
                    suggested_fix="Adjust description to be physically plausible",
                    auto_fixable=False
                ))

        return issues

    def _check_lighting_alignment(
        self,
        prompt: str,
        lighting_notation: str,
        frame_id: str
    ) -> List[ValidationIssue]:
        """Check that prompt lighting matches the [LIGHT:] notation."""
        issues = []

        if not lighting_notation:
            return issues

        lighting_lower = lighting_notation.lower()
        prompt_lower = prompt.lower()

        # Extract key light direction from notation
        key_directions = {
            "from east": ["east", "morning", "sunrise", "dawn"],
            "from west": ["west", "sunset", "dusk", "evening"],
            "from north": ["north", "front", "facing"],
            "from south": ["south", "behind", "backlit"],
            "overhead": ["noon", "midday", "directly above", "harsh overhead"],
            "low angle": ["golden hour", "long shadows", "sunset", "sunrise"]
        }

        notation_direction = None
        for direction, _ in key_directions.items():
            if direction in lighting_lower:
                notation_direction = direction
                break

        # Check for contradictions
        if notation_direction:
            opposite_map = {
                "from east": "from west",
                "from west": "from east",
                "from north": "from south",
                "from south": "from north"
            }
            opposite = opposite_map.get(notation_direction)
            if opposite and opposite.replace("from ", "") in prompt_lower:
                issues.append(ValidationIssue(
                    code="LIGHTING_DIRECTION_CONFLICT",
                    message=f"Prompt mentions {opposite} but lighting notation says {notation_direction}",
                    severity=ValidationSeverity.WARNING,
                    location=frame_id,
                    suggested_fix=f"Align prompt with {notation_direction} key light",
                    auto_fixable=True
                ))

        return issues

    def _check_composition(self, prompt: str, frame_id: str) -> List[ValidationIssue]:
        """Check for composition issues that would confuse image generation."""
        issues = []
        prompt_lower = prompt.lower()

        # Check for multiple incompatible shot types in same prompt
        shot_types = {
            "wide": ["wide shot", "establishing shot", "wide view", "full view of"],
            "close": ["close-up", "closeup", "close up", "extreme close", "tight on"],
            "medium": ["medium shot", "waist up", "mid-shot"]
        }

        found_shots = []
        for shot_type, patterns in shot_types.items():
            if any(p in prompt_lower for p in patterns):
                found_shots.append(shot_type)

        if len(found_shots) > 1 and "wide" in found_shots and "close" in found_shots:
            issues.append(ValidationIssue(
                code="CONFLICTING_SHOT_TYPES",
                message="Prompt describes both wide and close-up shots - these cannot coexist",
                severity=ValidationSeverity.WARNING,
                location=frame_id,
                suggested_fix="Split into separate frames or choose one shot type",
                auto_fixable=False
            ))

        # Check for perspective conflicts
        perspectives = {
            "high": ["high angle", "bird's eye", "overhead", "looking down"],
            "low": ["low angle", "worm's eye", "looking up", "from below"],
            "level": ["eye level", "straight on"]
        }

        found_perspectives = []
        for perspective, patterns in perspectives.items():
            if any(p in prompt_lower for p in patterns):
                found_perspectives.append(perspective)

        if "high" in found_perspectives and "low" in found_perspectives:
            issues.append(ValidationIssue(
                code="CONFLICTING_PERSPECTIVES",
                message="Prompt describes both high and low angles simultaneously",
                severity=ValidationSeverity.ERROR,
                location=frame_id,
                suggested_fix="Choose one camera angle per frame",
                auto_fixable=False
            ))

        return issues

    def auto_fix_prompt(
        self,
        prompt: str,
        issues: List[ValidationIssue],
        scene_metadata: Dict[str, Any] = None
    ) -> str:
        """
        Attempt to auto-fix issues in the prompt.

        Args:
            prompt: Original prompt text
            issues: List of validation issues
            scene_metadata: Scene context for fixes

        Returns:
            Fixed prompt text
        """
        fixed = prompt
        scene_metadata = scene_metadata or {}

        for issue in issues:
            if not issue.auto_fixable:
                continue

            if issue.code == "TIME_MISMATCH_SCRIPT":
                # Fix time-of-day references
                script_time = scene_metadata.get("time", "morning")
                fixed = self._fix_time_references(fixed, script_time)

            elif issue.code == "PHYSICAL_IMPOSSIBILITY" and "sun and moon" in issue.message.lower():
                # Remove conflicting celestial body based on time
                time_of_day = self._detect_time_of_day(fixed)
                if time_of_day in ["night", "evening"]:
                    fixed = self._remove_celestial(fixed, "sun")
                else:
                    fixed = self._remove_celestial(fixed, "moon")

            elif issue.code == "LIGHTING_DIRECTION_CONFLICT":
                # This requires more context - mark as needing manual review
                pass

        return fixed

    def _fix_time_references(self, prompt: str, target_time: str) -> str:
        """Replace time-of-day references with target time."""
        # Map time periods to replacement phrases
        time_replacements = {
            "dawn": "golden morning light at dawn",
            "morning": "soft morning light",
            "noon": "harsh midday sun",
            "afternoon": "warm afternoon light",
            "golden_hour": "golden hour glow",
            "evening": "fading evening light",
            "night": "pale moonlight"
        }

        # Find and replace conflicting time references
        replacement = time_replacements.get(target_time, target_time)

        # Replace common mismatched patterns
        patterns_to_replace = [
            (r'moonlight\b', replacement if target_time not in ["night", "evening"] else "moonlight"),
            (r'bright sunlight\b', replacement if target_time in ["night", "evening"] else "bright sunlight"),
            (r'harsh noon sun\b', replacement if target_time != "noon" else "harsh noon sun"),
        ]

        result = prompt
        for pattern, repl in patterns_to_replace:
            if target_time in ["night", "evening"] and "sun" in pattern:
                result = re.sub(pattern, repl.replace("sun", "moon"), result, flags=re.IGNORECASE)
            elif target_time not in ["night", "evening"] and "moon" in pattern:
                result = re.sub(pattern, repl.replace("moon", "sun"), result, flags=re.IGNORECASE)

        return result

    def _remove_celestial(self, prompt: str, body: str) -> str:
        """Remove references to a celestial body."""
        if body == "sun":
            patterns = [
                r'\bsun\b', r'\bsunlight\b', r'\bsunrise\b',
                r'\bbright sun\b', r'\bsetting sun\b'
            ]
            replacement = "sky"
        else:  # moon
            patterns = [
                r'\bmoon\b', r'\bmoonlight\b', r'\bfull moon\b',
                r'\brising moon\b', r'\bpale moon\b'
            ]
            replacement = "sky"

        result = prompt
        for pattern in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Clean up any awkward phrasing
        result = re.sub(r'\bthe sky and sky\b', 'the sky', result)
        result = re.sub(r'\bsky sky\b', 'sky', result)

        return result


def create_prompt_validator(world_config: Dict[str, Any] = None) -> PromptQualityValidator:
    """Create a prompt quality validator instance."""
    return PromptQualityValidator(world_config)


async def validate_frame_prompt(
    prompt: str,
    frame_id: str,
    scene_metadata: Dict[str, Any] = None,
    lighting_notation: str = "",
    auto_fix: bool = True
) -> ValidationResult:
    """
    Convenience function to validate a frame prompt.

    Args:
        prompt: Frame prompt text
        frame_id: Frame identifier
        scene_metadata: Scene metadata (time, location, etc.)
        lighting_notation: The [LIGHT:] notation
        auto_fix: Whether to attempt auto-fixes

    Returns:
        ValidationResult with issues and optionally fixed content
    """
    validator = PromptQualityValidator()
    result = validator.validate_prompt(prompt, frame_id, scene_metadata, lighting_notation)

    if auto_fix and result.issues:
        fixable_issues = [i for i in result.issues if i.auto_fixable]
        if fixable_issues:
            result.fixed_content = validator.auto_fix_prompt(
                prompt, fixable_issues, scene_metadata
            )
            result.fixes_applied = len(fixable_issues)

    return result


# =============================================================================
# CINEMATIC CONSISTENCY VALIDATOR (OUTPUT-LEVEL)
# =============================================================================

class CinematicConsistencyValidator:
    """
    Validates and enforces cinematic rules at the OUTPUT level after LLM generation.

    This validator catches issues that the LLM may have introduced:
    - 180-degree rule violations (character position flips)
    - Shot rhythm problems (too many consecutive same-type shots)
    - Cross-scene continuity breaks
    - Screen direction inconsistencies

    Runs AFTER frame prompts are generated and can auto-fix issues.
    """

    # Screen position keywords for detection
    POSITION_PATTERNS = {
        "left": [r"screen-left", r"screen left", r"frame left", r"left of frame", r"on the left"],
        "right": [r"screen-right", r"screen right", r"frame right", r"right of frame", r"on the right"],
        "center": [r"center", r"centered", r"middle of frame", r"in the center"]
    }

    # Facing direction patterns
    FACING_PATTERNS = {
        "left": [r"facing left", r"looks left", r"turned left", r"looking left"],
        "right": [r"facing right", r"looks right", r"turned right", r"looking right"]
    }

    def __init__(self):
        """Initialize the cinematic consistency validator."""
        # Track established positions across frames
        self.character_positions: Dict[str, Dict[str, Any]] = {}
        self.axis_of_action: Optional[Tuple[str, str]] = None
        self.shot_history: List[Dict[str, str]] = []
        self.scene_number: Optional[int] = None

    def reset_scene(self, scene_number: int) -> None:
        """Reset tracking for a new scene (but preserve cross-scene data if same chars)."""
        self.scene_number = scene_number
        self.shot_history = []
        # Don't reset character_positions - they carry over for cross-scene continuity

    def validate_frame_sequence(
        self,
        frames: List[Dict[str, Any]],
        scene_number: int,
        auto_fix: bool = True
    ) -> Tuple[List[Dict[str, Any]], List[ValidationIssue]]:
        """
        Validate a sequence of frames for cinematic consistency.

        Args:
            frames: List of frame dicts with 'prompt', 'frame_id', 'shot_type', 'tags'
            scene_number: Current scene number
            auto_fix: Whether to auto-fix issues

        Returns:
            Tuple of (fixed_frames, issues_found)
        """
        self.reset_scene(scene_number)
        all_issues = []
        fixed_frames = []

        for i, frame in enumerate(frames):
            frame_issues = []
            fixed_frame = frame.copy()

            # 1. Check 180-degree rule
            position_issues = self._check_180_degree_rule(frame, i)
            frame_issues.extend(position_issues)

            # 2. Check shot rhythm
            rhythm_issues = self._check_shot_rhythm(frame, i)
            frame_issues.extend(rhythm_issues)

            # 3. Auto-fix if enabled
            if auto_fix and frame_issues:
                fixed_prompt = self._auto_fix_frame(
                    frame.get("prompt", ""),
                    frame_issues,
                    frame
                )
                fixed_frame["prompt"] = fixed_prompt
                fixed_frame["issues_fixed"] = len([i for i in frame_issues if i.auto_fixable])

            # Record this frame's shot for rhythm tracking
            self._record_shot(frame)

            all_issues.extend(frame_issues)
            fixed_frames.append(fixed_frame)

        return fixed_frames, all_issues

    def _check_180_degree_rule(
        self,
        frame: Dict[str, Any],
        frame_index: int
    ) -> List[ValidationIssue]:
        """Check for 180-degree rule violations."""
        issues = []
        prompt = frame.get("prompt", "").lower()
        frame_id = frame.get("frame_id", f"unknown.{frame_index}")
        tags = frame.get("tags", {})
        characters = tags.get("characters", [])

        for char_tag in characters:
            char_lower = char_tag.lower()

            # Detect current position in this frame
            current_position = self._detect_position(prompt, char_lower)
            current_facing = self._detect_facing(prompt, char_lower)

            if char_tag in self.character_positions:
                # Character was established before - check for violations
                established = self.character_positions[char_tag]
                established_pos = established.get("position")
                established_facing = established.get("facing")

                # Position flip violation
                if current_position and established_pos:
                    if self._is_position_flip(established_pos, current_position):
                        issues.append(ValidationIssue(
                            code="180_DEGREE_VIOLATION",
                            message=f"[{char_tag}] flipped from {established_pos} to {current_position} (180° rule violation)",
                            severity=ValidationSeverity.ERROR,
                            location=frame_id,
                            suggested_fix=f"Keep [{char_tag}] at {established_pos} as established in {established.get('frame_id')}",
                            auto_fixable=True
                        ))

                # Facing direction flip without motivation
                if current_facing and established_facing:
                    if current_facing != established_facing:
                        issues.append(ValidationIssue(
                            code="FACING_DIRECTION_FLIP",
                            message=f"[{char_tag}] facing changed from {established_facing} to {current_facing}",
                            severity=ValidationSeverity.WARNING,
                            location=frame_id,
                            suggested_fix=f"Maintain facing {established_facing} or describe character turning",
                            auto_fixable=True
                        ))
            else:
                # First appearance - establish position
                if current_position:
                    self.character_positions[char_tag] = {
                        "position": current_position,
                        "facing": current_facing,
                        "frame_id": frame_id,
                        "scene": self.scene_number
                    }

                    # Check if we can establish axis of action
                    if len(self.character_positions) == 2 and not self.axis_of_action:
                        chars = list(self.character_positions.keys())
                        pos1 = self.character_positions[chars[0]].get("position")
                        pos2 = self.character_positions[chars[1]].get("position")
                        if pos1 and pos2 and pos1 != pos2:
                            self.axis_of_action = (chars[0], chars[1])

        return issues

    def _detect_position(self, prompt: str, char_pattern: str) -> Optional[str]:
        """Detect character's screen position from prompt."""
        # Look for position keywords near character mention
        for position, patterns in self.POSITION_PATTERNS.items():
            for pattern in patterns:
                # Check if pattern appears near character mention
                if re.search(pattern, prompt):
                    return position
        return None

    def _detect_facing(self, prompt: str, char_pattern: str) -> Optional[str]:
        """Detect character's facing direction from prompt."""
        for direction, patterns in self.FACING_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, prompt):
                    return direction
        return None

    def _is_position_flip(self, established: str, current: str) -> bool:
        """Check if position change violates 180-degree rule."""
        # Left to Right or Right to Left is a violation
        flip_pairs = [("left", "right"), ("right", "left")]
        return (established, current) in flip_pairs

    def _check_shot_rhythm(
        self,
        frame: Dict[str, Any],
        frame_index: int
    ) -> List[ValidationIssue]:
        """Check for shot rhythm issues - STRICT enforcement for visual variety."""
        issues = []
        shot_type = frame.get("shot_type", "").lower()
        prompt = frame.get("prompt", "").lower()
        frame_id = frame.get("frame_id", f"unknown.{frame_index}")

        # Categorize shot type and camera angle
        category = self._categorize_shot(shot_type)
        angle = self._extract_camera_angle(shot_type, prompt)

        # Check for too many consecutive same-type shots (STRICTER: 2+ is a problem)
        if len(self.shot_history) >= 1:
            recent_categories = [s.get("category") for s in self.shot_history[-1:]]
            if all(c == category for c in recent_categories):
                issues.append(ValidationIssue(
                    code="SHOT_RHYTHM_MONOTONY",
                    message=f"2+ consecutive {category} shots detected - vary shot types",
                    severity=ValidationSeverity.WARNING,
                    location=frame_id,
                    suggested_fix=self._get_rhythm_suggestion(category),
                    auto_fixable=False
                ))

        # Check for 3+ consecutive same-type - CRITICAL issue
        if len(self.shot_history) >= 2:
            recent_categories = [s.get("category") for s in self.shot_history[-2:]]
            if all(c == category for c in recent_categories):
                issues.append(ValidationIssue(
                    code="SHOT_RHYTHM_CRITICAL",
                    message=f"3+ consecutive {category} shots - CRITICAL monotony issue",
                    severity=ValidationSeverity.ERROR,
                    location=frame_id,
                    suggested_fix=f"MUST change to different shot type: {self._get_rhythm_suggestion(category)}",
                    auto_fixable=False
                ))

        # Check if scene started without establishing shot
        if frame_index == 0 and category != "wide":
            issues.append(ValidationIssue(
                code="MISSING_ESTABLISHING_SHOT",
                message="Scene doesn't start with wide/establishing shot",
                severity=ValidationSeverity.WARNING,
                location=frame_id,
                suggested_fix="Start with WIDE or EXTREME WIDE shot to orient viewers",
                auto_fixable=False
            ))

        # Check camera angle variety (every 5+ frames should have angle variety)
        if len(self.shot_history) >= 4:
            recent_angles = [s.get("angle", "eye_level") for s in self.shot_history[-4:]]
            if len(set(recent_angles)) == 1 and angle == recent_angles[0]:
                issues.append(ValidationIssue(
                    code="CAMERA_ANGLE_MONOTONY",
                    message=f"5+ frames at {angle} angle - add LOW ANGLE or HIGH ANGLE for variety",
                    severity=ValidationSeverity.WARNING,
                    location=frame_id,
                    suggested_fix="Add LOW ANGLE (power/dominance) or HIGH ANGLE (vulnerability) shot",
                    auto_fixable=False
                ))

        # Check for missing close-up in emotional scenes (after 5 frames without one)
        if len(self.shot_history) >= 5:
            recent_categories = [s.get("category") for s in self.shot_history[-5:]]
            if "close" not in recent_categories and category != "close":
                issues.append(ValidationIssue(
                    code="MISSING_CLOSEUP",
                    message="No close-up in 6+ frames - missing emotional impact",
                    severity=ValidationSeverity.INFO,
                    location=frame_id,
                    suggested_fix="Add CLOSE-UP or EXTREME CLOSE-UP for emotional emphasis",
                    auto_fixable=False
                ))

        # Check for composition keywords in prompt
        composition_keywords = ["rule of thirds", "left-third", "right-third", "leading lines",
                               "foreground", "frame within frame", "negative space"]
        has_composition = any(kw in prompt for kw in composition_keywords)
        if not has_composition and frame_index > 0:
            issues.append(ValidationIssue(
                code="MISSING_COMPOSITION_GUIDANCE",
                message="Prompt lacks composition guidance (rule of thirds, leading lines, etc.)",
                severity=ValidationSeverity.INFO,
                location=frame_id,
                suggested_fix="Add composition: 'positioned at left-third', 'leading lines', or 'foreground interest'",
                auto_fixable=False
            ))

        return issues

    def _extract_camera_angle(self, shot_type: str, prompt: str) -> str:
        """Extract camera angle from shot type and prompt."""
        combined = f"{shot_type} {prompt}".lower()

        if any(w in combined for w in ["low angle", "looking up", "from below", "worm's eye"]):
            return "low_angle"
        elif any(w in combined for w in ["high angle", "looking down", "from above", "bird's eye", "overhead"]):
            return "high_angle"
        elif any(w in combined for w in ["dutch", "tilted", "canted"]):
            return "dutch_angle"
        elif any(w in combined for w in ["over-the-shoulder", "ots", "over shoulder"]):
            return "ots"
        elif any(w in combined for w in ["pov", "point of view", "subjective"]):
            return "pov"
        else:
            return "eye_level"

    def _categorize_shot(self, shot_type: str) -> str:
        """Categorize shot type string."""
        shot_lower = shot_type.lower()

        if any(w in shot_lower for w in ["wide", "establishing", "full", "master"]):
            return "wide"
        elif any(w in shot_lower for w in ["close", "closeup", "tight", "ecu"]):
            return "close"
        elif any(w in shot_lower for w in ["insert", "detail", "cutaway"]):
            return "insert"
        elif any(w in shot_lower for w in ["pov", "point of view"]):
            return "pov"
        elif any(w in shot_lower for w in ["reaction"]):
            return "reaction"
        else:
            return "medium"

    def _get_rhythm_suggestion(self, current_category: str) -> str:
        """Get shot type suggestion based on current rhythm."""
        suggestions = {
            "wide": "Follow with Medium or Close-up to build intimacy",
            "medium": "Add Close-up for emotion or Wide to re-establish",
            "close": "Pull back to Medium or add Reaction shot",
            "insert": "Return to Medium or character Close-up",
            "pov": "Add Reaction shot of POV character",
            "reaction": "Move to Close-up or Medium"
        }
        return suggestions.get(current_category, "Vary shot types for visual interest")

    def _record_shot(self, frame: Dict[str, Any]) -> None:
        """Record shot for rhythm analysis."""
        shot_type = frame.get("shot_type", "")
        prompt = frame.get("prompt", "")
        self.shot_history.append({
            "frame_id": frame.get("frame_id", ""),
            "shot_type": shot_type,
            "category": self._categorize_shot(shot_type),
            "angle": self._extract_camera_angle(shot_type, prompt)
        })

    def _auto_fix_frame(
        self,
        prompt: str,
        issues: List[ValidationIssue],
        frame: Dict[str, Any]
    ) -> str:
        """Auto-fix issues in the frame prompt."""
        fixed = prompt

        for issue in issues:
            if not issue.auto_fixable:
                continue

            if issue.code == "180_DEGREE_VIOLATION":
                # Extract character tag and correct position from issue
                fixed = self._fix_position_violation(fixed, issue)

            elif issue.code == "FACING_DIRECTION_FLIP":
                fixed = self._fix_facing_direction(fixed, issue)

        return fixed

    def _fix_position_violation(self, prompt: str, issue: ValidationIssue) -> str:
        """Fix a 180-degree position violation."""
        # Extract info from issue message
        # Format: "[CHAR_X] flipped from left to right"
        match = re.search(r'\[([A-Z_]+)\] flipped from (\w+) to (\w+)', issue.message)
        if not match:
            return prompt

        char_tag = match.group(1)
        correct_position = match.group(2)  # The established position
        wrong_position = match.group(3)

        # Replace wrong position with correct position
        position_map = {
            "left": ["screen-right", "screen right", "right of frame", "on the right"],
            "right": ["screen-left", "screen left", "left of frame", "on the left"]
        }

        wrong_patterns = position_map.get(wrong_position, [])
        correct_text = f"screen-{correct_position}"

        for pattern in wrong_patterns:
            if pattern in prompt.lower():
                # Case-insensitive replacement
                prompt = re.sub(re.escape(pattern), correct_text, prompt, flags=re.IGNORECASE)

        return prompt

    def _fix_facing_direction(self, prompt: str, issue: ValidationIssue) -> str:
        """Fix a facing direction inconsistency."""
        # Extract info from issue
        match = re.search(r'facing changed from (\w+) to (\w+)', issue.message)
        if not match:
            return prompt

        correct_facing = match.group(1)
        wrong_facing = match.group(2)

        # Replace wrong facing with correct
        facing_map = {
            "left": ["facing right", "looks right", "looking right"],
            "right": ["facing left", "looks left", "looking left"]
        }

        wrong_patterns = facing_map.get(wrong_facing, [])
        correct_text = f"facing {correct_facing}"

        for pattern in wrong_patterns:
            if pattern in prompt.lower():
                prompt = re.sub(re.escape(pattern), correct_text, prompt, flags=re.IGNORECASE)

        return prompt

    def get_established_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all established character positions."""
        return self.character_positions.copy()

    def inherit_positions_from_scene(
        self,
        previous_validator: "CinematicConsistencyValidator",
        shared_characters: List[str]
    ) -> None:
        """Inherit character positions from a previous scene's validator."""
        for char_tag in shared_characters:
            if char_tag in previous_validator.character_positions:
                self.character_positions[char_tag] = previous_validator.character_positions[char_tag].copy()


def create_cinematic_validator() -> CinematicConsistencyValidator:
    """Create a cinematic consistency validator instance."""
    return CinematicConsistencyValidator()


async def validate_frame_sequence(
    frames: List[Dict[str, Any]],
    scene_number: int,
    auto_fix: bool = True,
    previous_validator: CinematicConsistencyValidator = None
) -> Tuple[List[Dict[str, Any]], List[ValidationIssue], CinematicConsistencyValidator]:
    """
    Convenience function to validate a frame sequence for cinematic consistency.

    Args:
        frames: List of frame dicts
        scene_number: Current scene number
        auto_fix: Whether to auto-fix issues
        previous_validator: Validator from previous scene for cross-scene continuity

    Returns:
        Tuple of (fixed_frames, issues, validator)
    """
    validator = CinematicConsistencyValidator()

    # Inherit positions from previous scene if provided
    if previous_validator:
        # Find shared characters
        current_chars = set()
        for frame in frames:
            tags = frame.get("tags", {})
            current_chars.update(tags.get("characters", []))

        prev_chars = set(previous_validator.character_positions.keys())
        shared = list(current_chars & prev_chars)

        if shared:
            validator.inherit_positions_from_scene(previous_validator, shared)

    fixed_frames, issues = validator.validate_frame_sequence(frames, scene_number, auto_fix)

    return fixed_frames, issues, validator

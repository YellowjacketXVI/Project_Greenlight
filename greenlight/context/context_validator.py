"""
Greenlight Context Validator

Validates context integrity early in the pipeline to catch issues before they propagate.
Ensures entity references exist, tag formats are consistent, and world_config schema is valid.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
from pathlib import Path

from greenlight.core.logging_config import get_logger

logger = get_logger("context.validator")


class ValidationLevel(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ContextValidationIssue:
    """A single context validation issue."""
    code: str
    message: str
    level: ValidationLevel
    entity_type: str = ""  # "character", "location", "prop", "script", "config"
    entity_id: str = ""
    suggestion: str = ""
    auto_fixable: bool = False
    fix_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextValidationResult:
    """Result from context validation."""
    valid: bool
    issues: List[ContextValidationIssue] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0
    entities_validated: int = 0

    @property
    def has_errors(self) -> bool:
        return self.errors > 0

    @property
    def has_warnings(self) -> bool:
        return self.warnings > 0

    def add_issue(self, issue: ContextValidationIssue) -> None:
        self.issues.append(issue)
        if issue.level == ValidationLevel.ERROR or issue.level == ValidationLevel.CRITICAL:
            self.errors += 1
        elif issue.level == ValidationLevel.WARNING:
            self.warnings += 1

    def merge(self, other: "ContextValidationResult") -> None:
        """Merge another validation result into this one."""
        self.issues.extend(other.issues)
        self.warnings += other.warnings
        self.errors += other.errors
        self.entities_validated += other.entities_validated
        if other.errors > 0:
            self.valid = False


class ContextValidator:
    """
    Validates context integrity across the system.

    Features:
    - World config schema validation
    - Entity reference validation (characters, locations, props)
    - Tag format consistency checking
    - Script entity reference validation
    - Cross-reference validation between pipelines

    Usage:
        validator = ContextValidator(world_config)
        result = validator.validate_all()
        if not result.valid:
            for issue in result.issues:
                print(f"{issue.level.value}: {issue.message}")
    """

    # Valid tag prefixes
    VALID_PREFIXES = {"CHAR", "LOC", "PROP", "CONCEPT", "EVENT", "ENV"}

    # Required fields per entity type
    REQUIRED_CHARACTER_FIELDS = {"tag", "name"}
    REQUIRED_LOCATION_FIELDS = {"tag", "name"}
    REQUIRED_PROP_FIELDS = {"tag", "name"}

    # Tag pattern: [PREFIX_NAME] where PREFIX is from VALID_PREFIXES
    TAG_PATTERN = re.compile(r'\[([A-Z]+)_([A-Z0-9_]+)\]')

    # Malformed tag patterns to detect
    MALFORMED_PATTERNS = [
        (re.compile(r'(?<!\[)(CHAR|LOC|PROP|CONCEPT|EVENT|ENV)_[A-Z0-9_]+(?!\])'), "missing_brackets"),
        (re.compile(r'\[([a-z]+)_([a-z0-9_]+)\]'), "lowercase_tag"),
        (re.compile(r'\[([A-Z]+)\]'), "missing_prefix"),  # [MEI] instead of [CHAR_MEI]
    ]

    def __init__(
        self,
        world_config: Dict[str, Any] = None,
        script_content: str = None,
        visual_script_content: str = None,
        strict_mode: bool = False
    ):
        """
        Initialize the context validator.

        Args:
            world_config: World configuration dictionary
            script_content: Script markdown content
            visual_script_content: Visual script content
            strict_mode: If True, warnings are treated as errors
        """
        self.world_config = world_config or {}
        self.script_content = script_content or ""
        self.visual_script_content = visual_script_content or ""
        self.strict_mode = strict_mode

        # Build tag registry from world_config
        self._known_tags: Dict[str, str] = {}  # tag -> entity_type
        self._build_tag_registry()

    def _build_tag_registry(self) -> None:
        """Build registry of known tags from world_config."""
        # Characters
        for char in self.world_config.get("characters", []):
            if tag := char.get("tag"):
                self._known_tags[tag] = "character"

        # Locations
        for loc in self.world_config.get("locations", []):
            if tag := loc.get("tag"):
                self._known_tags[tag] = "location"

        # Props
        for prop in self.world_config.get("props", []):
            if tag := prop.get("tag"):
                self._known_tags[tag] = "prop"

    def validate_all(self) -> ContextValidationResult:
        """
        Run all validation checks.

        Returns:
            ContextValidationResult with all issues found
        """
        result = ContextValidationResult(valid=True)

        # 1. Validate world_config schema
        schema_result = self.validate_world_config_schema()
        result.merge(schema_result)

        # 2. Validate tag format consistency
        format_result = self.validate_tag_formats()
        result.merge(format_result)

        # 3. Validate script references (if script provided)
        if self.script_content:
            script_result = self.validate_script_references()
            result.merge(script_result)

        # 4. Validate visual script references (if provided)
        if self.visual_script_content:
            vs_result = self.validate_visual_script_references()
            result.merge(vs_result)

        # 5. Validate entity relationships
        rel_result = self.validate_entity_relationships()
        result.merge(rel_result)

        # Apply strict mode
        if self.strict_mode and result.warnings > 0:
            result.valid = False

        logger.info(
            f"Context validation complete: {result.entities_validated} entities, "
            f"{result.errors} errors, {result.warnings} warnings"
        )

        return result

    def validate_world_config_schema(self) -> ContextValidationResult:
        """Validate world_config structure and required fields."""
        result = ContextValidationResult(valid=True)

        # Check for required top-level keys
        if not self.world_config:
            result.add_issue(ContextValidationIssue(
                code="EMPTY_WORLD_CONFIG",
                message="World configuration is empty or not loaded",
                level=ValidationLevel.CRITICAL,
                entity_type="config"
            ))
            result.valid = False
            return result

        # Validate characters
        for i, char in enumerate(self.world_config.get("characters", [])):
            result.entities_validated += 1
            char_issues = self._validate_character(char, i)
            for issue in char_issues:
                result.add_issue(issue)

        # Validate locations
        for i, loc in enumerate(self.world_config.get("locations", [])):
            result.entities_validated += 1
            loc_issues = self._validate_location(loc, i)
            for issue in loc_issues:
                result.add_issue(issue)

        # Validate props
        for i, prop in enumerate(self.world_config.get("props", [])):
            result.entities_validated += 1
            prop_issues = self._validate_prop(prop, i)
            for issue in prop_issues:
                result.add_issue(issue)

        if result.errors > 0:
            result.valid = False

        return result

    def _validate_character(self, char: Dict[str, Any], index: int) -> List[ContextValidationIssue]:
        """Validate a character entry."""
        issues = []
        char_id = char.get("tag", f"character[{index}]")

        # Check required fields
        for field in self.REQUIRED_CHARACTER_FIELDS:
            if not char.get(field):
                issues.append(ContextValidationIssue(
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Character missing required field: {field}",
                    level=ValidationLevel.ERROR,
                    entity_type="character",
                    entity_id=char_id,
                    suggestion=f"Add '{field}' field to character definition"
                ))

        # Check tag format
        if tag := char.get("tag"):
            if not tag.startswith("CHAR_"):
                issues.append(ContextValidationIssue(
                    code="INVALID_TAG_PREFIX",
                    message=f"Character tag '{tag}' should start with 'CHAR_'",
                    level=ValidationLevel.ERROR,
                    entity_type="character",
                    entity_id=char_id,
                    suggestion=f"Rename to 'CHAR_{tag}'" if "_" not in tag else f"Ensure prefix is 'CHAR_'",
                    auto_fixable=True,
                    fix_data={"correct_tag": f"CHAR_{tag.replace('CHAR_', '')}"}
                ))
            elif not tag.isupper():
                issues.append(ContextValidationIssue(
                    code="LOWERCASE_TAG",
                    message=f"Character tag '{tag}' should be uppercase",
                    level=ValidationLevel.WARNING,
                    entity_type="character",
                    entity_id=char_id,
                    suggestion=f"Use '{tag.upper()}'",
                    auto_fixable=True,
                    fix_data={"correct_tag": tag.upper()}
                ))

        # Check for duplicate tag
        tag = char.get("tag", "")
        if tag:
            count = sum(1 for c in self.world_config.get("characters", []) if c.get("tag") == tag)
            if count > 1:
                issues.append(ContextValidationIssue(
                    code="DUPLICATE_TAG",
                    message=f"Character tag '{tag}' is used {count} times",
                    level=ValidationLevel.ERROR,
                    entity_type="character",
                    entity_id=char_id,
                    suggestion="Ensure each character has a unique tag"
                ))

        # Validate relationships reference existing characters
        if relationships := char.get("relationships"):
            if isinstance(relationships, dict):
                for rel_tag in relationships.keys():
                    if rel_tag not in self._known_tags:
                        issues.append(ContextValidationIssue(
                            code="UNKNOWN_RELATIONSHIP_TARGET",
                            message=f"Relationship references unknown entity: {rel_tag}",
                            level=ValidationLevel.WARNING,
                            entity_type="character",
                            entity_id=char_id,
                            suggestion=f"Ensure '{rel_tag}' exists in world_config or fix the reference"
                        ))

        return issues

    def _validate_location(self, loc: Dict[str, Any], index: int) -> List[ContextValidationIssue]:
        """Validate a location entry."""
        issues = []
        loc_id = loc.get("tag", f"location[{index}]")

        # Check required fields
        for field in self.REQUIRED_LOCATION_FIELDS:
            if not loc.get(field):
                issues.append(ContextValidationIssue(
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Location missing required field: {field}",
                    level=ValidationLevel.ERROR,
                    entity_type="location",
                    entity_id=loc_id,
                    suggestion=f"Add '{field}' field to location definition"
                ))

        # Check tag format
        if tag := loc.get("tag"):
            if not tag.startswith("LOC_"):
                issues.append(ContextValidationIssue(
                    code="INVALID_TAG_PREFIX",
                    message=f"Location tag '{tag}' should start with 'LOC_'",
                    level=ValidationLevel.ERROR,
                    entity_type="location",
                    entity_id=loc_id,
                    suggestion=f"Rename to 'LOC_{tag}'" if "_" not in tag else f"Ensure prefix is 'LOC_'",
                    auto_fixable=True,
                    fix_data={"correct_tag": f"LOC_{tag.replace('LOC_', '')}"}
                ))

        return issues

    def _validate_prop(self, prop: Dict[str, Any], index: int) -> List[ContextValidationIssue]:
        """Validate a prop entry."""
        issues = []
        prop_id = prop.get("tag", f"prop[{index}]")

        # Check required fields
        for field in self.REQUIRED_PROP_FIELDS:
            if not prop.get(field):
                issues.append(ContextValidationIssue(
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Prop missing required field: {field}",
                    level=ValidationLevel.ERROR,
                    entity_type="prop",
                    entity_id=prop_id,
                    suggestion=f"Add '{field}' field to prop definition"
                ))

        # Check tag format
        if tag := prop.get("tag"):
            if not tag.startswith("PROP_"):
                issues.append(ContextValidationIssue(
                    code="INVALID_TAG_PREFIX",
                    message=f"Prop tag '{tag}' should start with 'PROP_'",
                    level=ValidationLevel.ERROR,
                    entity_type="prop",
                    entity_id=prop_id,
                    suggestion=f"Rename to 'PROP_{tag}'" if "_" not in tag else f"Ensure prefix is 'PROP_'",
                    auto_fixable=True,
                    fix_data={"correct_tag": f"PROP_{tag.replace('PROP_', '')}"}
                ))

        return issues

    def validate_tag_formats(self) -> ContextValidationResult:
        """Validate tag format consistency across all content."""
        result = ContextValidationResult(valid=True)

        # Combine all content to check
        all_content = f"{self.script_content}\n{self.visual_script_content}"

        # Find malformed tags
        for pattern, issue_type in self.MALFORMED_PATTERNS:
            for match in pattern.finditer(all_content):
                bad_tag = match.group(0)

                if issue_type == "missing_brackets":
                    result.add_issue(ContextValidationIssue(
                        code="TAG_MISSING_BRACKETS",
                        message=f"Tag '{bad_tag}' is missing square brackets",
                        level=ValidationLevel.ERROR,
                        suggestion=f"Use '[{bad_tag}]' instead",
                        auto_fixable=True,
                        fix_data={"original": bad_tag, "fixed": f"[{bad_tag}]"}
                    ))

                elif issue_type == "lowercase_tag":
                    result.add_issue(ContextValidationIssue(
                        code="TAG_LOWERCASE",
                        message=f"Tag '{bad_tag}' should be uppercase",
                        level=ValidationLevel.WARNING,
                        suggestion=f"Use '{bad_tag.upper()}' instead",
                        auto_fixable=True,
                        fix_data={"original": bad_tag, "fixed": bad_tag.upper()}
                    ))

                elif issue_type == "missing_prefix":
                    name = match.group(1)
                    result.add_issue(ContextValidationIssue(
                        code="TAG_MISSING_PREFIX",
                        message=f"Tag '[{name}]' is missing category prefix",
                        level=ValidationLevel.WARNING,
                        suggestion=f"Use '[CHAR_{name}]', '[LOC_{name}]', or appropriate prefix",
                        auto_fixable=False  # Can't auto-fix without knowing type
                    ))

        if result.errors > 0:
            result.valid = False

        return result

    def validate_script_references(self) -> ContextValidationResult:
        """Validate that all tags in script exist in world_config."""
        result = ContextValidationResult(valid=True)

        # Extract all tags from script
        tags_in_script = set(self.TAG_PATTERN.findall(self.script_content))

        for prefix, name in tags_in_script:
            full_tag = f"{prefix}_{name}"
            result.entities_validated += 1

            if full_tag not in self._known_tags:
                # Determine expected entity type from prefix
                prefix_to_type = {
                    "CHAR": "character",
                    "LOC": "location",
                    "PROP": "prop",
                    "CONCEPT": "concept",
                    "EVENT": "event",
                    "ENV": "environment"
                }
                expected_type = prefix_to_type.get(prefix, "unknown")

                result.add_issue(ContextValidationIssue(
                    code="UNKNOWN_ENTITY_REFERENCE",
                    message=f"Script references unknown {expected_type}: [{full_tag}]",
                    level=ValidationLevel.WARNING,
                    entity_type="script",
                    entity_id=full_tag,
                    suggestion=f"Add [{full_tag}] to world_config {expected_type}s or fix the reference"
                ))

        return result

    def validate_visual_script_references(self) -> ContextValidationResult:
        """Validate that all tags in visual script exist."""
        result = ContextValidationResult(valid=True)

        # Extract all tags from visual script
        tags_in_vs = set(self.TAG_PATTERN.findall(self.visual_script_content))

        for prefix, name in tags_in_vs:
            full_tag = f"{prefix}_{name}"
            result.entities_validated += 1

            if full_tag not in self._known_tags:
                prefix_to_type = {
                    "CHAR": "character",
                    "LOC": "location",
                    "PROP": "prop"
                }
                expected_type = prefix_to_type.get(prefix, "unknown")

                result.add_issue(ContextValidationIssue(
                    code="UNKNOWN_ENTITY_REFERENCE",
                    message=f"Visual script references unknown {expected_type}: [{full_tag}]",
                    level=ValidationLevel.WARNING,
                    entity_type="visual_script",
                    entity_id=full_tag,
                    suggestion=f"Add [{full_tag}] to world_config or fix the reference"
                ))

        return result

    def validate_entity_relationships(self) -> ContextValidationResult:
        """Validate that entity relationships are bidirectional and consistent."""
        result = ContextValidationResult(valid=True)

        # Build relationship graph
        relationships: Dict[str, Set[str]] = {}

        for char in self.world_config.get("characters", []):
            tag = char.get("tag", "")
            if not tag:
                continue

            char_rels = char.get("relationships", {})
            if isinstance(char_rels, dict):
                relationships[tag] = set(char_rels.keys())
            elif isinstance(char_rels, list):
                relationships[tag] = set(char_rels)
            else:
                relationships[tag] = set()

        # Check for one-way relationships (warning only)
        for char_tag, related_tags in relationships.items():
            for related_tag in related_tags:
                if related_tag in relationships:
                    if char_tag not in relationships.get(related_tag, set()):
                        result.add_issue(ContextValidationIssue(
                            code="ASYMMETRIC_RELATIONSHIP",
                            message=f"[{char_tag}] has relationship to [{related_tag}] but not vice versa",
                            level=ValidationLevel.INFO,
                            entity_type="character",
                            entity_id=char_tag,
                            suggestion=f"Consider adding reciprocal relationship from [{related_tag}] to [{char_tag}]"
                        ))

        return result

    def get_unknown_references(self) -> Dict[str, List[str]]:
        """Get all unknown entity references organized by type."""
        unknown: Dict[str, List[str]] = {
            "characters": [],
            "locations": [],
            "props": [],
            "other": []
        }

        all_content = f"{self.script_content}\n{self.visual_script_content}"
        tags = set(self.TAG_PATTERN.findall(all_content))

        for prefix, name in tags:
            full_tag = f"{prefix}_{name}"
            if full_tag not in self._known_tags:
                if prefix == "CHAR":
                    unknown["characters"].append(full_tag)
                elif prefix == "LOC":
                    unknown["locations"].append(full_tag)
                elif prefix == "PROP":
                    unknown["props"].append(full_tag)
                else:
                    unknown["other"].append(full_tag)

        return unknown

    def auto_fix_tags(self, content: str) -> Tuple[str, int]:
        """
        Auto-fix tag format issues in content.

        Args:
            content: Content to fix

        Returns:
            Tuple of (fixed_content, number_of_fixes)
        """
        fixed = content
        fix_count = 0

        # Fix missing brackets
        pattern = re.compile(r'(?<!\[)(CHAR|LOC|PROP|CONCEPT|EVENT|ENV)_([A-Z0-9_]+)(?!\])')
        for match in pattern.finditer(content):
            bad_tag = match.group(0)
            fixed = fixed.replace(bad_tag, f"[{bad_tag}]")
            fix_count += 1

        # Fix lowercase tags
        pattern = re.compile(r'\[([a-z]+_[a-z0-9_]+)\]')
        for match in pattern.finditer(content):
            bad_tag = match.group(0)
            fixed = fixed.replace(bad_tag, bad_tag.upper())
            fix_count += 1

        return fixed, fix_count


# Convenience functions
def validate_context(
    world_config: Dict[str, Any],
    script: str = "",
    visual_script: str = "",
    strict: bool = False
) -> ContextValidationResult:
    """
    Validate context integrity.

    Args:
        world_config: World configuration dictionary
        script: Optional script content
        visual_script: Optional visual script content
        strict: Treat warnings as errors

    Returns:
        ContextValidationResult
    """
    validator = ContextValidator(
        world_config=world_config,
        script_content=script,
        visual_script_content=visual_script,
        strict_mode=strict
    )
    return validator.validate_all()


def validate_world_config(world_config: Dict[str, Any]) -> ContextValidationResult:
    """Quick validation of world_config structure."""
    validator = ContextValidator(world_config=world_config)
    return validator.validate_world_config_schema()


def find_unknown_references(
    world_config: Dict[str, Any],
    script: str = "",
    visual_script: str = ""
) -> Dict[str, List[str]]:
    """Find all tags referenced but not defined in world_config."""
    validator = ContextValidator(
        world_config=world_config,
        script_content=script,
        visual_script_content=visual_script
    )
    return validator.get_unknown_references()

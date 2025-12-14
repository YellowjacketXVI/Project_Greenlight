"""
Greenlight Tag Validator

Single-agent tag validation with format and registry checks.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict
from enum import Enum

from greenlight.core.constants import TagCategory, TAG_CONSENSUS_THRESHOLD
from greenlight.core.exceptions import TagError
from .tag_parser import TagParser, ParsedTag
from .tag_registry import TagRegistry


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Must fix
    WARNING = "warning"  # Should fix
    INFO = "info"        # Informational


@dataclass
class ValidationIssue:
    """Represents a validation issue found."""
    tag: str
    severity: ValidationSeverity
    message: str
    suggestion: Optional[str] = None
    position: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of tag validation."""
    is_valid: bool
    tags_found: List[ParsedTag]
    valid_tags: List[str]
    invalid_tags: List[str]
    unregistered_tags: List[str]
    issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)


class TagValidator:
    """
    Validates tags in text content against format rules and registry.
    
    Checks:
    - Tag format validity
    - Registry registration
    - Directional tag base existence
    - Category consistency
    """
    
    def __init__(self, registry: TagRegistry):
        """
        Initialize validator with a tag registry.
        
        Args:
            registry: TagRegistry instance for validation
        """
        self.registry = registry
        self.parser = TagParser()
    
    def validate_text(self, text: str) -> ValidationResult:
        """
        Validate all tags in a text.
        
        Args:
            text: Text content to validate
            
        Returns:
            ValidationResult with all findings
        """
        tags = self.parser.parse_text(text)
        issues = []
        valid_tags = []
        invalid_tags = []
        unregistered_tags = []
        
        for tag in tags:
            tag_issues = self._validate_tag(tag)
            issues.extend(tag_issues)
            
            if any(i.severity == ValidationSeverity.ERROR for i in tag_issues):
                invalid_tags.append(tag.name)
            else:
                valid_tags.append(tag.name)
            
            # Check registration
            if not self.registry.exists(tag.name):
                # For directional tags, check base name
                if tag.is_directional and tag.base_name:
                    if not self.registry.exists(tag.base_name):
                        unregistered_tags.append(tag.name)
                else:
                    unregistered_tags.append(tag.name)
        
        is_valid = len(invalid_tags) == 0 and len(unregistered_tags) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            tags_found=tags,
            valid_tags=valid_tags,
            invalid_tags=invalid_tags,
            unregistered_tags=unregistered_tags,
            issues=issues
        )
    
    def _validate_tag(self, tag: ParsedTag) -> List[ValidationIssue]:
        """Validate a single parsed tag."""
        issues = []
        
        # Check format
        if not self.parser.validate_format(tag.name):
            issues.append(ValidationIssue(
                tag=tag.name,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid tag format: {tag.name}",
                suggestion="Tags must start with uppercase letter, contain only A-Z, 0-9, _",
                position=tag.position
            ))
        
        # Check directional tag validity
        if tag.is_directional:
            if not tag.base_name:
                issues.append(ValidationIssue(
                    tag=tag.name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Directional tag missing base name: {tag.name}",
                    position=tag.position
                ))
            elif tag.category != TagCategory.LOCATION:
                issues.append(ValidationIssue(
                    tag=tag.name,
                    severity=ValidationSeverity.WARNING,
                    message=f"Directional suffix on non-location tag: {tag.name}",
                    suggestion="Directional suffixes are typically for locations",
                    position=tag.position
                ))
        
        # Check registry
        if self.registry.exists(tag.name):
            entry = self.registry.get(tag.name)
            # Check category consistency
            if entry.category != tag.category:
                issues.append(ValidationIssue(
                    tag=tag.name,
                    severity=ValidationSeverity.WARNING,
                    message=f"Tag category mismatch: expected {entry.category.value}, inferred {tag.category.value}",
                    position=tag.position
                ))
        else:
            issues.append(ValidationIssue(
                tag=tag.name,
                severity=ValidationSeverity.WARNING,
                message=f"Tag not registered: {tag.name}",
                suggestion="Register this tag in the world bible",
                position=tag.position
            ))
        
        return issues
    
    def validate_tag_list(self, tags: List[str]) -> ValidationResult:
        """
        Validate a list of tag names.
        
        Args:
            tags: List of tag names to validate
            
        Returns:
            ValidationResult
        """
        # Create synthetic text for validation
        text = " ".join(f"[{tag}]" for tag in tags)
        return self.validate_text(text)
    
    def suggest_similar_tags(
        self,
        tag_name: str,
        max_suggestions: int = 3
    ) -> List[str]:
        """
        Suggest similar registered tags for an unregistered tag.
        
        Args:
            tag_name: Unregistered tag name
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of similar registered tag names
        """
        registered = self.registry.get_all_names()
        
        # Simple similarity based on common prefix/suffix
        suggestions = []
        tag_upper = tag_name.upper()
        
        for reg_tag in registered:
            reg_upper = reg_tag.upper()
            # Check prefix match
            if reg_upper.startswith(tag_upper[:3]) or tag_upper.startswith(reg_upper[:3]):
                suggestions.append(reg_tag)
            # Check suffix match
            elif reg_upper.endswith(tag_upper[-3:]) or tag_upper.endswith(reg_upper[-3:]):
                suggestions.append(reg_tag)
        
        return suggestions[:max_suggestions]


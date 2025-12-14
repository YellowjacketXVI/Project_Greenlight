"""
Anchor Agent - Scene.Frame.Camera Notation Enforcer

An agent specifically designed to validate and reinforce the scene.frame.camera
notation system throughout the script.

SCENE-ONLY ARCHITECTURE:
- Scenes are the atomic narrative unit (## Scene N:)
- No beat markers - scenes contain continuous prose
- Director pipeline creates frames from scenes using scene.frame.camera notation

Notation Format: {scene}.{frame}.c{letter}
Examples: 1.1.cA, 1.2.cB, 2.3.cC

Validates:
- Scene markers: ## Scene N:
- Frame chunks: (/scene_frame_chunk_start/) ... (/scene_frame_chunk_end/)
- Camera blocks: [N.N.cX] (shot_type)
- Tag formats: [CHAR_TAG], [LOC_TAG], [PROP_TAG]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple
import re

from greenlight.core.logging_config import get_logger
from greenlight.config.notation_patterns import (
    SCENE_FRAME_CAMERA_PATTERNS,
    REGEX_PATTERNS,
)
from .universal_context import UniversalContext

logger = get_logger("patterns.quality.anchor")


@dataclass
class NotationIssue:
    """An issue with notation formatting."""
    issue_type: str  # scene_marker, camera_block, tag_format, frame_chunk
    location: str  # Where in the script
    line_number: int
    description: str
    current_value: str
    suggested_fix: str


@dataclass
class NotationFix:
    """A fix to apply to the script."""
    line_number: int
    original: str
    replacement: str
    fix_type: str


@dataclass
class NotationReport:
    """Complete notation validation report.

    SCENE-ONLY ARCHITECTURE: No beat_count field.
    """
    original_script: str
    fixed_script: str
    issues_found: List[NotationIssue]
    fixes_applied: List[NotationFix]
    notation_valid: bool
    scene_count: int
    camera_count: int


class AnchorAgent:
    """
    Enforces and validates scene.frame.camera notation throughout the script.

    SCENE-ONLY ARCHITECTURE:
    - Validates scene markers (## Scene N:)
    - No beat marker validation (beats removed from architecture)
    - Validates frame chunks and camera blocks
    - Validates tag formats

    Note: Patterns are imported from greenlight/config/notation_patterns.py
    which is the canonical source for all notation regex patterns.
    """

    # Notation patterns - consolidated from notation_patterns.py
    # This combines patterns from SCENE_FRAME_CAMERA_PATTERNS and REGEX_PATTERNS
    # for AnchorAgent's specific validation needs
    PATTERNS = {
        # Scene markers (from SCENE_FRAME_CAMERA_PATTERNS) - SCENE-ONLY, no beats
        "scene_marker": SCENE_FRAME_CAMERA_PATTERNS["scene_marker"],
        # Frame chunk delimiters (from REGEX_PATTERNS)
        "frame_chunk_start": REGEX_PATTERNS["frame_chunk_start"],
        "frame_chunk_end": REGEX_PATTERNS["frame_chunk_end"],
        # Camera block with shot type (from SCENE_FRAME_CAMERA_PATTERNS)
        "camera_block": SCENE_FRAME_CAMERA_PATTERNS["full_id_with_type"],
        # Tag patterns (from REGEX_PATTERNS)
        "tag_bracketed": REGEX_PATTERNS["tag_bracketed"],
        "tag_char": REGEX_PATTERNS["tag_char"],
        "tag_loc": REGEX_PATTERNS["tag_loc"],
        "tag_prop": REGEX_PATTERNS["tag_prop"],
    }

    def __init__(self, llm_caller: Optional[Callable] = None):
        self.llm_caller = llm_caller
    
    async def enforce_notation(
        self,
        script: str,
        world_config: Dict[str, Any]
    ) -> NotationReport:
        """
        Validate and fix all notation in the script.
        
        Args:
            script: The script text
            world_config: World configuration for tag validation
            
        Returns:
            NotationReport with issues and fixes
        """
        logger.info("AnchorAgent: Validating notation (SCENE-ONLY architecture)...")

        issues = []
        fixes = []

        # Split script into lines for line-by-line analysis
        lines = script.split('\n')

        # 1. Validate scene markers (SCENE-ONLY - no beat validation)
        scene_issues = self._validate_scene_markers(lines)
        issues.extend(scene_issues)

        # 2. Validate tag formats
        tag_issues = self._validate_tag_formats(lines, world_config)
        issues.extend(tag_issues)

        # 3. Validate camera notation (if present)
        camera_issues = self._validate_camera_notation(lines)
        issues.extend(camera_issues)

        # 4. Validate frame chunks
        chunk_issues = self._validate_frame_chunks(lines)
        issues.extend(chunk_issues)

        # 5. Generate fixes for issues
        for issue in issues:
            if issue.suggested_fix:
                fixes.append(NotationFix(
                    line_number=issue.line_number,
                    original=issue.current_value,
                    replacement=issue.suggested_fix,
                    fix_type=issue.issue_type
                ))

        # 6. Apply fixes
        fixed_script = self._apply_fixes(script, fixes)

        # Count notation elements (SCENE-ONLY - no beat count)
        scene_count = len(re.findall(self.PATTERNS['scene_marker'], script))
        camera_count = len(re.findall(self.PATTERNS['camera_block'], script))

        logger.info(f"AnchorAgent: Found {len(issues)} issues, applied {len(fixes)} fixes")

        return NotationReport(
            original_script=script,
            fixed_script=fixed_script,
            issues_found=issues,
            fixes_applied=fixes,
            notation_valid=len(issues) == 0,
            scene_count=scene_count,
            camera_count=camera_count
        )
    
    def _validate_scene_markers(self, lines: List[str]) -> List[NotationIssue]:
        """Validate scene marker format."""
        issues = []
        expected_scene = 1
        
        for i, line in enumerate(lines):
            # Check for scene-like headers
            if line.strip().lower().startswith('## scene'):
                match = re.match(self.PATTERNS['scene_marker'], line.strip())
                if not match:
                    # Malformed scene marker
                    issues.append(NotationIssue(
                        issue_type='scene_marker',
                        location=f"Line {i + 1}",
                        line_number=i + 1,
                        description="Malformed scene marker",
                        current_value=line.strip(),
                        suggested_fix=f"## Scene {expected_scene}:"
                    ))
                else:
                    scene_num = int(match.group(1))
                    if scene_num != expected_scene:
                        issues.append(NotationIssue(
                            issue_type='scene_marker',
                            location=f"Line {i + 1}",
                            line_number=i + 1,
                            description=f"Scene number out of sequence (expected {expected_scene})",
                            current_value=line.strip(),
                            suggested_fix=f"## Scene {expected_scene}:"
                        ))
                    expected_scene = scene_num + 1

        return issues

    # NOTE: _validate_beat_markers() removed - SCENE-ONLY ARCHITECTURE
    # Scenes are the atomic narrative unit, no beat subdivisions

    def _validate_tag_formats(
        self,
        lines: List[str],
        world_config: Dict[str, Any]
    ) -> List[NotationIssue]:
        """Validate all tag references."""
        issues = []

        # Get valid tags from world_config
        valid_tags = set(world_config.get('all_tags', []))
        for char in world_config.get('characters', []):
            if char.get('tag'):
                valid_tags.add(char['tag'])
        for loc in world_config.get('locations', []):
            if loc.get('tag'):
                valid_tags.add(loc['tag'])
        for prop in world_config.get('props', []):
            if prop.get('tag'):
                valid_tags.add(prop['tag'])

        for i, line in enumerate(lines):
            # Find all bracketed tags
            tags = re.findall(self.PATTERNS['tag_bracketed'], line)

            for tag in tags:
                # Check if tag is valid
                if tag not in valid_tags:
                    # Check if it's a known prefix but wrong name
                    if tag.startswith(('CHAR_', 'LOC_', 'PROP_')):
                        suggested = self._find_similar_tag(tag, valid_tags)
                        issues.append(NotationIssue(
                            issue_type='tag_format',
                            location=f"Line {i + 1}",
                            line_number=i + 1,
                            description=f"Tag [{tag}] not found in world_config",
                            current_value=f"[{tag}]",
                            suggested_fix=f"[{suggested}]" if suggested else ""
                        ))

                # Check for lowercase tags
                if tag != tag.upper():
                    issues.append(NotationIssue(
                        issue_type='tag_format',
                        location=f"Line {i + 1}",
                        line_number=i + 1,
                        description=f"Tag [{tag}] should be uppercase",
                        current_value=f"[{tag}]",
                        suggested_fix=f"[{tag.upper()}]"
                    ))

        return issues

    def _validate_camera_notation(self, lines: List[str]) -> List[NotationIssue]:
        """Validate camera block notation."""
        issues = []
        current_scene = 0
        current_frame = 0
        expected_camera = 'A'

        for i, line in enumerate(lines):
            # Track current scene
            scene_match = re.match(self.PATTERNS['scene_marker'], line.strip())
            if scene_match:
                current_scene = int(scene_match.group(1))
                current_frame = 0
                expected_camera = 'A'
                continue

            # Check for camera blocks
            camera_match = re.search(self.PATTERNS['camera_block'], line)
            if camera_match:
                scene_num = int(camera_match.group(1))
                frame_num = int(camera_match.group(2))
                camera_letter = camera_match.group(3)
                shot_type = camera_match.group(4)

                # Validate scene number
                if scene_num != current_scene:
                    issues.append(NotationIssue(
                        issue_type='camera_block',
                        location=f"Line {i + 1}",
                        line_number=i + 1,
                        description=f"Camera scene ({scene_num}) doesn't match current scene ({current_scene})",
                        current_value=camera_match.group(0),
                        suggested_fix=f"[{current_scene}.{frame_num}.c{camera_letter}] ({shot_type})"
                    ))

                # Track frame progression
                if frame_num != current_frame:
                    current_frame = frame_num
                    expected_camera = 'A'

                # Validate camera letter sequence
                if camera_letter != expected_camera:
                    issues.append(NotationIssue(
                        issue_type='camera_block',
                        location=f"Line {i + 1}",
                        line_number=i + 1,
                        description=f"Camera letter out of sequence (expected c{expected_camera})",
                        current_value=camera_match.group(0),
                        suggested_fix=f"[{scene_num}.{frame_num}.c{expected_camera}] ({shot_type})"
                    ))

                expected_camera = chr(ord(expected_camera) + 1)

        return issues

    def _validate_frame_chunks(self, lines: List[str]) -> List[NotationIssue]:
        """Validate frame chunk delimiters."""
        issues = []
        chunk_open = False
        chunk_start_line = 0

        for i, line in enumerate(lines):
            if '(/scene_frame_chunk_start/)' in line:
                if chunk_open:
                    issues.append(NotationIssue(
                        issue_type='frame_chunk',
                        location=f"Line {i + 1}",
                        line_number=i + 1,
                        description=f"Nested chunk start (previous chunk started at line {chunk_start_line})",
                        current_value=line.strip(),
                        suggested_fix="Close previous chunk before starting new one"
                    ))
                chunk_open = True
                chunk_start_line = i + 1

            if '(/scene_frame_chunk_end/)' in line:
                if not chunk_open:
                    issues.append(NotationIssue(
                        issue_type='frame_chunk',
                        location=f"Line {i + 1}",
                        line_number=i + 1,
                        description="Chunk end without matching start",
                        current_value=line.strip(),
                        suggested_fix="Add (/scene_frame_chunk_start/) before this"
                    ))
                chunk_open = False

        # Check for unclosed chunk
        if chunk_open:
            issues.append(NotationIssue(
                issue_type='frame_chunk',
                location=f"Line {chunk_start_line}",
                line_number=chunk_start_line,
                description="Unclosed frame chunk",
                current_value="(/scene_frame_chunk_start/)",
                suggested_fix="Add (/scene_frame_chunk_end/) to close chunk"
            ))

        return issues

    def _find_similar_tag(self, tag: str, valid_tags: set) -> Optional[str]:
        """Find a similar valid tag."""
        tag_lower = tag.lower()

        for valid in valid_tags:
            valid_lower = valid.lower()
            # Check for partial match
            if tag_lower[5:] in valid_lower or valid_lower[5:] in tag_lower:
                return valid

        return None

    def _apply_fixes(self, script: str, fixes: List[NotationFix]) -> str:
        """Apply fixes to the script."""
        if not fixes:
            return script

        lines = script.split('\n')

        # Sort fixes by line number (descending) to avoid offset issues
        sorted_fixes = sorted(fixes, key=lambda f: f.line_number, reverse=True)

        for fix in sorted_fixes:
            line_idx = fix.line_number - 1
            if 0 <= line_idx < len(lines):
                lines[line_idx] = lines[line_idx].replace(fix.original, fix.replacement)

        return '\n'.join(lines)

    def generate_notation_report(self, report: NotationReport) -> str:
        """Generate a human-readable notation report.

        SCENE-ONLY ARCHITECTURE: No beat count in report.
        """
        lines = [
            "=" * 60,
            "NOTATION VALIDATION REPORT (SCENE-ONLY)",
            "=" * 60,
            "",
            f"Valid: {'Yes' if report.notation_valid else 'No'}",
            f"Scenes: {report.scene_count}",
            f"Camera Blocks: {report.camera_count}",
            f"Issues Found: {len(report.issues_found)}",
            f"Fixes Applied: {len(report.fixes_applied)}",
            "",
        ]

        if report.issues_found:
            lines.append("ISSUES:")
            for issue in report.issues_found:
                lines.append(f"  [{issue.issue_type.upper()}] {issue.location}: {issue.description}")
                lines.append(f"    Current: {issue.current_value}")
                if issue.suggested_fix:
                    lines.append(f"    Fix: {issue.suggested_fix}")
            lines.append("")

        return "\n".join(lines)

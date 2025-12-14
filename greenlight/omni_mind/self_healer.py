"""
Self-Healer for Greenlight OmniMind

Implements self-healing protocols that can automatically fix common errors
before escalating to Augment. Saves credits by handling routine issues.

Healing Patterns:
    - Missing directories/files
    - Config key defaults
    - Import path corrections
    - API rate limit backoff
    - Pipeline retry logic
    - UI state recovery

Architecture:
    Error → Pattern Match → Heal Attempt → Verify → Log Result
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.self_healer")


class HealingPattern(Enum):
    """Categories of self-healing patterns."""
    MISSING_DIRECTORY = "missing_directory"
    MISSING_FILE = "missing_file"
    CONFIG_DEFAULT = "config_default"
    IMPORT_FIX = "import_fix"
    API_RETRY = "api_retry"
    PIPELINE_RETRY = "pipeline_retry"
    UI_RESET = "ui_reset"
    CACHE_CLEAR = "cache_clear"
    CONNECTION_RETRY = "connection_retry"
    NOTATION_FIX = "notation_fix"  # Fix scene.frame.camera notation issues
    MISSING_CHARACTER = "missing_character"  # Consensus-approved character missing from world_config
    JSON_PARSE_ERROR = "json_parse_error"  # Malformed JSON in config files
    CONFIG_KEY_MISSING = "config_key_missing"  # Missing required keys in world_config.json
    UI_WIDGET_ERROR = "ui_widget_error"  # Tkinter widget destruction race conditions


class HealResult(Enum):
    """Result of healing attempt."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    DEFERRED = "deferred"


@dataclass
class HealingAction:
    """Record of a healing action."""
    pattern: HealingPattern
    target: str
    result: HealResult
    action_taken: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "target": self.target,
            "result": self.result.value,
            "action_taken": self.action_taken,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "error": self.error
        }


@dataclass
class HealingRule:
    """A rule for pattern matching and healing."""
    pattern: HealingPattern
    name: str
    description: str
    matcher: Callable[[Exception, Dict], bool]
    healer: Callable[[Exception, Dict], HealingAction]
    priority: int = 5  # 1-10, higher = more priority
    enabled: bool = True


class SelfHealer:
    """
    Self-healing system for automatic error recovery.
    
    Features:
    - Pattern-based error matching
    - Automatic fix attempts
    - Retry with backoff
    - Health logging integration
    - Augment escalation for unresolved issues
    """
    
    def __init__(
        self,
        project_path: Optional[Path] = None,
        health_logger: Any = None,
        max_retries: int = 3,
        backoff_base: float = 1.0
    ):
        self.project_path = project_path
        self.health_logger = health_logger
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        
        self._rules: List[HealingRule] = []
        self._history: List[HealingAction] = []
        self._stats: Dict[str, int] = {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "deferred": 0
        }
        
        # Register default rules
        self._register_default_rules()
        
        logger.info("SelfHealer initialized")
    
    def _register_default_rules(self) -> None:
        """Register default healing rules."""
        # Rule: Missing directory
        self.add_rule(HealingRule(
            pattern=HealingPattern.MISSING_DIRECTORY,
            name="Create Missing Directory",
            description="Creates directories that don't exist",
            matcher=self._match_missing_dir,
            healer=self._heal_missing_dir,
            priority=8
        ))
        
        # Rule: Missing file with template
        self.add_rule(HealingRule(
            pattern=HealingPattern.MISSING_FILE,
            name="Create Missing File",
            description="Creates missing files with defaults",
            matcher=self._match_missing_file,
            healer=self._heal_missing_file,
            priority=7
        ))
        
        # Rule: API rate limit
        self.add_rule(HealingRule(
            pattern=HealingPattern.API_RETRY,
            name="API Rate Limit Backoff",
            description="Waits and retries on rate limits",
            matcher=self._match_api_rate_limit,
            healer=self._heal_api_rate_limit,
            priority=9
        ))
        
        # Rule: Connection retry
        self.add_rule(HealingRule(
            pattern=HealingPattern.CONNECTION_RETRY,
            name="Connection Retry",
            description="Retries failed connections",
            matcher=self._match_connection_error,
            healer=self._heal_connection_error,
            priority=8
        ))

        # Rule: Notation fix (scene.frame.camera)
        self.add_rule(HealingRule(
            pattern=HealingPattern.NOTATION_FIX,
            name="Fix Scene.Frame.Camera Notation",
            description="Converts old frame notation to scene.frame.camera format",
            matcher=self._match_notation_error,
            healer=self._heal_notation_error,
            priority=6
        ))

        # Rule: Missing character from consensus
        self.add_rule(HealingRule(
            pattern=HealingPattern.MISSING_CHARACTER,
            name="Fix Missing Consensus Character",
            description="Generates and inserts missing character profiles approved by consensus",
            matcher=self._match_missing_character,
            healer=self._heal_missing_character,
            priority=7
        ))

        # Rule: JSON parse error
        self.add_rule(HealingRule(
            pattern=HealingPattern.JSON_PARSE_ERROR,
            name="Fix Malformed JSON",
            description="Attempts to repair malformed JSON in config files",
            matcher=self._match_json_error,
            healer=self._heal_json_error,
            priority=8
        ))

        # Rule: Missing config keys
        self.add_rule(HealingRule(
            pattern=HealingPattern.CONFIG_KEY_MISSING,
            name="Fix Missing Config Keys",
            description="Adds missing required keys to world_config.json with defaults",
            matcher=self._match_config_key_missing,
            healer=self._heal_config_key_missing,
            priority=7
        ))

        # Rule: UI widget errors (informational - these are cosmetic)
        self.add_rule(HealingRule(
            pattern=HealingPattern.UI_WIDGET_ERROR,
            name="UI Widget Destruction Error",
            description="Logs Tkinter widget destruction race conditions (cosmetic, non-blocking)",
            matcher=self._match_ui_widget_error,
            healer=self._heal_ui_widget_error,
            priority=3  # Low priority - cosmetic only
        ))

    def add_rule(self, rule: HealingRule) -> None:
        """Add a healing rule."""
        self._rules.append(rule)
        # Sort by priority (highest first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"Added healing rule: {rule.name}")

    # ==================== MATCHERS ====================

    def _match_missing_dir(self, error: Exception, context: Dict) -> bool:
        """Match missing directory errors."""
        if isinstance(error, (FileNotFoundError, OSError)):
            msg = str(error).lower()
            return "directory" in msg or "no such file" in msg
        return False

    def _match_missing_file(self, error: Exception, context: Dict) -> bool:
        """Match missing file errors."""
        if isinstance(error, FileNotFoundError):
            path_str = str(error)
            # Check if it's a file (has extension)
            if "'" in path_str:
                path = path_str.split("'")[1]
                return "." in Path(path).name
        return False

    def _match_api_rate_limit(self, error: Exception, context: Dict) -> bool:
        """Match API rate limit errors."""
        msg = str(error).lower()
        return any(term in msg for term in ["rate limit", "429", "too many requests", "quota"])

    def _match_connection_error(self, error: Exception, context: Dict) -> bool:
        """Match connection errors."""
        return isinstance(error, (ConnectionError, TimeoutError)) or \
               "connection" in str(error).lower()

    def _match_notation_error(self, error: Exception, context: Dict) -> bool:
        """Match notation format errors (old frame_X.Y format)."""
        msg = str(error).lower()
        # Match errors related to old notation format
        if any(term in msg for term in ["frame_", "notation", "frame id", "invalid frame"]):
            return True
        # Check context for notation issues
        if context.get("notation_issue"):
            return True
        return False

    def _match_missing_character(self, error: Exception, context: Dict) -> bool:
        """Match missing character errors from consensus validation.

        Detects log warnings about consensus-approved characters missing from world_config.
        """
        msg = str(error).lower()

        # Match specific warning patterns from our diagnostic logging
        warning_patterns = [
            "characters approved by consensus but missing",
            "consensus-approved characters missing from character_arcs",
            "missing character",
            "char_" in msg and "missing" in msg
        ]

        if any(pattern in msg if isinstance(pattern, str) else pattern for pattern in warning_patterns):
            return True

        # Check context for missing character flag
        if context.get("missing_characters"):
            return True

        # Check context for pipeline validation failure
        if context.get("validation_type") == "character" and context.get("missing_tags"):
            return True

        return False

    def _match_json_error(self, error: Exception, context: Dict) -> bool:
        """Match JSON parsing errors."""
        import json
        if isinstance(error, json.JSONDecodeError):
            return True
        msg = str(error).lower()
        return any(term in msg for term in ["json", "decode", "expecting", "unterminated"])

    def _match_config_key_missing(self, error: Exception, context: Dict) -> bool:
        """Match missing config key errors."""
        if isinstance(error, KeyError):
            # Check if it's a world_config key
            key = str(error).strip("'\"")
            required_keys = ["visual_style", "style_notes", "lighting", "vibe", "characters", "locations", "props"]
            return key in required_keys
        msg = str(error).lower()
        return "keyerror" in msg or ("missing" in msg and "key" in msg)

    def _match_ui_widget_error(self, error: Exception, context: Dict) -> bool:
        """Match Tkinter widget destruction errors (cosmetic)."""
        msg = str(error).lower()
        # Match CustomTkinter widget destruction race conditions
        return any(term in msg for term in [
            "invalid command name",
            "_update_dimensions_event",
            "tclerror",
            "!ctkcanvas",
            "!ctkframe",
            "!ctklabel",
            "!ctkbutton"
        ])

    # ==================== HEALERS ====================

    def _heal_missing_dir(self, error: Exception, context: Dict) -> HealingAction:
        """Heal missing directory by creating it."""
        start = time.time()
        target = "unknown"

        try:
            # Extract path from error
            if "'" in str(error):
                target = str(error).split("'")[1]

            path = Path(target)
            if not path.suffix:  # Looks like a directory
                path.mkdir(parents=True, exist_ok=True)
                return HealingAction(
                    pattern=HealingPattern.MISSING_DIRECTORY,
                    target=target,
                    result=HealResult.SUCCESS,
                    action_taken=f"Created directory: {path}",
                    duration_ms=(time.time() - start) * 1000
                )
        except Exception as e:
            return HealingAction(
                pattern=HealingPattern.MISSING_DIRECTORY,
                target=target,
                result=HealResult.FAILED,
                action_taken="Attempted to create directory",
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

        return HealingAction(
            pattern=HealingPattern.MISSING_DIRECTORY,
            target=target,
            result=HealResult.SKIPPED,
            action_taken="Could not determine directory path",
            duration_ms=(time.time() - start) * 1000
        )

    def _heal_missing_file(self, error: Exception, context: Dict) -> HealingAction:
        """Heal missing file - defer to Augment for content."""
        target = str(error).split("'")[1] if "'" in str(error) else "unknown"

        return HealingAction(
            pattern=HealingPattern.MISSING_FILE,
            target=target,
            result=HealResult.DEFERRED,
            action_taken="File content requires Augment to generate"
        )

    def _heal_api_rate_limit(self, error: Exception, context: Dict) -> HealingAction:
        """Heal API rate limit with exponential backoff."""
        start = time.time()
        retry_count = context.get("retry_count", 0)

        if retry_count >= self.max_retries:
            return HealingAction(
                pattern=HealingPattern.API_RETRY,
                target="API",
                result=HealResult.FAILED,
                action_taken=f"Max retries ({self.max_retries}) exceeded",
                duration_ms=(time.time() - start) * 1000
            )

        # Calculate backoff
        wait_time = self.backoff_base * (2 ** retry_count)

        return HealingAction(
            pattern=HealingPattern.API_RETRY,
            target="API",
            result=HealResult.PARTIAL,
            action_taken=f"Waiting {wait_time}s before retry {retry_count + 1}/{self.max_retries}",
            duration_ms=wait_time * 1000
        )

    def _heal_connection_error(self, error: Exception, context: Dict) -> HealingAction:
        """Heal connection error with retry."""
        retry_count = context.get("retry_count", 0)

        if retry_count >= self.max_retries:
            return HealingAction(
                pattern=HealingPattern.CONNECTION_RETRY,
                target="Connection",
                result=HealResult.FAILED,
                action_taken=f"Max retries ({self.max_retries}) exceeded"
            )

        return HealingAction(
            pattern=HealingPattern.CONNECTION_RETRY,
            target="Connection",
            result=HealResult.PARTIAL,
            action_taken=f"Retry {retry_count + 1}/{self.max_retries} scheduled"
        )

    def _heal_notation_error(self, error: Exception, context: Dict) -> HealingAction:
        """Heal notation format errors by converting to scene.frame.camera format.

        Converts old notation formats:
        - {frame_1.2} → [1.2.cA]
        - frame_1.2 → 1.2.cA
        """
        import re
        start = time.time()

        text = context.get("text", "")
        if not text:
            return HealingAction(
                pattern=HealingPattern.NOTATION_FIX,
                target="notation",
                result=HealResult.SKIPPED,
                action_taken="No text provided for notation fix",
                duration_ms=(time.time() - start) * 1000
            )

        # Pattern to find old-style frame markers
        old_pattern = r'\{frame_(\d+)\.(\d+)\}'

        def replace_notation(match):
            scene = match.group(1)
            frame = match.group(2)
            return f"[{scene}.{frame}.cA]"

        fixed_text = re.sub(old_pattern, replace_notation, text)

        # Count replacements
        old_count = len(re.findall(old_pattern, text))

        if old_count > 0:
            context["fixed_text"] = fixed_text
            context["notation_fixes"] = old_count
            return HealingAction(
                pattern=HealingPattern.NOTATION_FIX,
                target="notation",
                result=HealResult.SUCCESS,
                action_taken=f"Converted {old_count} old notation(s) to scene.frame.camera format",
                duration_ms=(time.time() - start) * 1000
            )

        return HealingAction(
            pattern=HealingPattern.NOTATION_FIX,
            target="notation",
            result=HealResult.SKIPPED,
            action_taken="No old notation found to fix",
            duration_ms=(time.time() - start) * 1000
        )

    def _heal_missing_character(self, error: Exception, context: Dict) -> HealingAction:
        """Heal missing character by generating and inserting profile.

        Uses ToolExecutor's fix_missing_characters tool to:
        1. Detect missing consensus-approved characters
        2. Generate profiles using LLM based on story context
        3. Insert profiles into world_config.json
        """
        start = time.time()
        target = "world_config.json"

        try:
            # Get project path from context
            project_path = context.get("project_path")
            if not project_path:
                return HealingAction(
                    pattern=HealingPattern.MISSING_CHARACTER,
                    target=target,
                    result=HealResult.SKIPPED,
                    action_taken="No project path in context",
                    duration_ms=(time.time() - start) * 1000
                )

            # Import and use ToolExecutor
            from greenlight.omni_mind.tool_executor import ToolExecutor

            executor = ToolExecutor(project_path=Path(project_path))

            # First detect missing characters
            detection_result = executor.execute("detect_missing_characters")

            if not detection_result.success:
                return HealingAction(
                    pattern=HealingPattern.MISSING_CHARACTER,
                    target=target,
                    result=HealResult.FAILED,
                    action_taken="Failed to detect missing characters",
                    error=detection_result.error,
                    duration_ms=(time.time() - start) * 1000
                )

            missing_tags = detection_result.result.get("missing_tags", [])

            if not missing_tags:
                return HealingAction(
                    pattern=HealingPattern.MISSING_CHARACTER,
                    target=target,
                    result=HealResult.SKIPPED,
                    action_taken="No missing characters detected",
                    duration_ms=(time.time() - start) * 1000
                )

            # Fix missing characters
            fix_result = executor.execute(
                "fix_missing_characters",
                missing_tags=missing_tags,
                dry_run=False
            )

            if fix_result.success:
                fixed_count = fix_result.result.get("fixed_count", 0)
                fixed_tags = fix_result.result.get("fixed_tags", [])

                logger.info(f"✅ Self-healed {fixed_count} missing character(s): {fixed_tags}")

                return HealingAction(
                    pattern=HealingPattern.MISSING_CHARACTER,
                    target=target,
                    result=HealResult.SUCCESS,
                    action_taken=f"Generated and inserted {fixed_count} character profile(s): {fixed_tags}",
                    duration_ms=(time.time() - start) * 1000
                )
            else:
                return HealingAction(
                    pattern=HealingPattern.MISSING_CHARACTER,
                    target=target,
                    result=HealResult.PARTIAL if fix_result.result.get("fixed_count", 0) > 0 else HealResult.FAILED,
                    action_taken=f"Partial fix: {fix_result.result.get('message', 'Unknown')}",
                    error=str(fix_result.result.get("errors", [])),
                    duration_ms=(time.time() - start) * 1000
                )

        except Exception as e:
            logger.error(f"Error healing missing character: {e}")
            return HealingAction(
                pattern=HealingPattern.MISSING_CHARACTER,
                target=target,
                result=HealResult.FAILED,
                action_taken="Exception during character healing",
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    def _heal_json_error(self, error: Exception, context: Dict) -> HealingAction:
        """Heal malformed JSON by attempting to repair common issues."""
        import json
        import re
        start = time.time()
        target = context.get("file_path", "unknown")

        try:
            content = context.get("content", "")
            if not content:
                return HealingAction(
                    pattern=HealingPattern.JSON_PARSE_ERROR,
                    target=target,
                    result=HealResult.SKIPPED,
                    action_taken="No content provided for JSON repair",
                    duration_ms=(time.time() - start) * 1000
                )

            # Common JSON fixes
            fixed = content
            fixes_applied = []

            # Fix trailing commas before } or ]
            if re.search(r',\s*[}\]]', fixed):
                fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
                fixes_applied.append("removed trailing commas")

            # Fix single quotes to double quotes
            if "'" in fixed and '"' not in fixed:
                fixed = fixed.replace("'", '"')
                fixes_applied.append("converted single to double quotes")

            # Try to parse the fixed content
            try:
                json.loads(fixed)
                context["fixed_content"] = fixed
                return HealingAction(
                    pattern=HealingPattern.JSON_PARSE_ERROR,
                    target=target,
                    result=HealResult.SUCCESS,
                    action_taken=f"Repaired JSON: {', '.join(fixes_applied)}",
                    duration_ms=(time.time() - start) * 1000
                )
            except json.JSONDecodeError:
                return HealingAction(
                    pattern=HealingPattern.JSON_PARSE_ERROR,
                    target=target,
                    result=HealResult.DEFERRED,
                    action_taken="JSON repair failed - requires manual intervention",
                    duration_ms=(time.time() - start) * 1000
                )

        except Exception as e:
            return HealingAction(
                pattern=HealingPattern.JSON_PARSE_ERROR,
                target=target,
                result=HealResult.FAILED,
                action_taken="Exception during JSON repair",
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    def _heal_config_key_missing(self, error: Exception, context: Dict) -> HealingAction:
        """Heal missing config keys by adding defaults."""
        import json
        start = time.time()
        target = "world_config.json"

        # Default values for required keys
        defaults = {
            "visual_style": "live_action",
            "style_notes": "",
            "lighting": "Natural lighting with soft shadows",
            "vibe": "Cinematic, Atmospheric",
            "characters": [],
            "locations": [],
            "props": []
        }

        try:
            project_path = context.get("project_path")
            if not project_path:
                return HealingAction(
                    pattern=HealingPattern.CONFIG_KEY_MISSING,
                    target=target,
                    result=HealResult.SKIPPED,
                    action_taken="No project path in context",
                    duration_ms=(time.time() - start) * 1000
                )

            config_path = Path(project_path) / "world_bible" / "world_config.json"
            if not config_path.exists():
                return HealingAction(
                    pattern=HealingPattern.CONFIG_KEY_MISSING,
                    target=target,
                    result=HealResult.SKIPPED,
                    action_taken="world_config.json not found",
                    duration_ms=(time.time() - start) * 1000
                )

            # Load existing config
            config = json.loads(config_path.read_text(encoding='utf-8'))

            # Find missing key from error
            missing_key = str(error).strip("'\"")
            if missing_key in defaults:
                config[missing_key] = defaults[missing_key]
                config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

                logger.info(f"✅ Added missing key '{missing_key}' with default value")

                return HealingAction(
                    pattern=HealingPattern.CONFIG_KEY_MISSING,
                    target=target,
                    result=HealResult.SUCCESS,
                    action_taken=f"Added missing key '{missing_key}' with default: {defaults[missing_key]}",
                    duration_ms=(time.time() - start) * 1000
                )

            return HealingAction(
                pattern=HealingPattern.CONFIG_KEY_MISSING,
                target=target,
                result=HealResult.SKIPPED,
                action_taken=f"Key '{missing_key}' not in known defaults",
                duration_ms=(time.time() - start) * 1000
            )

        except Exception as e:
            return HealingAction(
                pattern=HealingPattern.CONFIG_KEY_MISSING,
                target=target,
                result=HealResult.FAILED,
                action_taken="Exception during config key healing",
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    def _heal_ui_widget_error(self, error: Exception, context: Dict) -> HealingAction:
        """Handle UI widget destruction errors (cosmetic, non-blocking).

        These errors are caused by CustomTkinter's internal event scheduling
        and cannot be fully prevented. They are logged but don't affect functionality.
        """
        start = time.time()

        # This is informational only - the error is cosmetic
        logger.debug(f"UI widget destruction error (cosmetic): {error}")

        return HealingAction(
            pattern=HealingPattern.UI_WIDGET_ERROR,
            target="UI",
            result=HealResult.SKIPPED,
            action_taken="Tkinter widget destruction race condition (cosmetic, non-blocking). "
                        "This is a known CustomTkinter limitation and does not affect functionality.",
            duration_ms=(time.time() - start) * 1000
        )

    # ==================== MAIN HEALING LOGIC ====================

    def heal(
        self,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> Tuple[HealResult, List[HealingAction]]:
        """
        Attempt to heal an error.

        Args:
            error: The exception to heal
            context: Additional context

        Returns:
            Tuple of (overall result, list of actions taken)
        """
        context = context or {}
        actions = []

        self._stats["attempts"] += 1

        # Find matching rules
        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                if rule.matcher(error, context):
                    logger.info(f"Matched healing rule: {rule.name}")
                    action = rule.healer(error, context)
                    actions.append(action)
                    self._history.append(action)

                    # Log to health logger
                    if self.health_logger:
                        self.health_logger.log_self_heal(
                            action=rule.name,
                            success=action.result == HealResult.SUCCESS,
                            details=action.to_dict()
                        )

                    # If successful, stop trying other rules
                    if action.result == HealResult.SUCCESS:
                        self._stats["successes"] += 1
                        return HealResult.SUCCESS, actions
                    elif action.result == HealResult.DEFERRED:
                        self._stats["deferred"] += 1
            except Exception as e:
                logger.error(f"Error in healing rule {rule.name}: {e}")

        # Determine overall result
        if not actions:
            return HealResult.SKIPPED, actions

        if any(a.result == HealResult.SUCCESS for a in actions):
            return HealResult.SUCCESS, actions
        elif any(a.result == HealResult.PARTIAL for a in actions):
            return HealResult.PARTIAL, actions
        elif any(a.result == HealResult.DEFERRED for a in actions):
            self._stats["deferred"] += 1
            return HealResult.DEFERRED, actions
        else:
            self._stats["failures"] += 1
            return HealResult.FAILED, actions

    async def heal_async(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        retry_fn: Callable = None
    ) -> Tuple[HealResult, Any]:
        """
        Async healing with retry support.

        Args:
            error: The exception to heal
            context: Additional context
            retry_fn: Function to retry after healing

        Returns:
            Tuple of (result, retry_fn result if successful)
        """
        context = context or {}

        result, actions = self.heal(error, context)

        if result == HealResult.PARTIAL and retry_fn:
            # Handle backoff for API/connection retries
            for action in actions:
                if action.pattern in [HealingPattern.API_RETRY, HealingPattern.CONNECTION_RETRY]:
                    wait_time = action.duration_ms / 1000
                    if wait_time > 0:
                        logger.info(f"Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)

                    # Retry
                    retry_count = context.get("retry_count", 0) + 1
                    context["retry_count"] = retry_count

                    try:
                        retry_result = await retry_fn()
                        return HealResult.SUCCESS, retry_result
                    except Exception as retry_error:
                        # Recursive retry
                        return await self.heal_async(retry_error, context, retry_fn)

        return result, None

    def get_stats(self) -> Dict[str, Any]:
        """Get healing statistics."""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successes"] / self._stats["attempts"] * 100
                if self._stats["attempts"] > 0 else 0
            ),
            "rules_count": len(self._rules),
            "history_count": len(self._history)
        }

    def get_history(self, limit: int = 20) -> List[HealingAction]:
        """Get recent healing history."""
        return self._history[-limit:]

    def generate_report(self) -> str:
        """Generate healing report for health log."""
        stats = self.get_stats()

        lines = [
            "# Self-Healing Report",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Statistics",
            f"- Total Attempts: {stats['attempts']}",
            f"- Successes: {stats['successes']}",
            f"- Failures: {stats['failures']}",
            f"- Deferred: {stats['deferred']}",
            f"- Success Rate: {stats['success_rate']:.1f}%",
            "",
            "## Recent Actions"
        ]

        for action in self._history[-10:]:
            icon = "✅" if action.result == HealResult.SUCCESS else "❌"
            lines.append(f"- {icon} [{action.pattern.value}] {action.action_taken}")

        return "\n".join(lines)


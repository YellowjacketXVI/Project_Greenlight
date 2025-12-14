"""
Greenlight Self-Guidance System

Autonomous decision-making and self-guidance using Gemini 2.5 as default,
with user-selectable LLM picker integration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from pathlib import Path
from enum import Enum
import asyncio
import json

from greenlight.core.logging_config import get_logger
from greenlight.llm import GeminiClient, TextResponse
from greenlight.llm.llm_registry import (
    LLM_REGISTRY, LLMInfo, LLMConfig, get_llm_by_id, get_llm_client, list_available_llms
)
from greenlight.utils.file_utils import ensure_directory, read_json, write_json

logger = get_logger("omni_mind.self_guidance")


# =============================================================================
# ENUMS
# =============================================================================

class GuidanceMode(Enum):
    """Self-guidance operating modes."""
    AUTONOMOUS = "autonomous"     # Full autonomous decision making
    SUPERVISED = "supervised"     # Decisions require user approval
    MANUAL = "manual"             # User makes all decisions
    LEARNING = "learning"         # Learning from user corrections


class DecisionType(Enum):
    """Types of decisions the system can make."""
    TASK_PRIORITY = "task_priority"
    RESOURCE_ALLOCATION = "resource_allocation"
    ERROR_RECOVERY = "error_recovery"
    OPTIMIZATION = "optimization"
    WORKFLOW = "workflow"
    CONTENT = "content"


class LLMRole(Enum):
    """Roles for LLM selection."""
    GUIDANCE = "guidance"         # Self-guidance decisions
    ANALYSIS = "analysis"         # Content analysis
    GENERATION = "generation"     # Content generation
    VALIDATION = "validation"     # Validation tasks
    CONSENSUS = "consensus"       # Multi-agent consensus


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Decision:
    """A decision made by the self-guidance system."""
    id: str
    decision_type: DecisionType
    question: str
    options: List[str]
    selected_option: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    llm_used: str
    created_at: datetime = field(default_factory=datetime.now)
    approved: bool = None  # None = pending, True/False = user response
    user_correction: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "decision_type": self.decision_type.value,
            "question": self.question,
            "options": self.options,
            "selected_option": self.selected_option,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "llm_used": self.llm_used,
            "created_at": self.created_at.isoformat(),
            "approved": self.approved,
            "user_correction": self.user_correction
        }


@dataclass
class LLMSelection:
    """User's LLM selection for a role."""
    role: LLMRole
    llm_id: str
    llm_info: LLMInfo = None
    custom_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "llm_id": self.llm_id,
            "custom_params": self.custom_params
        }


@dataclass
class GuidanceConfig:
    """Configuration for self-guidance system."""
    mode: GuidanceMode = GuidanceMode.SUPERVISED
    default_llm: str = "gemini-flash"  # Gemini 2.5 Flash as default
    confidence_threshold: float = 0.8  # Auto-approve above this
    max_retries: int = 3
    learning_enabled: bool = True
    llm_selections: Dict[str, LLMSelection] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "default_llm": self.default_llm,
            "confidence_threshold": self.confidence_threshold,
            "max_retries": self.max_retries,
            "learning_enabled": self.learning_enabled,
            "llm_selections": {k: v.to_dict() for k, v in self.llm_selections.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuidanceConfig":
        config = cls(
            mode=GuidanceMode(data.get("mode", "supervised")),
            default_llm=data.get("default_llm", "gemini-flash"),
            confidence_threshold=data.get("confidence_threshold", 0.8),
            max_retries=data.get("max_retries", 3),
            learning_enabled=data.get("learning_enabled", True)
        )
        for role_str, sel_data in data.get("llm_selections", {}).items():
            role = LLMRole(role_str)
            config.llm_selections[role_str] = LLMSelection(
                role=role,
                llm_id=sel_data["llm_id"],
                custom_params=sel_data.get("custom_params", {})
            )
        return config


# =============================================================================
# LLM PICKER
# =============================================================================

class LLMPicker:
    """
    User-selectable LLM picker for role-based model selection.

    Maps roles to specific LLMs, with Gemini 2.5 Flash as default.
    """

    # Default LLM assignments by role
    DEFAULT_ASSIGNMENTS = {
        LLMRole.GUIDANCE: "gemini-flash",      # Gemini 2.5 Flash for guidance
        LLMRole.ANALYSIS: "gemini-flash",      # Gemini 2.5 Flash for analysis
        LLMRole.GENERATION: "claude-sonnet",   # Claude Sonnet for generation
        LLMRole.VALIDATION: "claude-haiku",    # Claude Haiku for validation
        LLMRole.CONSENSUS: "claude-haiku",     # Claude Haiku for consensus (cost efficient)
    }

    def __init__(self, config: GuidanceConfig = None):
        """
        Initialize LLM Picker.

        Args:
            config: Guidance configuration with LLM selections
        """
        self.config = config or GuidanceConfig()
        self._selections: Dict[LLMRole, LLMSelection] = {}
        self._clients: Dict[str, Any] = {}

        # Initialize with defaults
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default LLM assignments."""
        for role, llm_id in self.DEFAULT_ASSIGNMENTS.items():
            if role.value not in self.config.llm_selections:
                llm_info = get_llm_by_id(llm_id)
                if llm_info:
                    self._selections[role] = LLMSelection(
                        role=role,
                        llm_id=llm_id,
                        llm_info=llm_info
                    )
            else:
                sel = self.config.llm_selections[role.value]
                sel.llm_info = get_llm_by_id(sel.llm_id)
                self._selections[role] = sel

    def get_available_llms(self) -> List[LLMInfo]:
        """Get list of available LLMs."""
        return list_available_llms()

    def get_llm_for_role(self, role: LLMRole) -> Optional[LLMInfo]:
        """Get the LLM assigned to a role."""
        selection = self._selections.get(role)
        if selection:
            return selection.llm_info
        return None

    def set_llm_for_role(self, role: LLMRole, llm_id: str, **custom_params) -> bool:
        """
        Set the LLM for a specific role.

        Args:
            role: The role to assign
            llm_id: LLM identifier from registry
            **custom_params: Custom parameters for this assignment

        Returns:
            True if successful
        """
        llm_info = get_llm_by_id(llm_id)
        if not llm_info:
            logger.warning(f"LLM not found: {llm_id}")
            return False

        self._selections[role] = LLMSelection(
            role=role,
            llm_id=llm_id,
            llm_info=llm_info,
            custom_params=custom_params
        )

        # Update config
        self.config.llm_selections[role.value] = self._selections[role]

        logger.info(f"Set {role.value} LLM to {llm_id}")
        return True

    def get_client_for_role(self, role: LLMRole) -> Any:
        """Get an API client for the role's LLM."""
        selection = self._selections.get(role)
        if not selection or not selection.llm_info:
            # Fall back to default
            llm_id = self.config.default_llm
            llm_info = get_llm_by_id(llm_id)
        else:
            llm_id = selection.llm_id
            llm_info = selection.llm_info

        # Cache clients
        if llm_id not in self._clients:
            config = LLMConfig.from_llm_info(llm_info)
            self._clients[llm_id] = get_llm_client(config)

        return self._clients[llm_id]

    def get_assignments(self) -> Dict[str, str]:
        """Get current role-to-LLM assignments."""
        return {
            role.value: sel.llm_id
            for role, sel in self._selections.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize picker state."""
        return {
            "default_llm": self.config.default_llm,
            "assignments": self.get_assignments(),
            "available_llms": [llm.id for llm in self.get_available_llms()]
        }


# =============================================================================
# SELF-GUIDANCE SYSTEM
# =============================================================================

class SelfGuidance:
    """
    Self-Guidance System for autonomous decision-making.

    Uses Gemini 2.5 Flash as default for guidance decisions,
    with user-selectable LLM picker for role-based model selection.

    Features:
    - Autonomous decision making with confidence scoring
    - User approval workflow for supervised mode
    - Learning from user corrections
    - Role-based LLM selection
    - Decision history and analytics
    """

    VERSION = "0.1.0"

    # System prompt for guidance decisions
    GUIDANCE_PROMPT = """You are an AI guidance system for Project Greenlight, a cinematic storyboard generation platform.

Your role is to make intelligent decisions about:
- Task prioritization and scheduling
- Resource allocation
- Error recovery strategies
- Workflow optimization
- Content generation approaches

When making a decision:
1. Analyze the context carefully
2. Consider all available options
3. Select the best option with clear reasoning
4. Provide a confidence score (0.0 to 1.0)

Respond in JSON format:
{
    "selected_option": "option text",
    "confidence": 0.85,
    "reasoning": "Clear explanation of why this option was chosen"
}
"""

    def __init__(
        self,
        project_path: Path = None,
        config: GuidanceConfig = None
    ):
        """
        Initialize Self-Guidance System.

        Args:
            project_path: Project root path
            config: Guidance configuration
        """
        self.project_path = project_path
        self.config = config or GuidanceConfig()

        # Components
        self.llm_picker = LLMPicker(self.config)

        # State
        self._decisions: List[Decision] = []
        self._pending_approvals: List[Decision] = []
        self._next_decision_id = 0
        self._learning_data: List[Dict] = []

        # Storage
        if project_path:
            self.guidance_dir = project_path / ".guidance"
            ensure_directory(self.guidance_dir)
            self.decisions_file = self.guidance_dir / "decisions.json"
            self.config_file = self.guidance_dir / "config.json"
            self._load_state()
        else:
            self.guidance_dir = None

    def _load_state(self) -> None:
        """Load saved state."""
        if self.config_file and self.config_file.exists():
            try:
                data = read_json(self.config_file)
                self.config = GuidanceConfig.from_dict(data)
                self.llm_picker = LLMPicker(self.config)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        if self.guidance_dir:
            try:
                write_json(self.config_file, self.config.to_dict())
                write_json(self.decisions_file, {
                    "next_id": self._next_decision_id,
                    "decisions": [d.to_dict() for d in self._decisions[-100:]]
                })
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

    # =========================================================================
    # DECISION MAKING
    # =========================================================================

    async def make_decision(
        self,
        decision_type: DecisionType,
        question: str,
        options: List[str],
        context: str = None
    ) -> Decision:
        """
        Make a decision using the guidance LLM.

        Args:
            decision_type: Type of decision
            question: The question to decide
            options: Available options
            context: Additional context

        Returns:
            Decision object
        """
        self._next_decision_id += 1
        decision_id = f"decision_{self._next_decision_id:06d}"

        # Get guidance LLM client
        client = self.llm_picker.get_client_for_role(LLMRole.GUIDANCE)
        llm_info = self.llm_picker.get_llm_for_role(LLMRole.GUIDANCE)
        llm_name = llm_info.id if llm_info else self.config.default_llm

        # Build prompt
        prompt = self._build_decision_prompt(question, options, context)

        try:
            # Call LLM
            response = client.generate_text(prompt, temperature=0.3)
            result = self._parse_decision_response(response.text)

            decision = Decision(
                id=decision_id,
                decision_type=decision_type,
                question=question,
                options=options,
                selected_option=result["selected_option"],
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                llm_used=llm_name
            )

        except Exception as e:
            logger.error(f"Decision failed: {e}")
            # Fallback to first option
            decision = Decision(
                id=decision_id,
                decision_type=decision_type,
                question=question,
                options=options,
                selected_option=options[0] if options else "",
                confidence=0.0,
                reasoning=f"Fallback due to error: {e}",
                llm_used=llm_name
            )

        # Handle based on mode
        await self._handle_decision(decision)

        self._decisions.append(decision)
        self._save_state()

        return decision

    def _build_decision_prompt(
        self,
        question: str,
        options: List[str],
        context: str = None
    ) -> str:
        """Build the decision prompt."""
        prompt = self.GUIDANCE_PROMPT + "\n\n"

        if context:
            prompt += f"Context:\n{context}\n\n"

        prompt += f"Question: {question}\n\n"
        prompt += "Options:\n"
        for i, opt in enumerate(options, 1):
            prompt += f"{i}. {opt}\n"

        prompt += "\nMake your decision:"
        return prompt

    def _parse_decision_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM decision response."""
        try:
            # Try to extract JSON
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass

        # Fallback parsing
        return {
            "selected_option": response.strip()[:100],
            "confidence": 0.5,
            "reasoning": "Could not parse structured response"
        }

    async def _handle_decision(self, decision: Decision) -> None:
        """Handle decision based on mode."""
        if self.config.mode == GuidanceMode.AUTONOMOUS:
            decision.approved = True
        elif self.config.mode == GuidanceMode.SUPERVISED:
            if decision.confidence >= self.config.confidence_threshold:
                decision.approved = True
            else:
                self._pending_approvals.append(decision)
        elif self.config.mode == GuidanceMode.MANUAL:
            self._pending_approvals.append(decision)

    # =========================================================================
    # USER INTERACTION
    # =========================================================================

    def get_pending_approvals(self) -> List[Decision]:
        """Get decisions pending user approval."""
        return self._pending_approvals.copy()

    def approve_decision(self, decision_id: str) -> bool:
        """Approve a pending decision."""
        for decision in self._pending_approvals:
            if decision.id == decision_id:
                decision.approved = True
                self._pending_approvals.remove(decision)
                self._save_state()
                return True
        return False

    def reject_decision(self, decision_id: str, correction: str = None) -> bool:
        """Reject a decision with optional correction."""
        for decision in self._pending_approvals:
            if decision.id == decision_id:
                decision.approved = False
                decision.user_correction = correction
                self._pending_approvals.remove(decision)

                # Learn from correction
                if correction and self.config.learning_enabled:
                    self._learn_from_correction(decision)

                self._save_state()
                return True
        return False

    def _learn_from_correction(self, decision: Decision) -> None:
        """Learn from user correction."""
        self._learning_data.append({
            "question": decision.question,
            "wrong_answer": decision.selected_option,
            "correct_answer": decision.user_correction,
            "decision_type": decision.decision_type.value,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"Learned from correction: {decision.id}")

    # =========================================================================
    # LLM PICKER INTERFACE
    # =========================================================================

    def set_llm(self, role: str, llm_id: str, **params) -> bool:
        """Set LLM for a role (user interface)."""
        try:
            role_enum = LLMRole(role)
            return self.llm_picker.set_llm_for_role(role_enum, llm_id, **params)
        except ValueError:
            logger.error(f"Invalid role: {role}")
            return False

    def get_llm_assignments(self) -> Dict[str, str]:
        """Get current LLM assignments."""
        return self.llm_picker.get_assignments()

    def list_available_llms(self) -> List[Dict[str, Any]]:
        """List available LLMs for picker UI."""
        return [
            {
                "id": llm.id,
                "name": llm.name,
                "provider": llm.provider,
                "description": llm.description,
                "capabilities": llm.capabilities
            }
            for llm in self.llm_picker.get_available_llms()
        ]

    # =========================================================================
    # MODE CONTROL
    # =========================================================================

    def set_mode(self, mode: str) -> None:
        """Set guidance mode."""
        self.config.mode = GuidanceMode(mode)
        self._save_state()
        logger.info(f"Guidance mode set to: {mode}")

    def get_mode(self) -> str:
        """Get current guidance mode."""
        return self.config.mode.value

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics."""
        total = len(self._decisions)
        approved = len([d for d in self._decisions if d.approved == True])
        rejected = len([d for d in self._decisions if d.approved == False])
        pending = len(self._pending_approvals)

        avg_confidence = 0.0
        if total > 0:
            avg_confidence = sum(d.confidence for d in self._decisions) / total

        return {
            "total_decisions": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "average_confidence": round(avg_confidence, 3),
            "learning_samples": len(self._learning_data),
            "mode": self.config.mode.value,
            "default_llm": self.config.default_llm
        }


"""
User Journey Walkthrough System

Interactive step-by-step guidance through pipeline phases with user input hooks.
Allows users to insert inputs while processes are happening at each phase.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from greenlight.ui.theme import theme


class JourneyPhase(Enum):
    """Pipeline journey phases."""
    PITCH = "pitch"
    WORLD_BUILDING = "world_building"
    STORY_STRUCTURE = "story_structure"
    BEATS = "beats"
    SHOTS = "shots"
    DIRECTING = "directing"
    STORYBOARD = "storyboard"
    GENERATION = "generation"


@dataclass
class PhaseConfig:
    """Configuration for a journey phase."""
    name: str
    description: str
    icon: str
    input_prompt: str
    allows_input: bool = True
    can_reiterate: bool = True
    required_fields: List[str] = field(default_factory=list)


# Phase configurations
PHASE_CONFIGS: Dict[JourneyPhase, PhaseConfig] = {
    JourneyPhase.PITCH: PhaseConfig(
        name="Pitch",
        description="Define your story concept and logline",
        icon="📝",
        input_prompt="Enter your story pitch or modify the current one:",
        required_fields=["logline", "genre"]
    ),
    JourneyPhase.WORLD_BUILDING: PhaseConfig(
        name="World Building",
        description="Create characters, locations, and props",
        icon="🌍",
        input_prompt="Add or modify world elements:",
        required_fields=["characters", "locations"]
    ),
    JourneyPhase.STORY_STRUCTURE: PhaseConfig(
        name="Story Structure",
        description="Define acts and story arc",
        icon="📊",
        input_prompt="Adjust story structure:",
    ),
    JourneyPhase.BEATS: PhaseConfig(
        name="Scene Beats",
        description="Break down scenes into beats",
        icon="🎭",
        input_prompt="Modify scene beats:",
    ),
    JourneyPhase.SHOTS: PhaseConfig(
        name="Shot List",
        description="Define camera shots for each beat",
        icon="🎬",
        input_prompt="Adjust shot descriptions:",
    ),
    JourneyPhase.DIRECTING: PhaseConfig(
        name="Directing",
        description="Generate visual prompts for each shot",
        icon="🎥",
        input_prompt="Refine visual direction:",
    ),
    JourneyPhase.STORYBOARD: PhaseConfig(
        name="Storyboard",
        description="Review and edit storyboard prompts",
        icon="🖼️",
        input_prompt="Edit storyboard prompts:",
    ),
    JourneyPhase.GENERATION: PhaseConfig(
        name="Generation",
        description="Generate storyboard images",
        icon="🎨",
        input_prompt="Adjust generation settings:",
        can_reiterate=False
    ),
}


@dataclass
class JourneyStep:
    """A step in the user journey."""
    phase: JourneyPhase
    status: str = "pending"  # pending, active, complete, skipped
    user_input: Optional[str] = None
    output: Optional[Dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    epoch: int = 1  # Iteration count


class UserJourneyPanel(ctk.CTkFrame):
    """
    User Journey walkthrough panel.
    
    Shows current phase, allows user input, and tracks progress.
    """
    
    def __init__(
        self,
        master,
        on_input: Callable[[JourneyPhase, str], None] = None,
        on_reiterate: Callable[[JourneyPhase], None] = None,
        on_skip: Callable[[JourneyPhase], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.on_input = on_input
        self.on_reiterate = on_reiterate
        self.on_skip = on_skip
        
        self._steps: Dict[JourneyPhase, JourneyStep] = {}
        self._current_phase: Optional[JourneyPhase] = None
        self._is_processing = False
        
        self._setup_ui()
        self._initialize_steps()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_medium,
            corner_radius=8
        )
        
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_dark, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        title = ctk.CTkLabel(
            header,
            text="🚀 User Journey",
            font=(theme.fonts.family, theme.fonts.size_large, "bold"),
            text_color=theme.colors.text_primary
        )
        title.pack(side="left", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # Phase indicator
        self.phase_label = ctk.CTkLabel(
            header,
            text="Phase: Not Started",
            text_color=theme.colors.text_secondary
        )
        self.phase_label.pack(side="right", padx=theme.spacing.md)

        # Progress steps (horizontal)
        self.steps_frame = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.steps_frame.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.sm)
        self.steps_frame.pack_propagate(False)

        self._step_indicators: Dict[JourneyPhase, ctk.CTkButton] = {}

        # Current phase content
        self.content_frame = ctk.CTkFrame(self, fg_color=theme.colors.bg_light)
        self.content_frame.pack(fill="both", expand=True, padx=theme.spacing.sm, pady=theme.spacing.sm)

        # Phase description
        self.desc_label = ctk.CTkLabel(
            self.content_frame,
            text="Select a project to begin your journey",
            wraplength=350,
            text_color=theme.colors.text_secondary
        )
        self.desc_label.pack(pady=theme.spacing.md)

        # User input area
        self.input_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        self.input_label = ctk.CTkLabel(
            self.input_frame,
            text="Your input:",
            text_color=theme.colors.text_secondary
        )
        self.input_label.pack(anchor="w")

        self.input_text = ctk.CTkTextbox(
            self.input_frame,
            height=80,
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary
        )
        self.input_text.pack(fill="x", pady=theme.spacing.xs)

        # Action buttons
        self.action_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)

        self.submit_btn = ctk.CTkButton(
            self.action_frame,
            text="✓ Submit Input",
            command=self._submit_input,
            fg_color=theme.colors.success,
            hover_color="#388e3c"
        )
        self.submit_btn.pack(side="left", padx=theme.spacing.xs)

        self.reiterate_btn = ctk.CTkButton(
            self.action_frame,
            text="🔄 Reiterate",
            command=self._reiterate_phase,
            fg_color=theme.colors.warning,
            hover_color="#e68a00"
        )
        self.reiterate_btn.pack(side="left", padx=theme.spacing.xs)

        self.skip_btn = ctk.CTkButton(
            self.action_frame,
            text="⏭️ Skip",
            command=self._skip_phase,
            fg_color=theme.colors.bg_hover,
            hover_color=theme.colors.bg_light
        )
        self.skip_btn.pack(side="left", padx=theme.spacing.xs)

        # Epoch indicator
        self.epoch_label = ctk.CTkLabel(
            self.action_frame,
            text="Epoch: 1",
            text_color=theme.colors.text_muted
        )
        self.epoch_label.pack(side="right", padx=theme.spacing.md)

    def _initialize_steps(self) -> None:
        """Initialize journey steps."""
        for phase in JourneyPhase:
            self._steps[phase] = JourneyStep(phase=phase)

            # Create step indicator button
            config = PHASE_CONFIGS[phase]
            btn = ctk.CTkButton(
                self.steps_frame,
                text=config.icon,
                width=35,
                height=35,
                fg_color=theme.colors.bg_dark,
                hover_color=theme.colors.bg_hover,
                command=lambda p=phase: self._on_step_click(p)
            )
            btn.pack(side="left", padx=2)
            self._step_indicators[phase] = btn

    def set_phase(self, phase: JourneyPhase) -> None:
        """Set the current active phase."""
        self._current_phase = phase
        config = PHASE_CONFIGS[phase]
        step = self._steps[phase]

        # Update header
        self.phase_label.configure(text=f"Phase: {config.name}")

        # Update description
        self.desc_label.configure(text=f"{config.icon} {config.description}")

        # Update input prompt
        self.input_label.configure(text=config.input_prompt)

        # Update epoch
        self.epoch_label.configure(text=f"Epoch: {step.epoch}")

        # Update step indicators
        for p, btn in self._step_indicators.items():
            s = self._steps[p]
            if p == phase:
                btn.configure(fg_color=theme.colors.primary)
            elif s.status == "complete":
                btn.configure(fg_color=theme.colors.success)
            elif s.status == "skipped":
                btn.configure(fg_color=theme.colors.text_muted)
            else:
                btn.configure(fg_color=theme.colors.bg_dark)

        # Update button states
        self.reiterate_btn.configure(state="normal" if config.can_reiterate else "disabled")

        # Mark as active
        step.status = "active"
        step.started_at = datetime.now()

    def complete_phase(self, phase: JourneyPhase, output: Dict = None) -> None:
        """Mark a phase as complete."""
        step = self._steps[phase]
        step.status = "complete"
        step.completed_at = datetime.now()
        step.output = output

        # Update indicator
        self._step_indicators[phase].configure(fg_color=theme.colors.success)

    def set_processing(self, is_processing: bool) -> None:
        """Set processing state."""
        self._is_processing = is_processing
        state = "disabled" if is_processing else "normal"
        self.submit_btn.configure(state=state)
        self.reiterate_btn.configure(state=state)
        self.skip_btn.configure(state=state)

    def _submit_input(self) -> None:
        """Submit user input for current phase."""
        if not self._current_phase or self._is_processing:
            return

        user_input = self.input_text.get("1.0", "end-1c").strip()
        if user_input and self.on_input:
            self._steps[self._current_phase].user_input = user_input
            self.on_input(self._current_phase, user_input)
            self.input_text.delete("1.0", "end")

    def _reiterate_phase(self) -> None:
        """Reiterate the current phase with new epoch."""
        if not self._current_phase or self._is_processing:
            return

        step = self._steps[self._current_phase]
        step.epoch += 1
        self.epoch_label.configure(text=f"Epoch: {step.epoch}")

        if self.on_reiterate:
            self.on_reiterate(self._current_phase)

    def _skip_phase(self) -> None:
        """Skip the current phase."""
        if not self._current_phase or self._is_processing:
            return

        step = self._steps[self._current_phase]
        step.status = "skipped"
        self._step_indicators[self._current_phase].configure(fg_color=theme.colors.text_muted)

        if self.on_skip:
            self.on_skip(self._current_phase)

    def _on_step_click(self, phase: JourneyPhase) -> None:
        """Handle click on a step indicator."""
        step = self._steps[phase]
        if step.status in ["complete", "active"]:
            self.set_phase(phase)

    def get_user_inputs(self) -> Dict[JourneyPhase, str]:
        """Get all user inputs."""
        return {p: s.user_input for p, s in self._steps.items() if s.user_input}


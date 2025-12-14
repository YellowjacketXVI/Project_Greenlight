"""
Greenlight Agent Context Delivery

Prepares context packets for specific agent types in Story Pipeline v3.0.
Each agent type receives only the context it needs, minimizing token usage.

Agent Types:
- Brainstorm: story_seed + all character cards + philosophy
- Judge: story_seed + all concepts for ranking
- Outline: story_seed + winning concept + steal list + all cards
- Prose: story_seed + scene cards + thread tracker + scene goal
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path

from greenlight.core.logging_config import get_logger
from greenlight.utils.unicode_utils import count_tokens_estimate

from .context_compiler import ContextCompiler
from .thread_tracker import ThreadTracker

logger = get_logger("context.agent_delivery")


@dataclass
class SceneOutline:
    """Scene-level outline (NO beat breakdown)."""
    
    scene_number: int
    location: str  # Entity tag
    characters: List[str]  # Entity tags
    goal: str  # 1 sentence
    key_moment: str  # 1 sentence
    entry_states: Dict[str, str] = field(default_factory=dict)  # tag: emotional state
    exit_states: Dict[str, str] = field(default_factory=dict)
    tension: int = 5  # 1-10
    steal_elements: List[str] = field(default_factory=list)  # Which steal list items apply
    
    def to_context(self) -> str:
        """Format scene outline for prompt."""
        parts = [
            f"SCENE {self.scene_number}:",
            f"LOCATION: {self.location}",
            f"CHARACTERS: {', '.join(self.characters)}",
            f"GOAL: {self.goal}",
            f"KEY MOMENT: {self.key_moment}",
            f"TENSION: {self.tension}/10"
        ]
        
        if self.entry_states:
            entries = [f"{k}: {v}" for k, v in self.entry_states.items()]
            parts.append(f"ENTERING: {', '.join(entries)}")
        
        if self.exit_states:
            exits = [f"{k}: {v}" for k, v in self.exit_states.items()]
            parts.append(f"EXITING: {', '.join(exits)}")
        
        if self.steal_elements:
            parts.append(f"MUST INCLUDE: {', '.join(self.steal_elements)}")
        
        return '\n'.join(parts)


@dataclass
class AgentContextDelivery:
    """
    Prepares context packets for specific agent types.
    
    Uses ContextCompiler for cached cards and ThreadTracker for continuity.
    Target: ~250 words per agent call.
    """
    
    compiler: ContextCompiler
    tracker: ThreadTracker = field(default_factory=ThreadTracker)
    
    def for_brainstorm_agent(
        self,
        philosophy: str,
        focus: str
    ) -> str:
        """
        Prepare context for a brainstorm agent.
        
        Args:
            philosophy: Agent's storytelling philosophy (e.g., "Character-first")
            focus: What this philosophy focuses on
            
        Returns:
            Context string (~200 words)
        """
        parts = [
            "=== STORY SEED ===",
            self.compiler.get_story_seed(),
            "",
            "=== CHARACTERS ===",
            self.compiler.get_all_character_cards(),
            "",
            f"=== YOUR PHILOSOPHY: {philosophy} ===",
            f"Focus on: {focus}",
            "",
            "Generate a 150-200 word story concept pitch based on this philosophy.",
            "Be specific about character arcs, key moments, and emotional journey."
        ]
        
        context = '\n'.join(parts)
        logger.debug(f"Brainstorm context: {count_tokens_estimate(context)} tokens")
        return context
    
    def for_judge_agent(
        self,
        concepts: List[str],
        concept_labels: List[str] = None
    ) -> str:
        """
        Prepare context for a judge agent.
        
        Args:
            concepts: List of story concepts to judge
            concept_labels: Labels for concepts (A, B, C, D, E)
            
        Returns:
            Context string (~1100 words for 5 concepts)
        """
        if concept_labels is None:
            concept_labels = [chr(65 + i) for i in range(len(concepts))]  # A, B, C...
        
        parts = [
            "=== STORY SEED ===",
            self.compiler.get_story_seed(),
            "",
            "=== CONCEPTS TO JUDGE ==="
        ]
        
        for label, concept in zip(concept_labels, concepts):
            parts.append(f"\n--- CONCEPT {label} ---")
            parts.append(concept)
        
        parts.extend([
            "",
            "=== JUDGING CRITERIA ===",
            "Rank concepts 1-5 (1=best) based on:",
            "- Emotional resonance: Will audience feel something?",
            "- Narrative clarity: Is the through-line clear?",
            "- Specificity: Does it feel unique to THIS story?",
            "",
            "Also identify 1-2 specific elements to STEAL from non-winning concepts.",
            "",
            "FORMAT:",
            "RANK_1: [letter]",
            "RANK_2: [letter]",
            "RANK_3: [letter]",
            "RANK_4: [letter]",
            "RANK_5: [letter]",
            'STEAL: [letter]: "[exact element to steal]"',
            'STEAL: [letter]: "[exact element to steal]"'
        ])
        
        context = '\n'.join(parts)
        logger.debug(f"Judge context: {count_tokens_estimate(context)} tokens")
        return context

    def for_outline_agent(
        self,
        winning_concept: str,
        steal_list: List[str]
    ) -> str:
        """
        Prepare context for the scene outline agent.

        Args:
            winning_concept: The selected story concept
            steal_list: Elements to incorporate from other concepts

        Returns:
            Context string (~350 words)
        """
        parts = [
            "=== STORY SEED ===",
            self.compiler.get_story_seed(),
            "",
            "=== WINNING CONCEPT ===",
            winning_concept,
            ""
        ]

        if steal_list:
            parts.extend([
                "=== MUST INCLUDE (from other concepts) ===",
                '\n'.join(f"- {item}" for item in steal_list),
                ""
            ])

        parts.extend([
            "=== CHARACTERS ===",
            self.compiler.get_all_character_cards(),
            "",
            "=== LOCATIONS ===",
            self.compiler.get_all_location_cards(),
            "",
            "=== TASK ===",
            "Create a scene-by-scene outline. For each scene provide:",
            "",
            "SCENE [N]:",
            "LOCATION: [entity tag from world_config]",
            "CHARACTERS: [entity tags]",
            "GOAL: [what must happen - 1 sentence]",
            "KEY_MOMENT: [single most important narrative moment - 1 sentence]",
            "ENTRY_STATES: [character: emotional state entering]",
            "EXIT_STATES: [character: emotional state exiting]",
            "TENSION: [1-10]",
            "",
            "Incorporate the MUST INCLUDE elements naturally.",
            "Create 6-10 scenes based on story needs.",
            "Scenes are the atomic narrative unit - continuous prose, no subdivisions."
        ])

        context = '\n'.join(parts)
        logger.debug(f"Outline context: {count_tokens_estimate(context)} tokens")
        return context

    def for_prose_agent(
        self,
        scene_outline: SceneOutline,
        total_scenes: int,
        include_style: bool = True
    ) -> str:
        """
        Prepare context for a prose generation agent.

        Args:
            scene_outline: The scene to write
            total_scenes: Total number of scenes in story
            include_style: Whether to include style notes

        Returns:
            Context string (~260 words)
        """
        parts = [
            "=== STORY SEED ===",
            self.compiler.get_story_seed(),
            "",
            "=== SCENE CONTEXT ===",
            self.compiler.get_relevant_cards(
                character_tags=scene_outline.characters,
                location_tag=scene_outline.location
            ),
            "",
            "=== SCENE GOAL ===",
            scene_outline.to_context(),
            ""
        ]

        # Add thread tracker context
        tracker_context = self.tracker.to_context()
        if tracker_context:
            parts.extend([
                "=== CONTINUITY ===",
                tracker_context,
                ""
            ])

        # Add style if requested
        if include_style and self.compiler.world_config:
            style = self.compiler.world_config.get('visual_style', '')
            vibe = self.compiler.world_config.get('vibe', '')
            if style or vibe:
                parts.extend([
                    "=== STYLE ===",
                    f"Visual: {style}" if style else "",
                    f"Vibe: {vibe}" if vibe else "",
                    ""
                ])

        parts.extend([
            "=== TASK ===",
            f"Write scene {scene_outline.scene_number} of {total_scenes}.",
            "Write 150-250 words of continuous prose.",
            "Let the story breathe naturally through the narrative.",
            "NO markers, NO notation - pure prose only.",
            "Focus on the goal and key moment.",
            "Ensure character states transition from entry to exit."
        ])

        context = '\n'.join(parts)
        logger.debug(f"Prose context: {count_tokens_estimate(context)} tokens")
        return context

    def estimate_total_tokens(
        self,
        num_scenes: int = 8,
        num_concepts: int = 5,
        num_judges: int = 3
    ) -> Dict[str, int]:
        """
        Estimate total token usage for a full pipeline run.

        SCENE-ONLY ARCHITECTURE: No beat extraction phase.

        Args:
            num_scenes: Number of scenes to generate
            num_concepts: Number of brainstorm concepts
            num_judges: Number of judge agents

        Returns:
            Token estimates by phase
        """
        # Estimate based on typical context sizes
        brainstorm_per = 800  # ~200 words
        judge_per = 4400  # ~1100 words
        outline = 1400  # ~350 words
        prose_per = 1040  # ~260 words

        return {
            "phase_1_brainstorm": brainstorm_per * num_concepts,
            "phase_2_selection": judge_per * num_judges,
            "phase_3_outline": outline,
            "phase_4_prose": prose_per * num_scenes,
            "phase_5_validation": 2000,  # Fixed estimate
            "total": (
                brainstorm_per * num_concepts +
                judge_per * num_judges +
                outline +
                prose_per * num_scenes +
                2000
            )
        }

    @classmethod
    def from_project(cls, project_path: Path) -> "AgentContextDelivery":
        """
        Create AgentContextDelivery from a project directory.

        Args:
            project_path: Path to the project root

        Returns:
            Initialized AgentContextDelivery
        """
        compiler = ContextCompiler.from_project(project_path)
        tracker = ThreadTracker()
        return cls(compiler=compiler, tracker=tracker)


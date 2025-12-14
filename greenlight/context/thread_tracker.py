"""
Greenlight Thread Tracker

Tracks narrative threads across scenes for Story Pipeline v3.0.
Provides lightweight continuity context (~50 words max) for prose agents.

Key features:
- active_threads: Current narrative threads being developed
- setups_awaiting_payoff: Chekhov's guns that need resolution
- last_line: Final sentence of previous scene for smooth transitions
- tension_level: Current story tension (1-10)
- character_states: Current emotional state per character
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re

from greenlight.core.logging_config import get_logger

logger = get_logger("context.thread_tracker")


@dataclass
class ThreadTracker:
    """
    Tracks narrative threads across scenes (~50 words max context).
    
    Used by prose agents to maintain continuity without passing
    full previous scenes. Updated after each scene generation.
    """
    
    # Active narrative threads (e.g., "Mei's secret plan", "Lin unaware")
    active_threads: List[str] = field(default_factory=list)
    
    # Setups awaiting payoff (e.g., "orchid symbolism introduced")
    setups_awaiting_payoff: List[str] = field(default_factory=list)
    
    # Final sentence of previous scene for transition
    last_line: str = ""
    
    # Current tension level (1-10)
    tension_level: int = 5
    
    # Character emotional states (tag -> state)
    character_states: Dict[str, str] = field(default_factory=dict)
    
    # Scene counter
    current_scene: int = 0
    
    def to_context(self) -> str:
        """
        Generate context string for prose agent (~50 words max).
        
        Returns:
            Compressed context string for LLM prompt
        """
        parts = []
        
        # Active threads (most important)
        if self.active_threads:
            threads = ', '.join(self.active_threads[:3])  # Max 3 threads
            parts.append(f"THREADS: {threads}")
        
        # Setups needing payoff
        if self.setups_awaiting_payoff:
            setups = ', '.join(self.setups_awaiting_payoff[:2])  # Max 2
            parts.append(f"SETUPS: {setups}")
        
        # Previous scene ending
        if self.last_line:
            # Truncate to ~15 words
            words = self.last_line.split()[:15]
            truncated = ' '.join(words)
            if len(words) < len(self.last_line.split()):
                truncated += "..."
            parts.append(f'PREVIOUS: "{truncated}"')
        
        # Tension level
        parts.append(f"TENSION: {self.tension_level}/10")
        
        return '\n'.join(parts)
    
    def update_from_scene(
        self,
        prose: str,
        exit_states: Dict[str, str] = None,
        new_tension: int = None
    ) -> None:
        """
        Update tracker after a scene is generated.
        
        Args:
            prose: The generated scene prose
            exit_states: Character states at scene end
            new_tension: Updated tension level
        """
        self.current_scene += 1
        
        # Update last line
        self._extract_last_line(prose)
        
        # Update character states
        if exit_states:
            self.character_states.update(exit_states)
        
        # Update tension
        if new_tension is not None:
            self.tension_level = max(1, min(10, new_tension))
        
        logger.debug(
            f"ThreadTracker updated: scene={self.current_scene}, "
            f"tension={self.tension_level}, threads={len(self.active_threads)}"
        )
    
    def _extract_last_line(self, prose: str) -> None:
        """Extract the last meaningful sentence from prose."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', prose.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if sentences:
            self.last_line = sentences[-1]
            # Add back punctuation
            if prose.strip()[-1] in '.!?':
                self.last_line += prose.strip()[-1]
    
    def add_thread(self, thread: str) -> None:
        """Add a new active thread."""
        if thread and thread not in self.active_threads:
            self.active_threads.append(thread)
            logger.debug(f"Added thread: {thread}")
    
    def resolve_thread(self, thread: str) -> None:
        """Remove a resolved thread."""
        if thread in self.active_threads:
            self.active_threads.remove(thread)
            logger.debug(f"Resolved thread: {thread}")
    
    def add_setup(self, setup: str) -> None:
        """Add a setup awaiting payoff (Chekhov's gun)."""
        if setup and setup not in self.setups_awaiting_payoff:
            self.setups_awaiting_payoff.append(setup)
            logger.debug(f"Added setup: {setup}")
    
    def payoff_setup(self, setup: str) -> None:
        """Mark a setup as paid off."""
        if setup in self.setups_awaiting_payoff:
            self.setups_awaiting_payoff.remove(setup)
            logger.debug(f"Paid off setup: {setup}")

    def set_character_state(self, tag: str, state: str) -> None:
        """Set a character's current emotional state."""
        self.character_states[tag] = state

    def get_character_state(self, tag: str) -> str:
        """Get a character's current emotional state."""
        return self.character_states.get(tag, "unknown")

    def get_unresolved_count(self) -> int:
        """Get count of unresolved setups (for validation)."""
        return len(self.setups_awaiting_payoff)

    def get_character_states_summary(self) -> str:
        """Get a brief summary of character states."""
        if not self.character_states:
            return ""

        parts = [f"{tag}: {state}" for tag, state in self.character_states.items()]
        return "STATES: " + ', '.join(parts[:3])  # Max 3 characters

    def reset(self) -> None:
        """Reset tracker for a new story."""
        self.active_threads.clear()
        self.setups_awaiting_payoff.clear()
        self.last_line = ""
        self.tension_level = 5
        self.character_states.clear()
        self.current_scene = 0
        logger.info("ThreadTracker reset")

    def to_dict(self) -> Dict:
        """Serialize tracker state to dictionary."""
        return {
            "active_threads": self.active_threads.copy(),
            "setups_awaiting_payoff": self.setups_awaiting_payoff.copy(),
            "last_line": self.last_line,
            "tension_level": self.tension_level,
            "character_states": self.character_states.copy(),
            "current_scene": self.current_scene
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ThreadTracker":
        """Create tracker from dictionary."""
        return cls(
            active_threads=data.get("active_threads", []),
            setups_awaiting_payoff=data.get("setups_awaiting_payoff", []),
            last_line=data.get("last_line", ""),
            tension_level=data.get("tension_level", 5),
            character_states=data.get("character_states", {}),
            current_scene=data.get("current_scene", 0)
        )


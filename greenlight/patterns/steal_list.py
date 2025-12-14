"""
Greenlight Steal List Pattern - Story Pipeline v3.0

The Steal List Aggregator collects and validates "steal" elements from judge votes.

Steal List Mechanism:
1. Each judge identifies 2-3 elements worth stealing from non-winning concepts
2. Elements mentioned by 2+ judges are added to the final steal list
3. The winning concept MUST incorporate all steal list items
4. This ensures good ideas aren't lost just because another concept won

The aggregator also provides:
- Semantic similarity matching (to catch near-duplicates)
- Element categorization (character, visual, thematic, etc.)
- Integration validation (verify steal items appear in final output)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from enum import Enum
import re

from greenlight.core.logging_config import get_logger

logger = get_logger("patterns.steal_list")


class StealCategory(Enum):
    """Categories for steal list elements."""
    CHARACTER = "character"      # Character moment, trait, or arc
    VISUAL = "visual"            # Visual image, motif, or atmosphere
    THEMATIC = "thematic"        # Theme, meaning, or message
    RELATIONSHIP = "relationship"  # Connection between characters
    PLOT = "plot"                # Story beat or event
    SENSORY = "sensory"          # Texture, sound, or feeling
    UNKNOWN = "unknown"


@dataclass
class StealElement:
    """A single steal list element with metadata."""
    text: str
    category: StealCategory
    source_judges: List[str]  # Judge IDs that mentioned this
    mention_count: int
    normalized_text: str = ""  # For similarity matching
    
    def __post_init__(self):
        if not self.normalized_text:
            self.normalized_text = self._normalize(self.text)
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase, remove punctuation, collapse whitespace
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


@dataclass
class StealListResult:
    """Result from steal list aggregation."""
    elements: List[StealElement]
    all_mentions: List[str]  # All elements mentioned (including < 2 mentions)
    threshold: int
    
    def get_required_elements(self) -> List[str]:
        """Get list of element texts that must be incorporated."""
        return [e.text for e in self.elements]
    
    def to_prompt_text(self) -> str:
        """Format steal list for inclusion in prompts."""
        if not self.elements:
            return "No steal list elements required."
        
        lines = ["MUST INCLUDE (from steal list):"]
        for i, element in enumerate(self.elements, 1):
            lines.append(f"  {i}. {element.text} [{element.category.value}]")
        return "\n".join(lines)


class StealListAggregator:
    """
    Aggregates steal elements from multiple judges.
    
    Features:
    - 2+ mention threshold (configurable)
    - Semantic similarity matching for near-duplicates
    - Automatic categorization
    - Integration validation
    """
    
    # Keywords for category detection
    CATEGORY_KEYWORDS = {
        StealCategory.CHARACTER: [
            "character", "protagonist", "antagonist", "hero", "villain",
            "emotion", "feeling", "motivation", "arc", "transformation"
        ],
        StealCategory.VISUAL: [
            "visual", "image", "shot", "frame", "camera", "light", "color",
            "scene", "atmosphere", "look", "aesthetic"
        ],
        StealCategory.THEMATIC: [
            "theme", "meaning", "message", "symbol", "metaphor", "truth",
            "question", "moral", "lesson"
        ],
        StealCategory.RELATIONSHIP: [
            "relationship", "bond", "connection", "between", "together",
            "love", "friendship", "rivalry", "tension"
        ],
        StealCategory.PLOT: [
            "moment", "beat", "event", "twist", "reveal", "climax",
            "confrontation", "discovery", "decision"
        ],
        StealCategory.SENSORY: [
            "texture", "sound", "smell", "taste", "touch", "feeling",
            "sensation", "visceral", "tactile"
        ]
    }
    
    def __init__(self, threshold: int = 2, similarity_threshold: float = 0.7):
        """
        Initialize aggregator.
        
        Args:
            threshold: Minimum mentions required (default: 2)
            similarity_threshold: Similarity score for near-duplicate detection
        """
        self.threshold = threshold
        self.similarity_threshold = similarity_threshold
    
    def aggregate(
        self,
        judge_votes: List[Any],  # List of JudgeVote objects
    ) -> StealListResult:
        """
        Aggregate steal elements from judge votes.
        
        Args:
            judge_votes: List of JudgeVote objects with steal_elements
            
        Returns:
            StealListResult with aggregated elements
        """
        # Collect all mentions with source tracking
        all_mentions: List[str] = []
        element_sources: Dict[str, List[str]] = {}  # normalized -> [judge_ids]
        element_original: Dict[str, str] = {}  # normalized -> original text
        
        for vote in judge_votes:
            for element in vote.steal_elements:
                all_mentions.append(element)
                normalized = StealElement._normalize(element)
                
                if normalized not in element_sources:
                    element_sources[normalized] = []
                    element_original[normalized] = element
                element_sources[normalized].append(vote.judge_id)

        # Filter by threshold and create StealElements
        elements: List[StealElement] = []
        for normalized, sources in element_sources.items():
            if len(sources) >= self.threshold:
                original = element_original[normalized]
                category = self._categorize(original)

                elements.append(StealElement(
                    text=original,
                    category=category,
                    source_judges=sources,
                    mention_count=len(sources),
                    normalized_text=normalized
                ))

        # Sort by mention count (most mentioned first)
        elements.sort(key=lambda e: e.mention_count, reverse=True)

        logger.info(
            f"Steal list aggregation: {len(all_mentions)} total mentions, "
            f"{len(elements)} elements meet threshold of {self.threshold}"
        )

        return StealListResult(
            elements=elements,
            all_mentions=all_mentions,
            threshold=self.threshold
        )

    def _categorize(self, text: str) -> StealCategory:
        """Categorize an element based on keywords."""
        text_lower = text.lower()

        scores: Dict[StealCategory, int] = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        return StealCategory.UNKNOWN

    def validate_integration(
        self,
        steal_list: StealListResult,
        output_text: str
    ) -> Dict[str, Any]:
        """
        Validate that steal list elements appear in output.

        Args:
            steal_list: The steal list to validate
            output_text: The generated output to check

        Returns:
            Dict with validation results
        """
        output_lower = output_text.lower()

        found = []
        missing = []

        for element in steal_list.elements:
            # Check if key words from element appear in output
            words = element.normalized_text.split()
            key_words = [w for w in words if len(w) > 3]  # Skip short words

            if key_words:
                matches = sum(1 for w in key_words if w in output_lower)
                match_ratio = matches / len(key_words)

                if match_ratio >= 0.5:  # At least half the key words found
                    found.append(element.text)
                else:
                    missing.append(element.text)
            else:
                # No key words, check for any match
                if element.normalized_text in output_lower:
                    found.append(element.text)
                else:
                    missing.append(element.text)

        return {
            "valid": len(missing) == 0,
            "found": found,
            "missing": missing,
            "integration_score": len(found) / len(steal_list.elements) if steal_list.elements else 1.0
        }

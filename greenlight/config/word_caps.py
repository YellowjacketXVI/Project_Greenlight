"""
Word Caps Configuration for Writer Flow v2

Defines word limits for different media types and procedural generation budgets.
"""

from typing import Dict, Any
from dataclasses import dataclass


# =============================================================================
# MEDIA TYPE WORD CAPS
# =============================================================================

WORD_CAPS: Dict[str, Dict[str, int]] = {
    "short": {"min": 100, "max": 150, "scenes": 1},
    "brief": {"min": 250, "max": 500, "scenes": 3},
    "standard": {"min": 750, "max": 1000, "scenes": 8},
    "extended": {"min": 1250, "max": 1500, "scenes": 15},
    "feature": {"min": 2000, "max": 3000, "scenes": 40},
    # Dynamic mode: scenes determined by pitch analysis, not preset
    "dynamic": {"min": 0, "max": 0, "scenes": 0}  # Placeholder - actual values from PitchAnalyzer
}

# Frame prompt word cap (per individual frame)
FRAME_PROMPT_CAP = 250


# =============================================================================
# PROCEDURAL OUTPUT BUDGETS
# =============================================================================

OUTPUT_BUDGETS: Dict[str, Dict[str, int]] = {
    "short": {
        "total_words": 125,
        "chunk_size": 125,
        "chunks_needed": 1,
        "synthesis_overhead": 0
    },
    "brief": {
        "total_words": 375,
        "chunk_size": 150,
        "chunks_needed": 3,
        "synthesis_overhead": 25
    },
    "standard": {
        "total_words": 875,
        "chunk_size": 200,
        "chunks_needed": 5,
        "synthesis_overhead": 75
    },
    "extended": {
        "total_words": 1375,
        "chunk_size": 250,
        "chunks_needed": 6,
        "synthesis_overhead": 125
    },
    "feature": {
        "total_words": 2500,
        "chunk_size": 300,
        "chunks_needed": 9,
        "synthesis_overhead": 200
    }
}

# Optimal chunk size range (quality zone)
CHUNK_MIN = 150
CHUNK_MAX = 400
CHUNK_OPTIMAL = 250


# =============================================================================
# PROCEDURAL GENERATION CONFIG
# =============================================================================

PROCEDURAL_CONFIG = {
    # Chunk sizing
    "chunk_min_words": 150,
    "chunk_max_words": 400,
    "chunk_optimal_words": 250,
    
    # Retries
    "max_chunk_retries": 2,
    "max_synthesis_retries": 1,
    
    # Validation
    "word_budget_tolerance": 0.1,  # ±10%
    "require_clean_boundaries": True,
    
    # State tracking
    "include_prev_chunk_paragraphs": 2,
    "include_next_chunk_hint": True,
    
    # Synthesis
    "max_bridge_words": 30,
    "allow_boundary_edits": True
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_word_cap(media_type: str) -> Dict[str, int]:
    """Get word cap configuration for a media type."""
    return WORD_CAPS.get(media_type, WORD_CAPS["standard"])


def get_output_budget(media_type: str) -> Dict[str, int]:
    """Get output budget configuration for a media type."""
    return OUTPUT_BUDGETS.get(media_type, OUTPUT_BUDGETS["standard"])


def calculate_scene_budget(
    total_budget: int,
    scene_count: int,
    scene_weights: Dict[int, float] = None
) -> Dict[int, int]:
    """
    Calculate word budget per scene.
    
    Args:
        total_budget: Total word budget
        scene_count: Number of scenes
        scene_weights: Optional weights per scene (scene_num -> weight)
        
    Returns:
        Dict mapping scene number to word budget
    """
    if scene_weights is None:
        # Equal distribution
        base_budget = total_budget // scene_count
        return {i: base_budget for i in range(1, scene_count + 1)}
    
    # Weighted distribution
    total_weight = sum(scene_weights.values())
    budgets = {}
    for scene_num in range(1, scene_count + 1):
        weight = scene_weights.get(scene_num, 1.0)
        budgets[scene_num] = int((weight / total_weight) * total_budget)
    
    return budgets


"""
Greenlight Tags - Plots Module

Plot/concept tag extraction and validation.

Structure:
    /prompts/
        /01_extraction/     - Tag extraction prompts
    /scripts/
        plot_tagger.py      - Plot-specific tagging logic
    plot_tag_manager.py - Main plot tag manager
"""

from greenlight.tags.plots.plot_tag_manager import PlotTagManager

__all__ = [
    'PlotTagManager',
]


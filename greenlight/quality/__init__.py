"""
Greenlight Quality Module

Quality assurance patterns for validating and improving generated content.

Key Components:
    - QualityOrchestrator: Coordinates all quality agents in phases
    - TelescopeAgent: Zooms out to check overall narrative coherence
    - InquisitorPanel: Multi-agent panel for technical validation
    - ContinuityWeaver: Tracks and validates story continuity
    - ConstellationAgent: Maps relationships between story elements
    - AnchorAgent: Validates notation standards (tags, scene.frame.camera)
    - CoherenceValidator: Validates character motivation coherence
    - MirrorAgent: Reflects content for self-consistency checks

Directory Structure:
    /prompts/               - Externalized prompt templates
        /01_telescope/      - Narrative coherence prompts
        /02_inquisitor/     - Technical validation prompts
        /03_continuity/     - Continuity tracking prompts
        /04_constellation/  - Relationship mapping prompts
        /05_anchor/         - Notation validation prompts
        /06_coherence/      - Motivation coherence prompts
    /agents/                - Quality-specific agents (re-exported from patterns/quality)

Quality Phases (QualityOrchestrator):
    Phase 1: Telescope - Overall narrative check
    Phase 2: Inquisitor - Technical validation
    Phase 3: Continuity + Constellation - Relationship and continuity
    Phase 4: Anchor - Notation validation
    Phase 5: Coherence - Final motivation check
"""

# Re-export from patterns/quality for convenience
from greenlight.patterns.quality.quality_orchestrator import QualityOrchestrator
from greenlight.patterns.quality.telescope_agent import TelescopeAgent
from greenlight.patterns.quality.inquisitor_panel import InquisitorPanel
from greenlight.patterns.quality.continuity_weaver import ContinuityWeaver
from greenlight.patterns.quality.constellation_agent import ConstellationAgent
from greenlight.patterns.quality.anchor_agent import AnchorAgent
from greenlight.patterns.quality.coherence_validator import CoherenceValidator
from greenlight.patterns.quality.mirror_agent import MirrorAgent

__all__ = [
    'QualityOrchestrator',
    'TelescopeAgent',
    'InquisitorPanel',
    'ContinuityWeaver',
    'ConstellationAgent',
    'AnchorAgent',
    'CoherenceValidator',
    'MirrorAgent',
]


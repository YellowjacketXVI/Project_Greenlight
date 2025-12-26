"""
Greenlight Quality Assurance Patterns

Agent patterns for script finalization quality assurance:
- UniversalContext: Ensures world_config + pitch flow to all agents
- TelescopeAgent: Dual-focal (zoom in/out) analysis
- InquisitorPanel: Self-questioning assembly with specialized questioners
- ContinuityWeaver: Cross-scene state tracking
- MirrorAgent: Self-reflection pattern for content refinement
- ConstellationAgent: Tag relationship mapper and validator
- AnchorAgent: Scene.frame.camera notation enforcer
- QualityOrchestrator: Orchestrates all quality phases
"""

from .universal_context import (
    UniversalContext,
    SceneContext,
)
from .telescope_agent import (
    TelescopeAgent,
    TelescopeContext,
    TelescopeAnalysis,
    WideAssessment,
    NarrowAssessment,
)
from .inquisitor_panel import (
    InquisitorPanel,
    InquisitorQuestion,
    InquisitorReport,
    SynthesisResult,
    VisualInquisitor,
    NarrativeInquisitor,
    CharacterInquisitor,
    WorldInquisitor,
    TechnicalInquisitor,
)
from .continuity_weaver import (
    ContinuityWeaver,
    ContinuityThread,
    ContinuityIssue,
    ContinuityReport,
    RepairPatch,
)
from .mirror_agent import (
    MirrorAgent,
    MirrorCritique,
    MirrorIteration,
    MirrorResult,
)
from .constellation_agent import (
    ConstellationAgent,
    ConstellationMap,
    TagRelationship,
    TagValidationIssue,
)
from .anchor_agent import (
    AnchorAgent,
    NotationIssue,
    NotationFix,
    NotationReport,
)
from .quality_orchestrator import (
    QualityOrchestrator,
    QualityConfig,
    QualityPhaseResult,
    QualityReport,
)
from .coherence_validator import (
    CoherenceValidator,
    CoherenceReport,
    CoherenceIssue,
)
from .voice_validator import (
    VoiceValidator,
    VoiceReport,
    VoiceIssue,
    CharacterVoiceProfile,
    create_validator_from_character_arcs,
)

__all__ = [
    # Universal Context
    'UniversalContext',
    'SceneContext',
    # Telescope Agent
    'TelescopeAgent',
    'TelescopeContext',
    'TelescopeAnalysis',
    'WideAssessment',
    'NarrowAssessment',
    # Inquisitor Panel
    'InquisitorPanel',
    'InquisitorQuestion',
    'InquisitorReport',
    'SynthesisResult',
    'VisualInquisitor',
    'NarrativeInquisitor',
    'CharacterInquisitor',
    'WorldInquisitor',
    'TechnicalInquisitor',
    # Continuity Weaver
    'ContinuityWeaver',
    'ContinuityThread',
    'ContinuityIssue',
    'ContinuityReport',
    'RepairPatch',
    # Mirror Agent
    'MirrorAgent',
    'MirrorCritique',
    'MirrorIteration',
    'MirrorResult',
    # Constellation Agent
    'ConstellationAgent',
    'ConstellationMap',
    'TagRelationship',
    'TagValidationIssue',
    # Anchor Agent
    'AnchorAgent',
    'NotationIssue',
    'NotationFix',
    'NotationReport',
    # Quality Orchestrator
    'QualityOrchestrator',
    'QualityConfig',
    'QualityPhaseResult',
    'QualityReport',
    # Coherence Validator (Story Pipeline v3.0)
    'CoherenceValidator',
    'CoherenceReport',
    'CoherenceIssue',
    # Voice Validator (Character Voice Differentiation)
    'VoiceValidator',
    'VoiceReport',
    'VoiceIssue',
    'CharacterVoiceProfile',
    'create_validator_from_character_arcs',
]


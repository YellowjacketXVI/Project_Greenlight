"""
Greenlight Omni Mind Core

Re-export of OmniMind for backward compatibility.
"""

from .omni_mind import OmniMind, AssistantMode, AssistantResponse

# Alias for backward compatibility
OmniMindCore = OmniMind

__all__ = [
    'OmniMindCore',
    'OmniMind',
    'AssistantMode',
    'AssistantResponse',
]


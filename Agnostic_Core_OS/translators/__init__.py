"""Vector ↔ Natural language translators."""

from .vector_language import VectorLanguageTranslator, VectorNotation
from .systems_translator import (
    SystemsTranslatorIndex,
    SystemInfo,
    BuildParameters,
    CommandTranslation,
    OSType,
    Architecture,
    ShellType,
    get_systems_translator,
)

__all__ = [
    # Vector Language
    "VectorLanguageTranslator",
    "VectorNotation",
    # Systems Translator
    "SystemsTranslatorIndex",
    "SystemInfo",
    "BuildParameters",
    "CommandTranslation",
    "OSType",
    "Architecture",
    "ShellType",
    "get_systems_translator",
]


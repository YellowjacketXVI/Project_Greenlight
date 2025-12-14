"""
Vector Language Translator - Natural ↔ Vector Notation Translation

Translates between natural language and vector notation for LLM interactions.
Supports bidirectional translation with context preservation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
import re
import json
from pathlib import Path


class NotationType(Enum):
    """Types of vector notation."""
    TAG = "tag"              # @TAG lookups
    SCOPE = "scope"          # #SCOPE filters
    INCLUDE = "include"      # +INCLUDE
    EXCLUDE = "exclude"      # -EXCLUDE
    SIMILAR = "similar"      # ~SIMILAR semantic
    PIPELINE = "pipeline"    # >PIPELINE commands
    QUERY = "query"          # ?QUERY natural language
    COMMAND = "command"      # Direct commands
    ROUTE = "route"          # >route vector routing


@dataclass
class VectorNotation:
    """A parsed vector notation element."""
    notation_type: NotationType
    symbol: str
    value: str
    params: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.notation_type.value,
            "symbol": self.symbol,
            "value": self.value,
            "params": self.params,
            "raw": self.raw
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorNotation":
        return cls(
            notation_type=NotationType(data["type"]),
            symbol=data["symbol"],
            value=data["value"],
            params=data.get("params", {}),
            raw=data.get("raw", "")
        )


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    success: bool
    input_text: str
    output_text: str
    notations: List[VectorNotation] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "input": self.input_text,
            "output": self.output_text,
            "notations": [n.to_dict() for n in self.notations],
            "context": self.context,
            "tokens_used": self.tokens_used,
            "timestamp": self.timestamp.isoformat()
        }


class VectorLanguageTranslator:
    """
    Bidirectional translator between natural language and vector notation.
    
    Natural Language → Vector Notation:
        "Find character Mei in the story" → "@CHAR_MEI #STORY"
        "Run the story pipeline" → ">story standard"
        "Search for warrior themes" → '~"warrior spirit"'
    
    Vector Notation → Natural Language:
        "@CHAR_MEI #STORY" → "Look up character Mei in story scope"
        ">diagnose" → "Run project diagnostics"
    """
    
    # Notation patterns for parsing
    PATTERNS = {
        NotationType.TAG: re.compile(r'@([A-Z_]+(?:_[A-Z0-9]+)*)'),
        NotationType.SCOPE: re.compile(r'#([A-Z_]+)'),
        NotationType.INCLUDE: re.compile(r'\+([a-z_]+)'),
        NotationType.EXCLUDE: re.compile(r'-([a-z_]+)'),
        NotationType.SIMILAR: re.compile(r'~"([^"]+)"'),
        NotationType.PIPELINE: re.compile(r'>([a-z_]+)\s*([a-z_]*)?'),
        NotationType.QUERY: re.compile(r'\?"([^"]+)"'),
        NotationType.ROUTE: re.compile(r'>route\s+(\w+)(?:\s+(.+))?'),
    }
    
    # Natural language mappings
    NL_TO_VECTOR = {
        # Tag lookups
        r"find (?:the )?character (\w+)": "@CHAR_{0}",
        r"look up (?:the )?location (\w+)": "@LOC_{0}",
        r"get (?:the )?prop (\w+)": "@PROP_{0}",
        r"search for (\w+) tag": "@{0}",
        # Scope filters
        r"in (?:the )?story": "#STORY",
        r"in (?:the )?world bible": "#WORLD_BIBLE",
        r"in (?:the )?storyboard": "#STORYBOARD",
        r"in (?:the )?project": "#PROJECT",
        # Pipeline commands
        r"run (?:the )?story pipeline": ">story standard",
        r"run (?:the )?directing pipeline": ">direct by_scene",
        r"run diagnostics": ">diagnose",
        r"heal (?:the )?project": ">heal",
        r"validate tags": ">validate tags",
        # Semantic search
        r"search for (.+) themes?": '~"{0}"',
        r"find similar to (.+)": '~"{0}"',
        # Routing
        r"route error": ">route error",
        r"archive (.+)": ">route archive {0}",
        r"flush cache": ">route flush",
    }
    
    # Vector to natural language
    VECTOR_TO_NL = {
        "@CHAR_": "Look up character {0}",
        "@LOC_": "Look up location {0}",
        "@PROP_": "Look up prop {0}",
        "#STORY": "in story scope",
        "#WORLD_BIBLE": "in world bible scope",
        "#STORYBOARD": "in storyboard scope",
        "#PROJECT": "in project scope",
        ">story": "Run story pipeline",
        ">direct": "Run directing pipeline",
        ">diagnose": "Run project diagnostics",
        ">heal": "Auto-heal project issues",
        ">route error": "Route error to handoff",
        ">route archive": "Archive to background storage",
        ">route flush": "Flush vector cache",
    }

    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize the translator."""
        self.log_dir = log_dir
        self._translation_history: List[TranslationResult] = []

    def natural_to_vector(self, text: str) -> TranslationResult:
        """
        Translate natural language to vector notation.

        Args:
            text: Natural language input

        Returns:
            TranslationResult with vector notation output
        """
        notations = []
        output_parts = []
        remaining = text.lower().strip()

        for pattern, vector_template in self.NL_TO_VECTOR.items():
            match = re.search(pattern, remaining, re.IGNORECASE)
            if match:
                groups = match.groups()
                if groups:
                    vector = vector_template.format(*[g.upper() for g in groups])
                else:
                    vector = vector_template
                output_parts.append(vector)

                # Parse the notation type
                for ntype, npattern in self.PATTERNS.items():
                    nmatch = npattern.match(vector)
                    if nmatch:
                        notations.append(VectorNotation(
                            notation_type=ntype,
                            symbol=vector[0],
                            value=nmatch.group(1),
                            raw=vector
                        ))
                        break

        output = " ".join(output_parts) if output_parts else text
        result = TranslationResult(
            success=len(output_parts) > 0,
            input_text=text,
            output_text=output,
            notations=notations,
            tokens_used=len(text.split()) + len(output.split())
        )
        self._translation_history.append(result)
        return result

    def vector_to_natural(self, vector_text: str) -> TranslationResult:
        """
        Translate vector notation to natural language.

        Args:
            vector_text: Vector notation input

        Returns:
            TranslationResult with natural language output
        """
        notations = []
        output_parts = []

        # Parse all notations in the text
        for ntype, pattern in self.PATTERNS.items():
            for match in pattern.finditer(vector_text):
                value = match.group(1)
                notations.append(VectorNotation(
                    notation_type=ntype,
                    symbol=vector_text[match.start()],
                    value=value,
                    raw=match.group(0)
                ))

        # Translate each notation
        for notation in notations:
            for prefix, template in self.VECTOR_TO_NL.items():
                if notation.raw.startswith(prefix):
                    # Extract the specific part after prefix
                    suffix = notation.value.replace(prefix.lstrip("@#>"), "")
                    if "{0}" in template:
                        output_parts.append(template.format(suffix or notation.value))
                    else:
                        output_parts.append(template)
                    break

        output = " ".join(output_parts) if output_parts else f"Execute: {vector_text}"
        result = TranslationResult(
            success=len(notations) > 0,
            input_text=vector_text,
            output_text=output,
            notations=notations,
            tokens_used=len(vector_text.split()) + len(output.split())
        )
        self._translation_history.append(result)
        return result

    def parse_notations(self, text: str) -> List[VectorNotation]:
        """Parse all vector notations from text."""
        notations = []
        for ntype, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                notations.append(VectorNotation(
                    notation_type=ntype,
                    symbol=text[match.start()],
                    value=match.group(1),
                    params={"groups": match.groups()},
                    raw=match.group(0)
                ))
        return notations

    def get_history(self) -> List[Dict[str, Any]]:
        """Get translation history."""
        return [r.to_dict() for r in self._translation_history]

    def clear_history(self) -> None:
        """Clear translation history."""
        self._translation_history.clear()


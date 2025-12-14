"""
Greenlight Context Module

Enhanced context engine with RAG capabilities, vector search, and agentic search.

Story Pipeline v3.0 additions:
- ContextCompiler: Compiles minimal context packets (~250 words per agent)
- ThreadTracker: Tracks narrative threads across scenes (~50 words)
- AgentContextDelivery: Prepares context for specific agent types
"""

from .context_engine import ContextEngine, ContextQuery, ContextResult, ContextSource
from .vector_store import VectorStore
from .keyword_index import KeywordIndex
from .context_assembler import ContextAssembler
from .context_compiler import ContextCompiler
from .thread_tracker import ThreadTracker
from .agent_context_delivery import AgentContextDelivery, SceneOutline

__all__ = [
    'ContextEngine',
    'ContextQuery',
    'ContextResult',
    'ContextSource',
    'VectorStore',
    'KeywordIndex',
    'ContextAssembler',
    # Story Pipeline v3.0
    'ContextCompiler',
    'ThreadTracker',
    'AgentContextDelivery',
    'SceneOutline',
]


# Project Greenlight - Core Architecture Documentation

> **Version:** 1.0
> **Last Updated:** 2025-12-13
> **Purpose:** Comprehensive technical documentation of core architectural components

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Context Engine](#1-context-engine)
3. [Nodes Graph (Dependency Graph)](#2-nodes-graph-dependency-graph)
4. [Symbolic Notation System](#3-symbolic-notation-system)
5. [OmniMind Operations](#4-omnimind-operations)
6. [System Integration](#5-system-integration)
7. [Data Flow Diagrams](#6-data-flow-diagrams)

---

## System Overview

Project Greenlight is a vector-native runtime environment for AI-powered story development. The architecture consists of four interconnected core systems:

| System | Purpose | Primary Location |
|--------|---------|------------------|
| **Context Engine** | RAG-based retrieval and indexing | `greenlight/context/` |
| **Nodes Graph** | Dependency tracking and propagation | `greenlight/graph/` |
| **Symbolic Notation** | Query language and notation parsing | `greenlight/omni_mind/symbolic_registry.py` |
| **OmniMind** | AI orchestration and self-healing | `greenlight/omni_mind/` |

### Architectural Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           UI LAYER (Flet)                               │
├─────────────────────────────────────────────────────────────────────────┤
│                         OMNIMIND LAYER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Tool        │  │ Decision    │  │ Suggestion  │  │ Self-Heal   │    │
│  │ Executor    │  │ Engine      │  │ Engine      │  │ Queue       │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
├─────────────────────────────────────────────────────────────────────────┤
│                       CONTEXT & GRAPH LAYER                             │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐      │
│  │      Context Engine         │  │     Dependency Graph        │      │
│  │  ┌─────────┐ ┌───────────┐  │  │  ┌─────────┐ ┌───────────┐  │      │
│  │  │ Vector  │ │ Keyword   │  │  │  │ Nodes   │ │ Edges     │  │      │
│  │  │ Store   │ │ Index     │  │  │  │         │ │           │  │      │
│  │  └─────────┘ └───────────┘  │  │  └─────────┘ └───────────┘  │      │
│  └─────────────────────────────┘  └─────────────────────────────┘      │
├─────────────────────────────────────────────────────────────────────────┤
│                      SYMBOLIC NOTATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Symbolic Registry  │  Vector Language  │  Notation Library     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                     AGNOSTIC_CORE_OS LAYER                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Runtime     │  │ Core        │  │ Vector      │  │ LLM         │    │
│  │ Daemon      │  │ OmniMind    │  │ Cache       │  │ Handshake   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Context Engine

### Purpose and Responsibilities

The Context Engine provides **RAG (Retrieval-Augmented Generation) capabilities** for Project Greenlight. It indexes project content and retrieves relevant context for LLM operations.

**Key Responsibilities:**
- Semantic search via vector embeddings
- Keyword search with fuzzy matching
- Graph-based context traversal
- Tag-aware retrieval
- Story element tracking
- Pipeline output tracking (Script, Visual_Script, world_config)

### Architecture

**File Locations:**
```
greenlight/context/
├── __init__.py
├── context_engine.py      # Main ContextEngine class
├── context_assembler.py   # Context assembly and budget management
├── vector_store.py        # FAISS-based vector storage
└── keyword_index.py       # Inverted index for keyword search
```

### Key Classes

#### ContextEngine (`context_engine.py`)

The central orchestrator for all retrieval operations.

```python
class ContextEngine:
    """
    Enhanced context engine with RAG capabilities.

    Components:
    - vector_store: VectorStore for semantic search
    - keyword_index: KeywordIndex for text search
    - tag_registry: TagRegistry for validation
    - graph: DependencyGraph for relationships
    - assembler: ContextAssembler for budget management
    """
```

#### VectorStore (`vector_store.py`)

Manages vector embeddings with FAISS integration.

```python
class VectorStore:
    """
    Vector storage with FAISS indexing.

    Features:
    - Normalized embeddings for cosine similarity
    - FAISS index for fast nearest-neighbor search
    - Numpy fallback when FAISS unavailable
    - Metadata storage per entry
    """
```

#### KeywordIndex (`keyword_index.py`)

Inverted index for fast keyword lookups.

```python
class KeywordIndex:
    """
    Keyword-based search index.

    Features:
    - Tokenization with configurable min length
    - Inverted index for O(1) term lookup
    - Fuzzy matching with similarity threshold
    - Phrase search support
    """
```

#### ContextAssembler (`context_assembler.py`)

Manages context budget and assembly from multiple sources.

```python
class ContextAssembler:
    """
    Assembles context from multiple sources within token budget.

    Budget Allocation (default):
    - WORLD_BIBLE: 30%
    - VECTOR_SEARCH: 25%
    - KEYWORD_SEARCH: 20%
    - GRAPH_TRAVERSAL: 15%
    - MEMORY: 10%
    """
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONTEXT ENGINE DATA FLOW                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                                                        │
│  │ Document    │──────────────────────────────────────────────┐         │
│  │ (pitch.md,  │                                              │         │
│  │ world_bible)│                                              ▼         │
│  └─────────────┘                                    ┌─────────────────┐ │
│         │                                           │  Tag Parser     │ │
│         │ index_document()                          │  (extract tags) │ │
│         ▼                                           └────────┬────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DUAL INDEXING                               │   │
│  │  ┌─────────────────────┐    ┌─────────────────────┐             │   │
│  │  │    Vector Store     │    │   Keyword Index     │             │   │
│  │  │  ┌───────────────┐  │    │  ┌───────────────┐  │             │   │
│  │  │  │ Embeddings    │  │    │  │ Inverted      │  │             │   │
│  │  │  │ (FAISS)       │  │    │  │ Index         │  │             │   │
│  │  │  └───────────────┘  │    │  └───────────────┘  │             │   │
│  │  └─────────────────────┘    └─────────────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────┐     retrieve()      ┌─────────────────────────────┐   │
│  │ ContextQuery│─────────────────────▶│     Context Assembler      │   │
│  │ - query_text│                      │  ┌─────────────────────┐   │   │
│  │ - tags      │                      │  │ Budget Management   │   │   │
│  │ - sources   │                      │  │ - max_tokens: 50000 │   │   │
│  │ - node_ids  │                      │  │ - source priority   │   │   │
│  └─────────────┘                      │  └─────────────────────┘   │   │
│                                       └──────────────┬──────────────┘   │
│                                                      │                  │
│                                                      ▼                  │
│                                       ┌─────────────────────────────┐   │
│                                       │      ContextResult          │   │
│                                       │  - assembled context        │   │
│                                       │  - vector_results           │   │
│                                       │  - keyword_results          │   │
│                                       │  - graph_context            │   │
│                                       │  - tags_found               │   │
│                                       └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| Index Document | `index_document(doc_id, content, doc_type)` | Add document to both vector and keyword indexes |
| Retrieve Context | `retrieve(ContextQuery)` | Multi-source retrieval with budget management |
| Index Project | `index_project_files(project_path)` | Bulk index all project files |
| Get World Bible | `_get_world_bible_context(tags)` | Retrieve world bible entries by tag |
| Graph Context | `_get_graph_context(node_ids)` | Traverse graph for related content |

### Integration Points

- **OmniMind**: Uses Context Engine for all retrieval operations
- **Dependency Graph**: Provides graph-based context traversal
- **Tag Registry**: Validates and categorizes extracted tags
- **Pipelines**: Index pipeline outputs (script.md, visual_script.md)

---

## 2. Nodes Graph (Dependency Graph)

### Purpose and Responsibilities

The Dependency Graph tracks **relationships between story elements** and manages **edit propagation** through the system.

**Key Responsibilities:**
- Node and edge management for story elements
- Dependency traversal (upstream/downstream)
- Cycle detection and prevention
- Affected node calculation for cascading updates
- Pipeline flow tracking
- Regeneration queue management

### Architecture

**File Locations:**
```
greenlight/graph/
├── __init__.py
├── dependency_graph.py    # Core graph with NetworkX
├── propagation_engine.py  # Cascading edit management
└── regeneration_queue.py  # Priority-based regeneration
```

### Node Types

```python
class NodeType(Enum):
    # Story Elements
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    SCENE = "scene"
    FRAME = "frame"
    SHOT = "shot"
    BEAT = "beat"
    EPISODE = "episode"
    SEASON = "season"
    CONCEPT = "concept"
    EVENT = "event"

    # Pipeline Outputs
    PITCH = "pitch"
    WORLD_CONFIG = "world_config"
    SCRIPT = "script"
    VISUAL_SCRIPT = "visual_script"
    TAG_REFERENCE = "tag_reference"
    STORYBOARD_PROMPT = "storyboard_prompt"

    # Pipeline Types
    PIPELINE = "pipeline"
```

### Edge Types (Relationships)

```python
class EdgeType(Enum):
    CONTAINS = "contains"           # Parent contains child
    REFERENCES = "references"       # Element references another
    DEPENDS_ON = "depends_on"       # Element depends on another
    APPEARS_IN = "appears_in"       # Character/prop appears in scene
    LOCATED_AT = "located_at"       # Scene is at location
    RELATED_TO = "related_to"       # General relationship
    PRECEDES = "precedes"           # Temporal ordering
    DERIVED_FROM = "derived_from"   # Generated from source

    # Pipeline Relationships
    PRODUCES = "produces"           # Pipeline produces output
    CONSUMES = "consumes"           # Pipeline consumes input
    TRANSFORMS = "transforms"       # Pipeline transforms input to output
```


### Pipeline Flow Graph

The graph tracks the complete pipeline flow:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE FLOW GRAPH                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                          ┌─────────────┐                                │
│                          │  pitch.md   │                                │
│                          └──────┬──────┘                                │
│                                 │                                       │
│              ┌──────────────────┼──────────────────┐                    │
│              │                  │                  │                    │
│              ▼                  ▼                  ▼                    │
│  ┌───────────────────┐ ┌───────────────┐ ┌───────────────────┐         │
│  │ World Bible       │ │ Story         │ │ Story Pipeline    │         │
│  │ Pipeline          │ │ Pipeline      │ │ v2 (Assembly)     │         │
│  └─────────┬─────────┘ └───────┬───────┘ └─────────┬─────────┘         │
│            │                   │                   │                    │
│            ▼                   └─────────┬─────────┘                    │
│  ┌───────────────────┐                   │                              │
│  │ world_config.json │                   ▼                              │
│  └───────────────────┘         ┌─────────────────┐                      │
│                                │   script.md     │                      │
│                                └────────┬────────┘                      │
│                                         │                               │
│                    ┌────────────────────┼────────────────────┐          │
│                    │                    │                    │          │
│                    ▼                    ▼                    ▼          │
│        ┌───────────────────┐ ┌───────────────────┐ ┌─────────────────┐ │
│        │ Directing         │ │ Procedural        │ │ Tag Reference   │ │
│        │ Pipeline          │ │ Generator         │ │ System          │ │
│        └─────────┬─────────┘ └─────────┬─────────┘ └────────┬────────┘ │
│                  │                     │                    │          │
│                  └──────────┬──────────┘                    │          │
│                             ▼                               ▼          │
│                  ┌───────────────────┐           ┌─────────────────┐   │
│                  │ visual_script.md  │           │ tag_references  │   │
│                  └─────────┬─────────┘           └────────┬────────┘   │
│                            │                              │            │
│                            └──────────────┬───────────────┘            │
│                                           ▼                            │
│                              ┌─────────────────────┐                   │
│                              │ storyboard_prompts  │                   │
│                              └─────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Classes

#### DependencyGraph (`dependency_graph.py`)

Core graph implementation using NetworkX.

```python
class DependencyGraph:
    """
    Manages dependencies between story elements using NetworkX.

    Key Methods:
    - add_node(node_id, node_type, name, **data)
    - add_edge(source_id, target_id, edge_type, weight)
    - get_dependents(node_id)      # Downstream nodes
    - get_dependencies(node_id)    # Upstream nodes
    - get_all_affected(node_id)    # All downstream via BFS
    - register_pipeline_flow()     # Setup pipeline graph
    - mark_for_regeneration(node_id, reason)
    """
```

#### PropagationEngine (`propagation_engine.py`)

Manages cascading edits through the graph.

```python
class PropagationEngine:
    """
    Manages cascading edits through the dependency graph.

    Strategies:
    - IMMEDIATE: Propagate changes immediately
    - QUEUED: Add to regeneration queue
    - SELECTIVE: Only propagate to selected nodes
    - MANUAL: Mark for manual review
    """
```

#### RegenerationQueue (`regeneration_queue.py`)

Priority-based queue for content regeneration.

```python
class RegenerationQueue:
    """
    Priority-based queue for managing content regeneration.

    Priority Levels:
    - CRITICAL (1): Must regenerate immediately
    - HIGH (2): Regenerate soon
    - NORMAL (3): Standard priority
    - LOW (4): Can wait
    - BACKGROUND (5): Regenerate when idle
    """
```

### Key Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| Add Node | `add_node(id, type, name)` | Add story element to graph |
| Add Edge | `add_edge(source, target, type)` | Create relationship |
| Get Dependents | `get_dependents(node_id)` | Get downstream nodes |
| Get Dependencies | `get_dependencies(node_id)` | Get upstream nodes |
| Get All Affected | `get_all_affected(node_id)` | BFS for all downstream |
| Mark Regeneration | `mark_for_regeneration(node_id)` | Flag node and dependents |
| Propagate Change | `propagate(event, strategy)` | Cascade changes |

### Integration Points

- **Context Engine**: Provides graph-based context traversal
- **OmniMind**: Triggers regeneration on content changes
- **Pipelines**: Registered as nodes with PRODUCES/CONSUMES edges
- **Self-Heal Queue**: Coordinates with regeneration queue

---

## 3. Symbolic Notation System

### Purpose and Responsibilities

The Symbolic Notation System provides a **domain-specific query language** for interacting with Project Greenlight's content and operations.

**Key Responsibilities:**
- Parse and validate symbolic notation (Scene.Frame.Camera)
- Translate between natural language and vector notation
- Manage notation library with learning capabilities
- Route vectors with weight-based prioritization
- Self-healing symbol registration

### Architecture

**File Locations:**
```
greenlight/omni_mind/
├── symbolic_registry.py       # Dynamic symbol learning
├── vector_cache.py            # Weighted vector caching

greenlight/config/
├── notation_patterns.py       # Regex patterns for notation

Agnostic_Core_OS/translators/
├── vector_language.py         # Natural ↔ Vector translation

Agnostic_Core_OS/procedural/
├── notation_library.py        # Core notation storage
```

### Notation Syntax

#### Scene.Frame.Camera Notation (Core System)

| Component | Format | Examples |
|-----------|--------|----------|
| **Scene** | `{scene_number}` | `1`, `2`, `8` |
| **Frame** | `{scene}.{frame}` | `1.1`, `2.3`, `8.5` |
| **Camera** | `{scene}.{frame}.c{letter}` | `1.1.cA`, `2.3.cB` |

**Full Notation Examples:**
```
[1.1.cA] (Wide)
cA. WIDE ESTABLISHING SHOT. From elevated position...

[1.2.cB] (Close-up)
cB. CLOSE-UP on character's face...
```

#### Symbolic Query Notation

| Symbol | Type | Meaning | Example |
|--------|------|---------|---------|
| `@` | Tag | Entity reference | `@CHAR_MEI`, `@LOC_TEAHOUSE` |
| `#` | Scope | Category filter | `#WORLD_BIBLE`, `#STORY` |
| `>` | Command | Execute process | `>run_writer`, `>diagnose` |
| `?` | Query | Natural language | `?"who is the protagonist"` |
| `+` | Include | Add to results | `+relationships` |
| `-` | Exclude | Remove from results | `-archived` |
| `~` | Similar | Semantic search | `~"warrior spirit"` |

#### Tag Prefixes

| Prefix | Category | Example |
|--------|----------|---------|
| `CHAR_` | Character | `[CHAR_MEI]` |
| `LOC_` | Location | `[LOC_TEAHOUSE]` |
| `PROP_` | Prop | `[PROP_SWORD]` |
| `CONCEPT_` | Concept | `[CONCEPT_HONOR]` |
| `EVENT_` | Event | `[EVENT_BATTLE]` |
| `ENV_` | Environment | `[ENV_RAIN]` |


### Key Classes

#### SymbolicRegistry (`symbolic_registry.py`)

Dynamic symbol learning and management.

```python
class SymbolicRegistry:
    """
    Dynamic symbol learning and management.

    Features:
    - Wraps NotationLibrary for symbol storage
    - Self-healing via heal_missing_symbol()
    - Usage tracking for learning
    - Symbol validation and parsing
    """
```

#### VectorLanguageTranslator (`vector_language.py`)

Bidirectional translation between natural language and vector notation.

```python
class VectorLanguageTranslator:
    """
    Translates between natural language and vector notation.

    Mappings:
    - NL_TO_VECTOR: "find character" → "@CHAR_"
    - VECTOR_TO_NL: "@CHAR_MEI" → "character Mei"
    """
```

#### VectorCache (`vector_cache.py`)

Weighted caching for vector entries.

```python
class VectorCache:
    """
    LRU cache with weight-based prioritization.

    Entry Types:
    - ERROR_TRANSCRIPT: Error context for handoff
    - NOTATION_DEFINITION: Symbol definitions
    - ARCHIVED_CONCEPT: Deprecated content

    Weights:
    - ACTIVE (+1.0): Primary retrieval
    - ARCHIVED (-0.5): Deprioritized
    - DEPRECATED (-1.0): Excluded from search
    """
```

### Regex Patterns (`notation_patterns.py`)

```python
SCENE_FRAME_CAMERA_PATTERNS = {
    "full_id": r"(\d+)\.(\d+)\.c([A-Z])",           # 1.2.cA
    "scene_frame": r"(\d+)\.(\d+)",                  # 1.2
    "camera_block": r"\[(\d+\.\d+\.c[A-Z])\]\s*\(([^)]+)\)",  # [1.1.cA] (Wide)
    "scene_marker": r"##\s*Scene\s+(\d+):",          # ## Scene 1:
    "beat_marker": r"##\s*Beat:\s*scene\.(\d+)\.(\d+)",  # ## Beat: scene.1.01
    "frame_chunk_start": r"\(/scene_frame_chunk_start/\)",
    "frame_chunk_end": r"\(/scene_frame_chunk_end/\)",
}
```

### Vector Weight System

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VECTOR WEIGHT SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Weight: +1.0 (ACTIVE)                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Primary retrieval path                                          │   │
│  │  - ERROR_TRANSCRIPT: Active error context                        │   │
│  │  - NOTATION_DEFINITION: Current symbols                          │   │
│  │  - TASK_CONTEXT: Active task data                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Weight: -0.5 (ARCHIVED)                                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Deprioritized, background access                                │   │
│  │  - Old versions of content                                       │   │
│  │  - Superseded definitions                                        │   │
│  │  - Historical data                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Weight: -1.0 (DEPRECATED)                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Excluded from search                                            │   │
│  │  - Removed symbols                                               │   │
│  │  - Invalid notations                                             │   │
│  │  - Obsolete content                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| Parse Notation | `parse_notation(text)` | Extract scene.frame.camera IDs |
| Translate NL→Vector | `translate_to_vector(text)` | Convert natural language to notation |
| Translate Vector→NL | `translate_to_natural(notation)` | Convert notation to natural language |
| Register Symbol | `register_symbol(symbol, definition)` | Add new symbol to library |
| Heal Missing | `heal_missing_symbol(symbol)` | Auto-generate missing symbol |
| Cache Entry | `cache.put(key, value, type, weight)` | Store with weight |
| Route Vector | `route(entry_type, data)` | Route to appropriate handler |

### Integration Points

- **Context Engine**: Symbolic queries drive retrieval
- **OmniMind**: Commands (>) trigger tool execution
- **Tag Registry**: Tag symbols (@) validated against registry
- **Error Handoff**: Error transcripts cached with ACTIVE weight

---

## 4. OmniMind Operations

### Purpose and Responsibilities

OmniMind is the **AI orchestration layer** that coordinates all intelligent operations in Project Greenlight.

**Key Responsibilities:**
- Tool execution and management
- Decision making for autonomous operations
- Self-healing and error recovery
- Project diagnostics and health monitoring
- Context-aware suggestions
- Pipeline orchestration

### Architecture

**File Locations:**
```
greenlight/omni_mind/
├── __init__.py
├── omni_mind.py           # Main OmniMind class
├── tool_executor.py       # Tool registration and execution
├── decision_engine.py     # Autonomous decision making
├── suggestion_engine.py   # Context-aware suggestions
├── self_healer.py         # Error recovery
├── self_heal_queue.py     # Healing task queue
├── error_handoff.py       # Error transcript management
├── vector_cache.py        # Weighted caching
├── project_health.py      # Health monitoring
└── symbolic_registry.py   # Symbol management

Agnostic_Core_OS/runtime/
├── daemon.py              # Background runtime
├── context_engine.py      # Core context operations
└── omni_mind.py           # Core OmniMind operations
```

### OmniMind Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          OMNIMIND ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        USER / UI LAYER                           │   │
│  └────────────────────────────────┬────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         OMNIMIND CORE                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │ Tool        │  │ Decision    │  │ Suggestion              │  │   │
│  │  │ Executor    │  │ Engine      │  │ Engine                  │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │   │
│  │         │                │                     │                 │   │
│  │         └────────────────┼─────────────────────┘                 │   │
│  │                          │                                       │   │
│  │                          ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐│   │
│  │  │                    CONTEXT ENGINE                           ││   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ ││   │
│  │  │  │ Vector      │  │ Keyword     │  │ Dependency          │ ││   │
│  │  │  │ Store       │  │ Index       │  │ Graph               │ ││   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────┘ ││   │
│  │  └─────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      SELF-HEALING LAYER                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │ Self        │  │ Error       │  │ Project                 │  │   │
│  │  │ Healer      │  │ Handoff     │  │ Health                  │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │   │
│  │         │                │                     │                 │   │
│  │         └────────────────┼─────────────────────┘                 │   │
│  │                          │                                       │   │
│  │                          ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐│   │
│  │  │                    VECTOR CACHE                             ││   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ ││   │
│  │  │  │ Error       │  │ Notation    │  │ Archived            │ ││   │
│  │  │  │ Transcripts │  │ Definitions │  │ Concepts            │ ││   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────┘ ││   │
│  │  └─────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```


### Key Classes

#### OmniMind (`omni_mind.py`)

Main orchestration class.

```python
class OmniMind:
    """
    AI orchestration layer for Project Greenlight.

    Components:
    - tool_executor: ToolExecutor for tool management
    - decision_engine: DecisionEngine for autonomous decisions
    - suggestion_engine: SuggestionEngine for recommendations
    - self_healer: SelfHealer for error recovery
    - context_engine: ContextEngine for retrieval
    - symbolic_registry: SymbolicRegistry for notation
    """
```

#### ToolExecutor (`tool_executor.py`)

Tool registration and execution.

```python
class ToolExecutor:
    """
    Manages tool registration and execution.

    Tool Categories:
    - FILE_MANAGEMENT: File read/write/delete
    - PROJECT_INFO: Project queries, diagnostics
    - PIPELINE: Pipeline execution (writer, director)
    - CONTENT_MODIFICATION: RAG-powered content changes

    Key Methods:
    - register_tool(name, fn, description, params, required, category)
    - execute_tool(name, **params)
    - get_tool_declarations()
    """
```

#### SelfHealer (`self_healer.py`)

Pattern-based error recovery.

```python
class SelfHealer:
    """
    Pattern-matching error recovery.

    Features:
    - Healing rules with pattern matching
    - Retry logic with backoff
    - Integration with error handoff
    - Health report logging
    """
```

#### ErrorHandoff (`error_handoff.py`)

Error transcript management and handoff.

```python
class ErrorHandoff:
    """
    Manages error transcripts and guidance tasks.

    Flow:
    1. Flag error with severity
    2. Generate error transcript
    3. Cache in vector cache
    4. Create guidance task
    5. Log to health report
    """
```

### Error Handoff Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ERROR HANDOFF FLOW                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                                                        │
│  │ Error       │                                                        │
│  │ Detected    │                                                        │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [1] FLAG WITH SEVERITY                                           │   │
│  │     CRITICAL | ERROR | WARNING | INFO                            │   │
│  └────────────────────────────────┬────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [2] GENERATE ERROR TRANSCRIPT                                    │   │
│  │     - error_type, message, stack_trace                           │   │
│  │     - context (file, line, function)                             │   │
│  │     - symbolic_context (@TAG, #SCOPE)                            │   │
│  │     - suggested_actions                                          │   │
│  └────────────────────────────────┬────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [3] CACHE IN VECTOR CACHE                                        │   │
│  │     - Type: ERROR_TRANSCRIPT                                     │   │
│  │     - Weight: ACTIVE (+1.0)                                      │   │
│  │     - Max Size: 1MB                                              │   │
│  └────────────────────────────────┬────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [4] CREATE GUIDANCE TASK                                         │   │
│  │     - task_id, title, description                                │   │
│  │     - priority, assigned_to                                      │   │
│  │     - error_transcript_id                                        │   │
│  └────────────────────────────────┬────────────────────────────────┘   │
│                                   │                                     │
│                                   ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [5] LOG TO HEALTH REPORT                                         │   │
│  │     - .health/health_report.md                                   │   │
│  │     - Timestamp, severity, summary                               │   │
│  │     - Resolution status                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Tool Categories

| Category | Tools | Description |
|----------|-------|-------------|
| FILE_MANAGEMENT | `read_file`, `write_file`, `list_files` | File operations |
| PROJECT_INFO | `get_project_info`, `diagnose`, `generate_report` | Project queries |
| PIPELINE | `run_writer`, `run_director`, `run_storyboard` | Pipeline execution |
| CONTENT_MODIFICATION | `edit_content`, `regenerate_section` | RAG-powered edits |

### Key Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| Execute Tool | `execute_tool(name, **params)` | Run registered tool |
| Make Decision | `decide(context, options)` | Autonomous decision |
| Get Suggestions | `suggest(context)` | Context-aware recommendations |
| Self-Heal | `heal(error)` | Attempt error recovery |
| Diagnose | `diagnose(scope)` | Run diagnostics |
| Generate Report | `generate_health_report()` | Create health report |

### Integration Points

- **Context Engine**: All operations use context retrieval
- **Dependency Graph**: Triggers regeneration on changes
- **Symbolic Registry**: Parses and validates notation
- **UI Layer**: Provides suggestions and diagnostics
- **Pipelines**: Orchestrates Writer/Director execution

---

## 5. System Integration

### How Systems Work Together

The four core systems are deeply interconnected:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SYSTEM INTEGRATION MAP                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌─────────────────┐                             │
│                         │    OMNIMIND     │                             │
│                         │  (Orchestrator) │                             │
│                         └────────┬────────┘                             │
│                                  │                                      │
│              ┌───────────────────┼───────────────────┐                  │
│              │                   │                   │                  │
│              ▼                   ▼                   ▼                  │
│  ┌───────────────────┐ ┌─────────────────┐ ┌───────────────────┐       │
│  │ SYMBOLIC NOTATION │ │ CONTEXT ENGINE  │ │ DEPENDENCY GRAPH  │       │
│  │  (Query Language) │ │   (Retrieval)   │ │  (Relationships)  │       │
│  └─────────┬─────────┘ └────────┬────────┘ └─────────┬─────────┘       │
│            │                    │                    │                  │
│            └────────────────────┼────────────────────┘                  │
│                                 │                                       │
│                                 ▼                                       │
│                    ┌─────────────────────────┐                          │
│                    │    PROJECT CONTENT      │                          │
│                    │  (pitch, world_bible,   │                          │
│                    │   script, visual_script)│                          │
│                    └─────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Integration Flows

#### 1. Query Flow (User → Content)

```
User Query: "@CHAR_MEI #STORY +relationships"
     │
     ▼
┌─────────────────┐
│ Symbolic Parser │ ──▶ Parse @CHAR_MEI, #STORY, +relationships
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Engine  │ ──▶ Vector search + keyword search + graph traversal
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Result  │ ──▶ Assembled context with budget management
└─────────────────┘
```

#### 2. Pipeline Flow (Writer → Director)

```
pitch.md + world_config.json
     │
     ▼
┌─────────────────┐
│ Writer Pipeline │ ──▶ Generate script.md
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Dependency Graph│ ──▶ Register script node, mark dependents
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│Director Pipeline│ ──▶ Generate visual_script.md
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Engine  │ ──▶ Index new content
└─────────────────┘
```

#### 3. Self-Healing Flow (Error → Recovery)

```
Error Detected
     │
     ▼
┌─────────────────┐
│ Error Handoff   │ ──▶ Generate transcript, cache, create task
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Self Healer     │ ──▶ Pattern match, attempt fix
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Dependency Graph│ ──▶ Mark affected nodes for regeneration
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Regen Queue     │ ──▶ Priority-based regeneration
└─────────────────┘
```


### Cross-System Dependencies

| System | Depends On | Provides To |
|--------|------------|-------------|
| **Context Engine** | Dependency Graph, Tag Registry | OmniMind, Pipelines |
| **Dependency Graph** | - | Context Engine, Propagation Engine |
| **Symbolic Notation** | Notation Library | Context Engine, OmniMind |
| **OmniMind** | Context Engine, Symbolic Notation, Dependency Graph | UI, Pipelines |

### Shared Data Structures

| Structure | Used By | Purpose |
|-----------|---------|---------|
| `ContextQuery` | Context Engine, OmniMind | Query specification |
| `ContextResult` | Context Engine, OmniMind | Retrieval results |
| `NodeType` | Dependency Graph, Context Engine | Entity classification |
| `EdgeType` | Dependency Graph | Relationship types |
| `ErrorTranscript` | Error Handoff, Vector Cache | Error context |
| `GuidanceTask` | Error Handoff, OmniMind | Task for resolution |

---

## 6. Data Flow Diagrams

### Complete System Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE SYSTEM DATA FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                                 USER INPUT                                       │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │    │
│  │  │ pitch.md    │  │ style notes │  │ UI actions  │  │ symbolic queries        │ │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │    │
│  └─────────┼────────────────┼────────────────┼─────────────────────┼───────────────┘    │
│            │                │                │                     │                     │
│            └────────────────┴────────────────┴─────────────────────┘                     │
│                                              │                                           │
│                                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                              OMNIMIND LAYER                                      │    │
│  │                                                                                  │    │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │    │
│  │  │ Symbolic    │────▶│ Tool        │────▶│ Decision    │────▶│ Suggestion  │    │    │
│  │  │ Parser      │     │ Executor    │     │ Engine      │     │ Engine      │    │    │
│  │  └─────────────┘     └──────┬──────┘     └─────────────┘     └─────────────┘    │    │
│  │                             │                                                    │    │
│  └─────────────────────────────┼────────────────────────────────────────────────────┘    │
│                                │                                                         │
│                                ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                           CONTEXT & GRAPH LAYER                                  │    │
│  │                                                                                  │    │
│  │  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐       │    │
│  │  │        CONTEXT ENGINE           │  │       DEPENDENCY GRAPH          │       │    │
│  │  │  ┌───────────┐ ┌───────────┐    │  │  ┌───────────┐ ┌───────────┐    │       │    │
│  │  │  │ Vector    │ │ Keyword   │    │  │  │ Nodes     │ │ Edges     │    │       │    │
│  │  │  │ Store     │ │ Index     │    │  │  │           │ │           │    │       │    │
│  │  │  └───────────┘ └───────────┘    │  │  └───────────┘ └───────────┘    │       │    │
│  │  │  ┌───────────┐ ┌───────────┐    │  │  ┌───────────┐ ┌───────────┐    │       │    │
│  │  │  │ Tag       │ │ Context   │    │  │  │ Propagate │ │ Regen     │    │       │    │
│  │  │  │ Registry  │ │ Assembler │    │  │  │ Engine    │ │ Queue     │    │       │    │
│  │  │  └───────────┘ └───────────┘    │  │  └───────────┘ └───────────┘    │       │    │
│  │  └─────────────────────────────────┘  └─────────────────────────────────┘       │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                │                                                         │
│                                ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                            PIPELINE LAYER                                        │    │
│  │                                                                                  │    │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │    │
│  │  │ World Bible │────▶│ Writer      │────▶│ Director    │────▶│ Storyboard  │    │    │
│  │  │ Pipeline    │     │ Pipeline    │     │ Pipeline    │     │ Pipeline    │    │    │
│  │  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘    │    │
│  │         │                   │                   │                   │            │    │
│  │         ▼                   ▼                   ▼                   ▼            │    │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │    │
│  │  │world_config │     │ script.md   │     │visual_script│     │ prompts     │    │    │
│  │  │   .json     │     │             │     │    .md      │     │             │    │    │
│  │  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                │                                                         │
│                                ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                           SELF-HEALING LAYER                                     │    │
│  │                                                                                  │    │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │    │
│  │  │ Error       │────▶│ Vector      │────▶│ Self        │────▶│ Health      │    │    │
│  │  │ Handoff     │     │ Cache       │     │ Healer      │     │ Logger      │    │    │
│  │  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A: File Location Reference

### Context Engine Files
| File | Purpose |
|------|---------|
| `greenlight/context/context_engine.py` | Main ContextEngine class |
| `greenlight/context/vector_store.py` | FAISS-based vector storage |
| `greenlight/context/keyword_index.py` | Inverted index for keywords |
| `greenlight/context/context_assembler.py` | Budget-aware context assembly |

### Graph Files
| File | Purpose |
|------|---------|
| `greenlight/graph/dependency_graph.py` | NetworkX-based graph |
| `greenlight/graph/propagation_engine.py` | Cascading edit management |
| `greenlight/graph/regeneration_queue.py` | Priority-based regeneration |

### Symbolic Notation Files
| File | Purpose |
|------|---------|
| `greenlight/omni_mind/symbolic_registry.py` | Dynamic symbol learning |
| `greenlight/omni_mind/vector_cache.py` | Weighted vector caching |
| `greenlight/config/notation_patterns.py` | Regex patterns |
| `Agnostic_Core_OS/translators/vector_language.py` | NL ↔ Vector translation |
| `Agnostic_Core_OS/procedural/notation_library.py` | Core notation storage |

### OmniMind Files
| File | Purpose |
|------|---------|
| `greenlight/omni_mind/omni_mind.py` | Main OmniMind class |
| `greenlight/omni_mind/tool_executor.py` | Tool registration/execution |
| `greenlight/omni_mind/decision_engine.py` | Autonomous decisions |
| `greenlight/omni_mind/suggestion_engine.py` | Context-aware suggestions |
| `greenlight/omni_mind/self_healer.py` | Error recovery |
| `greenlight/omni_mind/self_heal_queue.py` | Healing task queue |
| `greenlight/omni_mind/error_handoff.py` | Error transcript management |
| `greenlight/omni_mind/project_health.py` | Health monitoring |

### Agnostic_Core_OS Files
| File | Purpose |
|------|---------|
| `Agnostic_Core_OS/runtime/daemon.py` | Background runtime |
| `Agnostic_Core_OS/runtime/context_engine.py` | Core context operations |
| `Agnostic_Core_OS/runtime/omni_mind.py` | Core OmniMind operations |

---

## Appendix B: Quick Reference

### Symbolic Query Cheat Sheet

```
@CHAR_MEI              # Find character Mei
@LOC_TEAHOUSE          # Find location Teahouse
#WORLD_BIBLE           # Scope to world bible
#STORY                 # Scope to story content
+relationships         # Include relationships
-archived              # Exclude archived
~"warrior spirit"      # Semantic search
>run_writer            # Execute writer pipeline
>diagnose              # Run diagnostics
?"who is protagonist"  # Natural language query
```

### Scene.Frame.Camera Quick Reference

```
1.1.cA                 # Scene 1, Frame 1, Camera A
2.3.cB                 # Scene 2, Frame 3, Camera B
[1.1.cA] (Wide)        # Camera block with shot type
## Scene 1:            # Scene marker
## Beat: scene.1.01    # Beat marker
```

### Vector Weight Quick Reference

```
ACTIVE (+1.0)          # Primary retrieval
ARCHIVED (-0.5)        # Deprioritized
DEPRECATED (-1.0)      # Excluded from search
```

### Error Severity Quick Reference

```
CRITICAL               # Blocks execution
ERROR                  # Needs attention
WARNING                # Potential issue
INFO                   # Informational
```

---

*Documentation generated for Project Greenlight v1.0*
*Last updated: 2025-12-13*
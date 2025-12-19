# 📁 File & Directory Map (Part 2)

> **greenlight/ Package Continued**

---

## 📦 greenlight/ Package Structure (Continued)

```
greenlight/
│
├── 🏷️ tags/                          # TAG SYSTEM
│   ├── consensus_tagger.py           # ConsensusTagger.extract_tags()
│   ├── directional_consensus.py      # DirectionalConsensus (N/E/S/W)
│   ├── spatial_continuity.py         # SpatialContinuity tracking
│   ├── tag_parser.py                 # parse_tag(), extract_tags()
│   ├── tag_registry.py               # TagRegistry.register()
│   ├── tag_reference_system.py       # TagReferenceSystem
│   └── tag_validator.py              # validate_tag_format()
│
├── 📸 references/                    # REFERENCE GENERATION
│   ├── unified_reference_script.py   # UnifiedReferenceScript (MAIN ENTRY)
│   │   ├── generate_character_sheet()
│   │   ├── generate_location_views()
│   │   ├── generate_prop_sheet()
│   │   ├── generate_all_references()
│   │   └── convert_image_to_sheet()
│   ├── reference_manager.py          # ReferenceManager
│   └── reference_watcher.py          # File watching
│
├── 🔮 llm/                           # LLM LAYER
│   ├── api_clients.py                # AnthropicClient, GeminiClient,
│   │                                 # GrokClient, ReplicateClient
│   ├── function_router.py            # FunctionRouter.route()
│   ├── llm_config.py                 # LLMManager, provider classes
│   └── llm_registry.py               # Model registry
│
├── ⚡ core/                          # CORE UTILITIES
│   ├── config.py                     # AppConfig, load_config()
│   ├── constants.py                  # LLMFunction enum, constants
│   ├── exceptions.py                 # Custom exceptions
│   ├── id_system.py                  # generate_id(), parse_id()
│   ├── image_handler.py              # ImageHandler.generate_image()
│   │   ├── generate_image()
│   │   ├── get_style_suffix()
│   │   └── create_blank_image()
│   ├── logging_config.py             # Logging setup
│   ├── storyboard_labeler.py         # Label frames
│   └── thumbnail_manager.py          # Thumbnail generation
│
├── 🎯 patterns/                      # QUALITY PATTERNS
│   ├── assembly.py                   # AssemblyPattern
│   ├── steal_list.py                 # StealListPattern
│   └── quality/
│       ├── quality_orchestrator.py   # QualityOrchestrator
│       ├── anchor_agent.py           # Notation validation
│       ├── coherence_validator.py    # Coherence checking
│       ├── constellation_agent.py    # Tag relationships
│       ├── continuity_weaver.py      # Continuity checking
│       ├── inquisitor_panel.py       # Technical validation
│       ├── mirror_agent.py           # Mirror validation
│       ├── telescope_agent.py        # Full context assembly
│       └── universal_context.py      # Universal context
│
├── 📐 config/                        # INTERNAL CONFIG
│   ├── api_dictionary.py             # Model IDs, symbolic notation
│   │   ├── @LLM_CLAUDE, @LLM_HAIKU
│   │   ├── @LLM_GEMINI, @LLM_GROK
│   │   └── @IMG_SEEDREAM, @IMG_FLUX
│   ├── notation_patterns.py          # Regex patterns for tags
│   └── word_caps.py                  # Word capitalization rules
│
├── 🧿 omni_mind/                     # AUTONOMOUS AI
│   └── (see 07_OMNIMIND_SYSTEM.md)
│
├── 📊 graph/                         # DEPENDENCY GRAPH
│   ├── dependency_graph.py           # DependencyGraph
│   ├── propagation_engine.py         # PropagationEngine
│   └── regeneration_queue.py         # RegenerationQueue
│
├── 🖼️ assets/                        # STATIC ASSETS
│   └── Character_Reference_Template.png
│
└── 🛠️ utils/                         # UTILITIES
    ├── chunk_manager.py              # ChunkManager
    ├── file_utils.py                 # File operations
    └── unicode_utils.py              # Unicode handling
```



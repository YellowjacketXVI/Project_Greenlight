# 📁 File & Directory Map

> **Complete Project Structure** - All Files with Purposes

---

## 🌳 Root Directory

```
Project_Greenlight/
│
├── 🚀 greenlight/                    # MAIN PYTHON PACKAGE
│   ├── __main__.py                   # Entry: py -m greenlight
│   ├── __init__.py                   # Package init
│   └── runtime_integration.py        # Agnostic_Core_OS bridge
│
├── 🌐 web/                           # NEXT.JS FRONTEND
│   └── src/                          # React components
│
├── 🧿 Agnostic_Core_OS/              # BACKEND OS LAYER
│   └── (see 10_AGNOSTIC_CORE_OS.md)
│
├── 📂 projects/                      # USER PROJECTS
│   ├── Beta_Test/
│   ├── New_Test/
│   └── The Orchid's Gambit/
│
├── ⚙️ config/                        # APP CONFIGURATION
│   ├── greenlight_config.json        # Main app config
│   └── camera_shot_library.json      # Camera shot definitions
│
├── 📊 Diagrams/                      # THIS DOCUMENTATION
├── 📚 docs/                          # Design documents
├── 🧪 tests/                         # Test suite
└── 📄 requirements.txt               # Python dependencies
```

---

## 📦 greenlight/ Package Structure

```
greenlight/
│
├── 🔌 api/                           # FASTAPI SERVER
│   ├── main.py                       # FastAPI app, CORS, routes
│   └── routers/
│       ├── projects.py               # GET/POST /projects
│       ├── writer.py                 # POST /writer/run
│       ├── director.py               # POST /director/run
│       ├── images.py                 # POST /images/generate
│       ├── pipelines.py              # GET /pipelines/status
│       └── settings.py               # GET/POST /settings
│
├── ⚙️ pipelines/                     # GENERATION PIPELINES
│   ├── base_pipeline.py              # BasePipeline class
│   ├── story_pipeline.py             # WriterPipeline.run()
│   ├── story_pipeline_v2.py          # V2 implementation
│   ├── story_pipeline_v3.py          # V3 implementation
│   ├── directing_pipeline.py         # DirectorPipeline.run()
│   ├── world_bible_pipeline.py       # WorldBiblePipeline.generate_profiles()
│   ├── quality_pipeline.py           # QualityPipeline.validate()
│   ├── shot_pipeline.py              # ShotPipeline.generate_frames()
│   ├── shot_list_extractor.py        # parse_scenes(), extract_shots()
│   └── procedural_generation.py      # Procedural content gen
│
├── 🤖 agents/                        # LLM AGENTS
│   ├── base_agent.py                 # BaseAgent class
│   ├── agent_pool.py                 # AgentPool management
│   ├── orchestrator.py               # AgentOrchestrator
│   ├── collaboration.py              # Multi-agent collaboration
│   ├── prompts.py                    # AgentPromptLibrary
│   ├── prose_agent.py                # ProseAgent.generate()
│   ├── scene_outline_agent.py        # SceneOutlineAgent
│   ├── beat_extractor.py             # BeatExtractor
│   ├── dialogue_consensus.py         # DialogueConsensus
│   ├── brainstorm_agents.py          # Brainstorming agents
│   ├── assembly_agents.py            # Assembly agents
│   ├── reference_prompt_agent.py     # build_character_prompt()
│   ├── profile_template_agent.py     # analyze_image()
│   ├── shot_list_validator.py        # validate_shots()
│   ├── steal_list_judge.py           # StealListJudge
│   └── task_translator.py            # TaskTranslator
│
├── 🧠 context/                       # CONTEXT ENGINE
│   ├── context_engine.py             # ContextEngine.get_world_style()
│   ├── context_assembler.py          # assemble_context()
│   ├── context_compiler.py           # compile_for_llm()
│   ├── agent_context_delivery.py     # inject_context()
│   ├── vector_store.py               # VectorStore
│   ├── keyword_index.py              # KeywordIndex
│   └── thread_tracker.py             # ThreadTracker
```



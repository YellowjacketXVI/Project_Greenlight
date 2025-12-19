# 🏗️ System Overview

> **Project Greenlight** - Complete Architecture at a Glance

---

```mermaid
flowchart LR
    subgraph ENTRY["🚀 ENTRY"]
        A1["__main__.py"]
        A2["api/main.py<br/>FastAPI Server"]
        A3["web/<br/>Next.js UI"]
    end

    subgraph FRONTEND["🖥️ WEB UI"]
        B1["workspace.tsx"]
        B2["sidebar.tsx"]
        B3["views/*.tsx"]
        B4["modals/*.tsx"]
    end

    subgraph API["🔌 API ROUTERS"]
        C1["projects.py"]
        C2["writer.py"]
        C3["director.py"]
        C4["images.py"]
    end

    subgraph PIPELINES["⚙️ PIPELINES"]
        D1["story_pipeline.py<br/>Writer"]
        D2["directing_pipeline.py<br/>Director"]
        D3["world_bible_pipeline.py"]
        D4["quality_pipeline.py"]
    end

    subgraph AGENTS["🤖 AGENTS"]
        E1["base_agent.py"]
        E2["prose_agent.py"]
        E3["collaboration.py"]
        E4["prompts.py"]
    end

    subgraph CONTEXT["🧠 CONTEXT"]
        F1["context_engine.py"]
        F2["vector_store.py"]
        F3["tag_registry.py"]
    end

    subgraph LLM["🔮 LLM"]
        G1["api_clients.py<br/>Anthropic/Gemini/Grok"]
        G2["function_router.py"]
        G3["api_dictionary.py"]
    end

    subgraph CORE["⚡ CORE"]
        H1["image_handler.py"]
        H2["config.py"]
        H3["id_system.py"]
    end

    subgraph OMNIMIND["🧿 OMNIMIND"]
        I1["omni_mind_core.py"]
        I2["backdoor.py"]
        I3["self_healer.py"]
    end

    A1 --> A2
    A3 --> API
    A2 --> API
    
    API --> PIPELINES
    PIPELINES --> AGENTS
    AGENTS --> LLM
    PIPELINES --> CONTEXT
    
    LLM --> G1
    CONTEXT --> F2
    
    CORE --> G1
    OMNIMIND --> PIPELINES
    OMNIMIND --> LLM
```

---

## 📋 Layer Responsibilities

| Layer | Files | Purpose |
|-------|-------|---------|
| **Entry** | `__main__.py`, `api/main.py` | Application bootstrap, FastAPI server |
| **Web UI** | `web/src/components/*` | React/Next.js frontend interface |
| **API** | `greenlight/api/routers/*` | REST endpoints for frontend |
| **Pipelines** | `greenlight/pipelines/*` | Orchestrate multi-step generation |
| **Agents** | `greenlight/agents/*` | Individual LLM-powered workers |
| **Context** | `greenlight/context/*` | World data and tag management |
| **LLM** | `greenlight/llm/*` | API clients and routing |
| **Core** | `greenlight/core/*` | Config, utilities, image handling |
| **OmniMind** | `greenlight/omni_mind/*` | Autonomous AI assistant |

---

## 🔑 Key Paths

```
C:/Users/Nikoles/Documents/Project_Greenlight/
├── greenlight/          # Main Python package
├── web/                 # Next.js frontend
├── Agnostic_Core_OS/    # Backend OS layer
├── projects/            # User projects
├── config/              # App configuration
└── Diagrams/            # This documentation
```



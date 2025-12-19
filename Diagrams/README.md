# 📊 Project Greenlight - Visual Architecture Guide

> **Print-Ready Documentation** | Last Updated: December 2024

---

## 📁 Diagram Index

| File | Description | Print Pages |
|------|-------------|-------------|
| [01_SYSTEM_OVERVIEW.md](01_SYSTEM_OVERVIEW.md) | High-level system architecture | 1 page |
| [02_PIPELINE_FLOW.md](02_PIPELINE_FLOW.md) | End-to-end pipeline data flow | 1 page |
| [03_FILE_DIRECTORY_MAP.md](03_FILE_DIRECTORY_MAP.md) | Complete file tree (Part 1) | 1 page |
| [03_FILE_DIRECTORY_MAP_PART2.md](03_FILE_DIRECTORY_MAP_PART2.md) | Complete file tree (Part 2) | 1 page |
| [04_AGENTS_REFERENCE.md](04_AGENTS_REFERENCE.md) | All agents with functions | 1 page |
| [05_LLM_LAYER.md](05_LLM_LAYER.md) | LLM routing and API clients | 1 page |
| [06_CONTEXT_ENGINE.md](06_CONTEXT_ENGINE.md) | Context and tag system | 1 page |
| [07_OMNIMIND_SYSTEM.md](07_OMNIMIND_SYSTEM.md) | Autonomous AI assistant | 1 page |
| [08_WEB_UI_COMPONENTS.md](08_WEB_UI_COMPONENTS.md) | Frontend architecture | 1 page |
| [09_REFERENCE_GENERATION.md](09_REFERENCE_GENERATION.md) | Image reference pipeline | 1 page |
| [10_AGNOSTIC_CORE_OS.md](10_AGNOSTIC_CORE_OS.md) | Backend OS layer | 1 page |
| [11_QUALITY_PATTERNS.md](11_QUALITY_PATTERNS.md) | Validation & assembly agents | 1 page |
| [12_PROJECT_FILES.md](12_PROJECT_FILES.md) | Per-project file structure | 1 page |
| [13_QUICK_REFERENCE_CARD.md](13_QUICK_REFERENCE_CARD.md) | Essential commands & paths | 1 page |

---

## 🎯 Quick Reference

### Entry Points
```
py -m greenlight          →  __main__.py  →  api/main.py (FastAPI)
web/                      →  Next.js frontend on port 3000
backdoor port 19847       →  OmniMind autonomous commands
```

### Main Data Flow
```
pitch.md  →  Writer  →  script.md + world_config.json
                ↓
          Director  →  visual_script.json
                ↓
          References →  references/{TAG}/
                ↓
          Storyboard →  storyboard_output/
```

### Tag Notation
```
[CHAR_NAME]     Character tags
[LOC_NAME]      Location tags
[PROP_NAME]     Prop tags
[CONCEPT_NAME]  Concept tags
[EVENT_NAME]    Event tags
[ENV_NAME]      Environment tags
```

### Scene.Frame.Camera Notation
```
1.2.cA  =  Scene 1, Frame 2, Camera A
[1.2.cA] (Wide)
cA. SHOT_DESCRIPTION. prompt_content...
```

---

## 🖨️ Printing Instructions

1. Open each `.md` file in VS Code or GitHub
2. Use browser print (Ctrl+P) with landscape orientation
3. Enable "Background graphics" for diagram colors
4. Recommended: Print to PDF first, then physical

---

## 🔧 Viewing Diagrams

Mermaid diagrams render automatically in:
- ✅ GitHub
- ✅ VS Code (with Mermaid extension)
- ✅ GitLab
- ✅ Obsidian
- ✅ [mermaid.live](https://mermaid.live)



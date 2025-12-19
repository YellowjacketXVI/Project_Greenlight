# 🎴 Quick Reference Card

> **Print This Page** - Essential Commands & Paths

---

## 🚀 Starting the Application

```bash
# Start backend (FastAPI)
py -m greenlight

# Start frontend (Next.js)
cd web && npm run dev

# Run tests
py -m pytest tests/ -v
```

---

## 📁 Key File Locations

| What | Path |
|------|------|
| **Entry Point** | `greenlight/__main__.py` |
| **FastAPI Server** | `greenlight/api/main.py` |
| **Writer Pipeline** | `greenlight/pipelines/story_pipeline.py` |
| **Director Pipeline** | `greenlight/pipelines/directing_pipeline.py` |
| **Image Handler** | `greenlight/core/image_handler.py` |
| **Context Engine** | `greenlight/context/context_engine.py` |
| **Reference Script** | `greenlight/references/unified_reference_script.py` |
| **OmniMind Core** | `greenlight/omni_mind/omni_mind_core.py` |
| **API Dictionary** | `greenlight/config/api_dictionary.py` |
| **Prompt Library** | `greenlight/agents/prompts.py` |

---

## 🏷️ Tag Notation

```
[CHAR_NAME]     Characters
[LOC_NAME]      Locations
[PROP_NAME]     Props
[CONCEPT_NAME]  Concepts
[EVENT_NAME]    Events
[ENV_NAME]      Environment
```

---

## 📐 Scene.Frame.Camera

```
1.2.cA = Scene 1, Frame 2, Camera A

[1.2.cA] (Wide)
cA. SHOT_DESCRIPTION. prompt...
```

---

## 🤖 Model Symbols

| Symbol | Model | Use |
|--------|-------|-----|
| `@LLM_CLAUDE` | claude-sonnet-4-5 | Assembly, World Building |
| `@LLM_HAIKU` | claude-3-5-haiku | Consensus Voting |
| `@LLM_GEMINI` | gemini-2.5-flash | OmniMind Background |
| `@LLM_GROK` | grok-4 | Content Fallback |
| `@IMG_SEEDREAM` | seedream-4.5 | Image Generation |

---

## 🔌 API Endpoints

```
GET  /api/projects          List projects
POST /api/projects          Create project
POST /api/writer/run        Run Writer pipeline
POST /api/director/run      Run Director pipeline
POST /api/images/generate   Generate images
GET  /api/pipelines/status  Pipeline status
```

---

## 🧿 OmniMind Backdoor (Port 19847)

```python
from greenlight.omni_mind.backdoor import BackdoorClient

client = BackdoorClient()
client.run_e2e_pipeline(dry_run=True)
client.generate_reference_images()
client.get_e2e_status()
```

---

## 📂 Project Structure

```
projects/{name}/
├── pitch.md              # Input
├── world_config.json     # World data
├── scripts/script.md     # Script output
├── visual_script.json    # Director output
├── references/           # Reference images
└── storyboard_output/    # Final frames
```

---

## 🔧 Common Commands

```bash
# Test E2E pipeline
py test_e2e_tools.py --test e2e

# Test reference generation
py test_reference_prompts.py

# Run specific test
py -m pytest tests/test_pipelines/ -v
```



# 📸 Reference Generation

> **Unified Reference Script** - Image Reference Pipeline

---

```mermaid
flowchart LR
    subgraph INPUT["📥 INPUT"]
        I1["world_config.json<br/>Character/Location/Prop data"]
        I2["Uploaded Image<br/>(optional)"]
    end

    subgraph UNIFIED["📸 UNIFIED REFERENCE SCRIPT<br/>unified_reference_script.py"]
        U1["generate_character_sheet()<br/>━━━━━━━━━━━━━━<br/>• Read character profile<br/>• Build visual prompt<br/>• Generate sheet image"]
        U2["generate_location_views()<br/>━━━━━━━━━━━━━━<br/>• Read location profile<br/>• Generate N→E→S→W<br/>• 4 directional views"]
        U3["generate_prop_sheet()<br/>━━━━━━━━━━━━━━<br/>• Read prop profile<br/>• Build visual prompt<br/>• Generate sheet image"]
        U4["generate_all_references()<br/>━━━━━━━━━━━━━━<br/>• Batch all characters<br/>• Batch all locations<br/>• Batch all props"]
        U5["convert_image_to_sheet()<br/>━━━━━━━━━━━━━━<br/>• Analyze uploaded image<br/>• Update world_config<br/>• Generate sheet"]
    end

    subgraph AGENTS["🤖 AGENTS"]
        A1["reference_prompt_agent.py<br/>━━━━━━━━━━━━━━<br/>ReferencePromptAgent<br/>• build_character_prompt()<br/>• build_location_prompt()<br/>• build_prop_prompt()"]
        A2["profile_template_agent.py<br/>━━━━━━━━━━━━━━<br/>ProfileTemplateAgent<br/>• analyze_image()<br/>• extract_features()<br/>• map_to_profile()"]
    end

    subgraph IMAGE["🎨 IMAGE GENERATION<br/>image_handler.py"]
        IM["ImageHandler<br/>━━━━━━━━━━━━━━<br/>• generate_image()<br/>• get_style_suffix()<br/>• create_blank_image()<br/><br/>Seedream 4.5<br/>Blank-First Method"]
    end

    subgraph OUTPUT["🖼️ OUTPUT"]
        O1["references/CHAR_*/sheet.png"]
        O2["references/LOC_*/north.png<br/>references/LOC_*/east.png<br/>references/LOC_*/south.png<br/>references/LOC_*/west.png"]
        O3["references/PROP_*/sheet.png"]
    end

    INPUT --> UNIFIED
    UNIFIED --> AGENTS
    AGENTS --> IMAGE
    IMAGE --> OUTPUT
    
    U1 --> A1
    U2 --> A1
    U3 --> A1
    U5 --> A2
```

---

## 📋 Method Reference

| Method | Purpose | Input | Output |
|--------|---------|-------|--------|
| `generate_character_sheet(tag)` | Single character sheet | `[CHAR_NAME]` | `references/CHAR_NAME/sheet.png` |
| `generate_character_from_image(tag, path)` | Analyze image → sheet | Tag + image path | Updated profile + sheet |
| `generate_location_views(tag)` | 4 directional views | `[LOC_NAME]` | N/E/S/W images |
| `generate_prop_sheet(tag)` | Single prop sheet | `[PROP_NAME]` | `references/PROP_NAME/sheet.png` |
| `generate_all_character_sheets()` | Batch all characters | - | All character sheets |
| `generate_all_location_views()` | Batch all locations | - | All location views |
| `generate_all_prop_sheets()` | Batch all props | - | All prop sheets |
| `generate_all_references()` | Everything | - | All references |
| `convert_image_to_sheet(tag, path)` | Image → sheet | Tag + image | Sheet from image |
| `get_reference_status(tag)` | Check status | Tag | Has sheet/views? |

---

## 🎨 Seedream Blank-First Method

```
1. Create blank image at 16:9 2K resolution
2. Insert blank as FIRST image input
3. Add reference images AFTER blank
4. Generate with style suffix from world_config.json
```

---

## 📂 Output Directory Structure

```
projects/{project}/references/
├── CHAR_PROTAGONIST/
│   ├── sheet.png           # Character reference sheet
│   └── key_reference.png   # Starred/key image
├── LOC_PALACE/
│   ├── north.png           # North view
│   ├── east.png            # East view
│   ├── south.png           # South view
│   └── west.png            # West view
└── PROP_SWORD/
    └── sheet.png           # Prop reference sheet
```



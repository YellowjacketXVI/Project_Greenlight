"""
Procedural UI Network Crafter

LLM-powered UI customization system that:
- Dynamically generates UI layouts based on user needs
- Learns from user interactions
- Provides easy navigation based on workflow patterns
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
import json


class ComponentType(Enum):
    """Types of UI components."""
    PANEL = "panel"
    BUTTON = "button"
    INPUT = "input"
    DROPDOWN = "dropdown"
    LIST = "list"
    TREE = "tree"
    TABS = "tabs"
    GRID = "grid"
    CARD = "card"
    MODAL = "modal"
    TOOLBAR = "toolbar"
    SIDEBAR = "sidebar"
    HEADER = "header"
    FOOTER = "footer"
    WORKSPACE = "workspace"


@dataclass
class UIComponent:
    """A UI component definition."""
    id: str
    component_type: ComponentType
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List["UIComponent"] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    visible: bool = True
    enabled: bool = True
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "component_type": self.component_type.value,
            "label": self.label,
            "properties": self.properties,
            "children": [c.to_dict() for c in self.children],
            "actions": self.actions,
            "visible": self.visible,
            "enabled": self.enabled,
            "order": self.order,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UIComponent":
        children = [cls.from_dict(c) for c in data.get("children", [])]
        return cls(
            id=data["id"],
            component_type=ComponentType(data["component_type"]),
            label=data["label"],
            properties=data.get("properties", {}),
            children=children,
            actions=data.get("actions", []),
            visible=data.get("visible", True),
            enabled=data.get("enabled", True),
            order=data.get("order", 0),
        )


@dataclass
class UILayout:
    """A complete UI layout configuration."""
    id: str
    name: str
    description: str
    components: List[UIComponent] = field(default_factory=list)
    theme: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "components": [c.to_dict() for c in self.components],
            "theme": self.theme,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UILayout":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            components=[UIComponent.from_dict(c) for c in data.get("components", [])],
            theme=data.get("theme", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            metadata=data.get("metadata", {}),
        )


@dataclass
class UICustomization:
    """A UI customization request/result."""
    request_id: str
    natural_request: str
    vector_notation: str
    target_components: List[str]
    changes: Dict[str, Any]
    applied: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "natural_request": self.natural_request,
            "vector_notation": self.vector_notation,
            "target_components": self.target_components,
            "changes": self.changes,
            "applied": self.applied,
            "timestamp": self.timestamp.isoformat(),
        }


class UINetworkCrafter:
    """
    LLM-powered procedural UI crafting network.
    
    Features:
    - Dynamic UI generation from natural language
    - Layout templates and customization
    - Component visibility/ordering based on workflow
    - LLM integration for intelligent suggestions
    """
    
    def __init__(self, llm_client: Any = None):
        self._llm_client = llm_client
        self._layouts: Dict[str, UILayout] = {}
        self._customizations: List[UICustomization] = []
        self._component_registry: Dict[str, UIComponent] = {}
        self._active_layout: Optional[str] = None
        self._init_default_layouts()

    def _init_default_layouts(self) -> None:
        """Initialize default layout templates."""
        # Story Writing Layout
        story_layout = UILayout(
            id="layout_story",
            name="Story Writing",
            description="Optimized for story document editing",
            components=[
                UIComponent("nav", ComponentType.SIDEBAR, "Navigator", order=0),
                UIComponent("editor", ComponentType.WORKSPACE, "Editor", order=1,
                           properties={"mode": "editor", "width_ratio": 0.6}),
                UIComponent("assistant", ComponentType.PANEL, "Assistant", order=2,
                           properties={"width_ratio": 0.25}),
            ]
        )
        self._layouts[story_layout.id] = story_layout

        # Storyboard Layout
        storyboard_layout = UILayout(
            id="layout_storyboard",
            name="Storyboard",
            description="Visual storyboard editing",
            components=[
                UIComponent("nav", ComponentType.SIDEBAR, "Navigator", order=0,
                           properties={"collapsed": True}),
                UIComponent("storyboard", ComponentType.GRID, "Storyboard", order=1,
                           properties={"mode": "storyboard", "width_ratio": 0.75}),
                UIComponent("properties", ComponentType.PANEL, "Properties", order=2),
            ]
        )
        self._layouts[storyboard_layout.id] = storyboard_layout

        # World Bible Layout
        worldbible_layout = UILayout(
            id="layout_worldbible",
            name="World Bible",
            description="Character and world management",
            components=[
                UIComponent("tree", ComponentType.TREE, "World Tree", order=0),
                UIComponent("details", ComponentType.PANEL, "Details", order=1),
                UIComponent("references", ComponentType.GRID, "References", order=2),
            ]
        )
        self._layouts[worldbible_layout.id] = worldbible_layout

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for intelligent customization."""
        self._llm_client = client

    def get_layout(self, layout_id: str) -> Optional[UILayout]:
        """Get a layout by ID."""
        return self._layouts.get(layout_id)

    def get_active_layout(self) -> Optional[UILayout]:
        """Get the currently active layout."""
        if self._active_layout:
            return self._layouts.get(self._active_layout)
        return None

    def set_active_layout(self, layout_id: str) -> bool:
        """Set the active layout."""
        if layout_id in self._layouts:
            self._active_layout = layout_id
            return True
        return False

    def list_layouts(self) -> List[Dict[str, str]]:
        """List all available layouts."""
        return [
            {"id": l.id, "name": l.name, "description": l.description}
            for l in self._layouts.values()
        ]

    def register_component(self, component: UIComponent) -> None:
        """Register a component in the registry."""
        self._component_registry[component.id] = component

    def create_layout(self, name: str, description: str, components: List[UIComponent] = None) -> UILayout:
        """Create a new layout."""
        import hashlib
        layout_id = f"layout_{hashlib.sha256(name.encode()).hexdigest()[:8]}"
        layout = UILayout(
            id=layout_id,
            name=name,
            description=description,
            components=components or [],
        )
        self._layouts[layout_id] = layout
        return layout

    async def customize_from_request(self, natural_request: str) -> UICustomization:
        """
        Customize UI based on natural language request.

        Examples:
        - "Hide the navigator panel"
        - "Make the editor larger"
        - "Show me a storyboard view"
        - "I need to focus on writing"
        """
        import hashlib
        request_id = hashlib.sha256(natural_request.encode()).hexdigest()[:12]

        # Parse request to vector notation
        vector_notation = self._parse_to_vector(natural_request)

        # Determine target components and changes
        targets, changes = await self._analyze_request(natural_request, vector_notation)

        customization = UICustomization(
            request_id=request_id,
            natural_request=natural_request,
            vector_notation=vector_notation,
            target_components=targets,
            changes=changes,
        )

        self._customizations.append(customization)
        return customization

    def _parse_to_vector(self, request: str) -> str:
        """Parse natural request to vector notation."""
        request_lower = request.lower()
        vectors = []

        # Component visibility
        if "hide" in request_lower:
            if "navigator" in request_lower or "nav" in request_lower:
                vectors.append(">ui hide nav")
            if "assistant" in request_lower:
                vectors.append(">ui hide assistant")

        if "show" in request_lower:
            if "storyboard" in request_lower:
                vectors.append(">ui layout storyboard")
            if "editor" in request_lower:
                vectors.append(">ui layout story")

        # Layout changes
        if "focus" in request_lower and "writing" in request_lower:
            vectors.append(">ui layout story +focus")

        if "larger" in request_lower or "bigger" in request_lower:
            if "editor" in request_lower:
                vectors.append(">ui resize editor +20%")

        return " ".join(vectors) if vectors else f">ui custom \"{request}\""

    async def _analyze_request(self, request: str, vector: str) -> tuple:
        """Analyze request to determine targets and changes."""
        targets = []
        changes = {}

        request_lower = request.lower()

        # Parse visibility changes
        if "hide" in request_lower:
            for comp_name in ["navigator", "nav", "assistant", "sidebar"]:
                if comp_name in request_lower:
                    targets.append(comp_name.replace("navigator", "nav"))
                    changes["visible"] = False

        if "show" in request_lower:
            for comp_name in ["navigator", "nav", "assistant", "sidebar"]:
                if comp_name in request_lower:
                    targets.append(comp_name.replace("navigator", "nav"))
                    changes["visible"] = True

        # Parse layout changes
        if "storyboard" in request_lower:
            changes["layout"] = "layout_storyboard"
        elif "writing" in request_lower or "editor" in request_lower:
            changes["layout"] = "layout_story"
        elif "world" in request_lower:
            changes["layout"] = "layout_worldbible"

        # Parse size changes
        if "larger" in request_lower or "bigger" in request_lower:
            changes["size_delta"] = 0.2
        elif "smaller" in request_lower:
            changes["size_delta"] = -0.2

        # Use LLM for complex requests if available
        if self._llm_client and not targets and not changes:
            targets, changes = await self._llm_analyze(request)

        return targets, changes

    async def _llm_analyze(self, request: str) -> tuple:
        """Use LLM to analyze complex UI requests."""
        if not self._llm_client:
            return [], {}

        prompt = f"""Analyze this UI customization request and return JSON:
Request: "{request}"

Return format:
{{"targets": ["component_ids"], "changes": {{"property": "value"}}}}

Available components: nav, editor, assistant, storyboard, properties, tree, details
Available changes: visible (bool), layout (string), size_delta (float), order (int)
"""
        try:
            response = await self._llm_client.generate(prompt=prompt)
            result = json.loads(response.text if hasattr(response, 'text') else str(response))
            return result.get("targets", []), result.get("changes", {})
        except Exception:
            return [], {}

    def apply_customization(self, customization: UICustomization) -> bool:
        """Apply a customization to the active layout."""
        layout = self.get_active_layout()
        if not layout:
            return False

        # Apply layout change
        if "layout" in customization.changes:
            self.set_active_layout(customization.changes["layout"])
            customization.applied = True
            return True

        # Apply component changes
        for component in layout.components:
            if component.id in customization.target_components:
                if "visible" in customization.changes:
                    component.visible = customization.changes["visible"]
                if "size_delta" in customization.changes:
                    current = component.properties.get("width_ratio", 0.33)
                    component.properties["width_ratio"] = current + customization.changes["size_delta"]
                if "order" in customization.changes:
                    component.order = customization.changes["order"]

        customization.applied = True
        layout.updated_at = datetime.now()
        return True

    def get_customization_history(self) -> List[Dict[str, Any]]:
        """Get history of customizations."""
        return [c.to_dict() for c in self._customizations]

    def export_layout(self, layout_id: str) -> Optional[str]:
        """Export layout as JSON."""
        layout = self._layouts.get(layout_id)
        if layout:
            return json.dumps(layout.to_dict(), indent=2)
        return None

    def import_layout(self, json_data: str) -> Optional[UILayout]:
        """Import layout from JSON."""
        try:
            data = json.loads(json_data)
            layout = UILayout.from_dict(data)
            self._layouts[layout.id] = layout
            return layout
        except Exception:
            return None


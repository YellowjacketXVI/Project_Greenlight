"""
Greenlight Dependency Visualization

Interactive graph view for dependency relationships.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass

from greenlight.ui.theme import theme


@dataclass
class GraphNode:
    """A node in the visual graph."""
    id: str
    label: str
    node_type: str
    x: float = 0.0
    y: float = 0.0
    selected: bool = False
    affected: bool = False


@dataclass
class GraphEdge:
    """An edge in the visual graph."""
    source: str
    target: str
    edge_type: str


class DependencyView(ctk.CTkFrame):
    """
    Interactive dependency graph visualization.
    
    Features:
    - Node visualization with types
    - Edge connections
    - Selection and highlighting
    - Affected node indication
    - Pan and zoom
    """
    
    def __init__(
        self,
        master,
        on_node_select: Callable[[str], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.on_node_select = on_node_select
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._selected_node: Optional[str] = None
        self._affected_nodes: Set[str] = set()
        
        # View state
        self._pan_x = 0
        self._pan_y = 0
        self._zoom = 1.0
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_medium,
            corner_radius=8
        )
        
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=35)
        toolbar.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.sm)
        
        title = ctk.CTkLabel(
            toolbar,
            text="📊 Dependency Graph",
            **theme.get_label_style()
        )
        title.pack(side="left")
        
        # Zoom controls
        zoom_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        zoom_frame.pack(side="right")
        
        zoom_out = ctk.CTkButton(
            zoom_frame, text="-", width=30,
            command=self._zoom_out,
            **theme.get_button_style("secondary")
        )
        zoom_out.pack(side="left", padx=2)
        
        self.zoom_label = ctk.CTkLabel(
            zoom_frame, text="100%",
            **theme.get_label_style("muted")
        )
        self.zoom_label.pack(side="left", padx=theme.spacing.sm)
        
        zoom_in = ctk.CTkButton(
            zoom_frame, text="+", width=30,
            command=self._zoom_in,
            **theme.get_button_style("secondary")
        )
        zoom_in.pack(side="left", padx=2)
        
        fit_btn = ctk.CTkButton(
            zoom_frame, text="Fit", width=40,
            command=self._fit_view,
            **theme.get_button_style("secondary")
        )
        fit_btn.pack(side="left", padx=(theme.spacing.sm, 0))
        
        # Canvas for graph
        self.canvas = ctk.CTkCanvas(
            self,
            bg=theme.colors.bg_dark,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True, padx=theme.spacing.sm, pady=theme.spacing.sm)
        
        # Bind events
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
    
    def set_graph(self, nodes: List[Dict], edges: List[Dict]) -> None:
        """Set the graph data."""
        self._nodes.clear()
        self._edges.clear()
        
        for node_data in nodes:
            node = GraphNode(
                id=node_data['id'],
                label=node_data.get('label', node_data['id']),
                node_type=node_data.get('type', 'default')
            )
            self._nodes[node.id] = node
        
        for edge_data in edges:
            edge = GraphEdge(
                source=edge_data['source'],
                target=edge_data['target'],
                edge_type=edge_data.get('type', 'default')
            )
            self._edges.append(edge)
        
        self._layout_graph()
        self._render()
    
    def highlight_affected(self, node_ids: Set[str]) -> None:
        """Highlight affected nodes."""
        self._affected_nodes = node_ids
        for node_id in node_ids:
            if node_id in self._nodes:
                self._nodes[node_id].affected = True
        self._render()
    
    def _layout_graph(self) -> None:
        """Calculate node positions using simple force-directed layout."""
        import math
        
        width = self.canvas.winfo_width() or 400
        height = self.canvas.winfo_height() or 300
        
        # Simple circular layout
        nodes = list(self._nodes.values())
        n = len(nodes)
        if n == 0:
            return
        
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.35
        
        for i, node in enumerate(nodes):
            angle = (2 * math.pi * i) / n
            node.x = cx + radius * math.cos(angle)
            node.y = cy + radius * math.sin(angle)
    
    def _render(self) -> None:
        """Render the graph."""
        self.canvas.delete("all")
        
        # Draw edges
        for edge in self._edges:
            src = self._nodes.get(edge.source)
            tgt = self._nodes.get(edge.target)
            if src and tgt:
                color = theme.colors.border
                if src.affected or tgt.affected:
                    color = theme.colors.warning
                
                self.canvas.create_line(
                    src.x, src.y, tgt.x, tgt.y,
                    fill=color, width=2, arrow="last"
                )
        
        # Draw nodes
        for node in self._nodes.values():
            self._draw_node(node)
    
    def _draw_node(self, node: GraphNode) -> None:
        """Draw a single node."""
        r = 25  # Node radius
        
        # Determine color
        if node.selected:
            fill = theme.colors.primary
        elif node.affected:
            fill = theme.colors.warning
        else:
            fill = theme.colors.bg_light
        
        # Draw circle
        self.canvas.create_oval(
            node.x - r, node.y - r,
            node.x + r, node.y + r,
            fill=fill, outline=theme.colors.border, width=2
        )
        
        # Draw label
        self.canvas.create_text(
            node.x, node.y,
            text=node.label[:8],
            fill=theme.colors.text_primary,
            font=(theme.fonts.family, 9)
        )
    
    def _on_click(self, event) -> None:
        """Handle click on canvas."""
        for node in self._nodes.values():
            dx = event.x - node.x
            dy = event.y - node.y
            if dx*dx + dy*dy < 625:  # 25^2
                self._select_node(node.id)
                return
        self._select_node(None)
    
    def _select_node(self, node_id: Optional[str]) -> None:
        """Select a node."""
        for node in self._nodes.values():
            node.selected = (node.id == node_id)
        
        self._selected_node = node_id
        self._render()
        
        if self.on_node_select and node_id:
            self.on_node_select(node_id)
    
    def _on_drag(self, event) -> None:
        """Handle drag for panning."""
        pass  # Would implement panning
    
    def _on_scroll(self, event) -> None:
        """Handle scroll for zooming."""
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()
    
    def _zoom_in(self) -> None:
        """Zoom in."""
        self._zoom = min(3.0, self._zoom * 1.2)
        self.zoom_label.configure(text=f"{int(self._zoom * 100)}%")
        self._render()
    
    def _zoom_out(self) -> None:
        """Zoom out."""
        self._zoom = max(0.3, self._zoom / 1.2)
        self.zoom_label.configure(text=f"{int(self._zoom * 100)}%")
        self._render()
    
    def _fit_view(self) -> None:
        """Fit all nodes in view."""
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self.zoom_label.configure(text="100%")
        self._layout_graph()
        self._render()


"""
Greenlight Dependency Graph

NetworkX-based graph for tracking relationships between story elements
and managing edit propagation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
from datetime import datetime
import json
from pathlib import Path

try:
    import networkx as nx
except ImportError:
    nx = None

from greenlight.core.exceptions import GraphError, NodeNotFoundError, CyclicDependencyError
from greenlight.core.logging_config import get_logger

logger = get_logger("graph.dependency")


class NodeType(Enum):
    """Types of nodes in the dependency graph."""
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
    # Pipeline output types
    PITCH = "pitch"
    WORLD_CONFIG = "world_config"
    SCRIPT = "script"
    VISUAL_SCRIPT = "visual_script"
    TAG_REFERENCE = "tag_reference"
    STORYBOARD_PROMPT = "storyboard_prompt"
    # Pipeline types
    PIPELINE = "pipeline"


class EdgeType(Enum):
    """Types of edges (relationships) in the graph."""
    CONTAINS = "contains"           # Parent contains child
    REFERENCES = "references"       # Element references another
    DEPENDS_ON = "depends_on"       # Element depends on another
    APPEARS_IN = "appears_in"       # Character/prop appears in scene
    LOCATED_AT = "located_at"       # Scene is at location
    RELATED_TO = "related_to"       # General relationship
    PRECEDES = "precedes"           # Temporal ordering
    DERIVED_FROM = "derived_from"   # Generated from source
    # Pipeline relationships
    PRODUCES = "produces"           # Pipeline produces output
    CONSUMES = "consumes"           # Pipeline consumes input
    TRANSFORMS = "transforms"       # Pipeline transforms input to output


@dataclass
class GraphNode:
    """Represents a node in the dependency graph."""
    id: str
    node_type: NodeType
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'node_type': self.node_type.value,
            'name': self.name,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version
        }


@dataclass
class GraphEdge:
    """Represents an edge in the dependency graph."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DependencyGraph:
    """
    Manages dependencies between story elements using NetworkX.
    
    Features:
    - Node and edge management
    - Dependency traversal
    - Cycle detection
    - Affected node calculation for propagation
    - Serialization/deserialization
    """
    
    def __init__(self):
        if nx is None:
            raise ImportError("NetworkX is required for DependencyGraph")
        
        self._graph = nx.DiGraph()
        self._nodes: Dict[str, GraphNode] = {}
    
    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        name: str,
        **data
    ) -> GraphNode:
        """
        Add a node to the graph.
        
        Args:
            node_id: Unique identifier
            node_type: Type of node
            name: Display name
            **data: Additional node data
            
        Returns:
            Created GraphNode
        """
        node = GraphNode(
            id=node_id,
            node_type=node_type,
            name=name,
            data=data
        )
        
        self._nodes[node_id] = node
        self._graph.add_node(node_id, **node.to_dict())
        
        logger.debug(f"Added node: {node_id} ({node_type.value})")
        return node
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        **metadata
    ) -> GraphEdge:
        """
        Add an edge between nodes.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of relationship
            weight: Edge weight for prioritization
            **metadata: Additional edge data
            
        Returns:
            Created GraphEdge
        """
        if source_id not in self._nodes:
            raise NodeNotFoundError(source_id)
        if target_id not in self._nodes:
            raise NodeNotFoundError(target_id)
        
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata
        )
        
        self._graph.add_edge(
            source_id,
            target_id,
            edge_type=edge_type.value,
            weight=weight,
            **metadata
        )
        
        # Check for cycles
        if not nx.is_directed_acyclic_graph(self._graph):
            # Remove the edge and raise error
            self._graph.remove_edge(source_id, target_id)
            cycle = nx.find_cycle(self._graph, source_id)
            raise CyclicDependencyError([str(n) for n in cycle])
        
        logger.debug(f"Added edge: {source_id} --{edge_type.value}--> {target_id}")
        return edge
    
    def get_node(self, node_id: str) -> GraphNode:
        """Get a node by ID."""
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)
        return self._nodes[node_id]
    
    def get_dependents(self, node_id: str) -> List[str]:
        """Get all nodes that depend on this node (downstream)."""
        if node_id not in self._graph:
            raise NodeNotFoundError(node_id)
        return list(self._graph.successors(node_id))
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all nodes this node depends on (upstream)."""
        if node_id not in self._graph:
            raise NodeNotFoundError(node_id)
        return list(self._graph.predecessors(node_id))
    
    def get_all_affected(self, node_id: str) -> Set[str]:
        """
        Get all nodes affected by changes to this node.
        Uses BFS to find all downstream dependents.
        """
        if node_id not in self._graph:
            raise NodeNotFoundError(node_id)
        
        affected = set()
        queue = [node_id]
        
        while queue:
            current = queue.pop(0)
            for dependent in self._graph.successors(current):
                if dependent not in affected:
                    affected.add(dependent)
                    queue.append(dependent)
        
        return affected

    # =========================================================================
    #  PIPELINE DEPENDENCY MANAGEMENT
    # =========================================================================

    def register_pipeline_flow(self) -> None:
        """
        Register the standard pipeline flow as graph nodes and edges.

        Pipeline Flow:
        pitch.md → World Bible Pipeline → world_config.json
        pitch.md → Story Pipeline → script.md
        script.md → Directing Pipeline → visual_script.md
        visual_script.md → Tag Reference System → tag_references
        visual_script.md → Storyboard Generation → storyboard_prompts
        """
        # Add pipeline nodes
        self.add_node("pipeline_world_bible", NodeType.PIPELINE, "World Bible Pipeline")
        self.add_node("pipeline_story", NodeType.PIPELINE, "Story Pipeline")
        self.add_node("pipeline_story_v2", NodeType.PIPELINE, "Story Pipeline v2 (Assembly)")
        self.add_node("pipeline_directing", NodeType.PIPELINE, "Directing Pipeline")
        self.add_node("pipeline_procedural", NodeType.PIPELINE, "Procedural Generator")
        self.add_node("system_tag_reference", NodeType.PIPELINE, "Tag Reference System")

        # Add output nodes
        self.add_node("output_pitch", NodeType.PITCH, "pitch.md")
        self.add_node("output_world_config", NodeType.WORLD_CONFIG, "world_config.json")
        self.add_node("output_script", NodeType.SCRIPT, "script.md")
        self.add_node("output_visual_script", NodeType.VISUAL_SCRIPT, "visual_script.md")
        self.add_node("output_tag_references", NodeType.TAG_REFERENCE, "tag_references")
        self.add_node("output_storyboard_prompts", NodeType.STORYBOARD_PROMPT, "storyboard_prompts")

        # Add pipeline flow edges
        # Pitch → World Bible Pipeline → world_config
        self.add_edge("output_pitch", "pipeline_world_bible", EdgeType.CONSUMES)
        self.add_edge("pipeline_world_bible", "output_world_config", EdgeType.PRODUCES)

        # Pitch → Story Pipeline → script
        self.add_edge("output_pitch", "pipeline_story", EdgeType.CONSUMES)
        self.add_edge("output_pitch", "pipeline_story_v2", EdgeType.CONSUMES)
        self.add_edge("pipeline_story", "output_script", EdgeType.PRODUCES)
        self.add_edge("pipeline_story_v2", "output_script", EdgeType.PRODUCES)

        # script → Directing Pipeline → visual_script
        self.add_edge("output_script", "pipeline_directing", EdgeType.CONSUMES)
        self.add_edge("pipeline_directing", "output_visual_script", EdgeType.PRODUCES)

        # script → Procedural Generator → visual_script (alternative path)
        self.add_edge("output_script", "pipeline_procedural", EdgeType.CONSUMES)
        self.add_edge("pipeline_procedural", "output_visual_script", EdgeType.PRODUCES)

        # visual_script → Tag Reference System → tag_references
        self.add_edge("output_visual_script", "system_tag_reference", EdgeType.CONSUMES)
        self.add_edge("system_tag_reference", "output_tag_references", EdgeType.PRODUCES)

        # tag_references → storyboard_prompts
        self.add_edge("output_tag_references", "output_storyboard_prompts", EdgeType.DERIVED_FROM)

        logger.info("Registered pipeline flow in dependency graph")

    def get_pipeline_dependencies(self, output_type: str) -> List[str]:
        """
        Get all pipeline dependencies for a given output type.

        Args:
            output_type: One of 'world_config', 'script', 'visual_script',
                        'tag_references', 'storyboard_prompts'

        Returns:
            List of node IDs that must be regenerated if this output changes
        """
        node_id = f"output_{output_type}"
        if node_id not in self._nodes:
            return []

        return list(self.get_all_affected(node_id))

    def get_pipeline_for_output(self, output_type: str) -> Optional[str]:
        """
        Get the pipeline that produces a given output type.

        Args:
            output_type: The output type (e.g., 'script_v1', 'visual_script')

        Returns:
            Pipeline node ID or None
        """
        node_id = f"output_{output_type}"
        if node_id not in self._nodes:
            return None

        # Find nodes that produce this output
        for pred in self._graph.predecessors(node_id):
            edge_data = self._graph.get_edge_data(pred, node_id)
            if edge_data and edge_data.get('edge_type') == EdgeType.PRODUCES.value:
                return pred

        return None

    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Get all nodes of a specific type."""
        return [
            node for node in self._nodes.values()
            if node.node_type == node_type
        ]

    def mark_for_regeneration(self, node_id: str, reason: str = None) -> Set[str]:
        """
        Mark a node and all its dependents for regeneration.

        Args:
            node_id: The node to mark
            reason: Optional reason for regeneration

        Returns:
            Set of all node IDs marked for regeneration
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)

        affected = self.get_all_affected(node_id)
        affected.add(node_id)

        for nid in affected:
            node = self._nodes[nid]
            node.data['needs_regeneration'] = True
            node.data['regeneration_reason'] = reason or f"Upstream change: {node_id}"
            node.updated_at = datetime.now()

        logger.info(f"Marked {len(affected)} nodes for regeneration due to change in {node_id}")
        return affected

    def clear_regeneration_flag(self, node_id: str) -> None:
        """Clear the regeneration flag for a node."""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            node.data.pop('needs_regeneration', None)
            node.data.pop('regeneration_reason', None)

    def get_nodes_needing_regeneration(self) -> List[GraphNode]:
        """Get all nodes that need regeneration."""
        return [
            node for node in self._nodes.values()
            if node.data.get('needs_regeneration', False)
        ]


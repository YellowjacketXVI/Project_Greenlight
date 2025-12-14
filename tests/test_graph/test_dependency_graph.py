"""
Tests for Dependency Graph Module

Tests for greenlight/graph/dependency_graph.py
"""

import pytest

from greenlight.graph.dependency_graph import (
    DependencyGraph,
    NodeType,
    EdgeType
)


class TestDependencyGraph:
    """Tests for DependencyGraph class."""
    
    def test_create_empty_graph(self):
        """Test creating an empty graph."""
        graph = DependencyGraph()
        
        assert graph is not None
        assert graph.node_count == 0
        assert graph.edge_count == 0
    
    def test_add_node(self):
        """Test adding a node."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY, {"title": "Test Story"})
        
        assert graph.node_count == 1
        assert graph.has_node("story_1")
    
    def test_add_edge(self):
        """Test adding an edge."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        
        assert graph.edge_count == 1
        assert graph.has_edge("story_1", "beat_1")
    
    def test_get_node_data(self):
        """Test getting node data."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY, {"title": "Test Story"})
        
        data = graph.get_node_data("story_1")
        
        assert data is not None
        assert data["title"] == "Test Story"
    
    def test_get_children(self):
        """Test getting child nodes."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_node("beat_2", NodeType.BEAT)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        graph.add_edge("story_1", "beat_2", EdgeType.CONTAINS)
        
        children = graph.get_children("story_1")
        
        assert len(children) == 2
        assert "beat_1" in children
        assert "beat_2" in children
    
    def test_get_parents(self):
        """Test getting parent nodes."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        
        parents = graph.get_parents("beat_1")
        
        assert len(parents) == 1
        assert "story_1" in parents
    
    def test_get_descendants(self):
        """Test getting all descendants."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_node("shot_1", NodeType.SHOT)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        graph.add_edge("beat_1", "shot_1", EdgeType.GENERATES)
        
        descendants = graph.get_descendants("story_1")
        
        assert len(descendants) == 2
        assert "beat_1" in descendants
        assert "shot_1" in descendants
    
    def test_remove_node(self):
        """Test removing a node."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        
        graph.remove_node("beat_1")
        
        assert graph.node_count == 1
        assert not graph.has_node("beat_1")
        assert graph.edge_count == 0
    
    def test_topological_sort(self):
        """Test topological sorting."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_node("shot_1", NodeType.SHOT)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        graph.add_edge("beat_1", "shot_1", EdgeType.GENERATES)
        
        sorted_nodes = graph.topological_sort()
        
        assert sorted_nodes.index("story_1") < sorted_nodes.index("beat_1")
        assert sorted_nodes.index("beat_1") < sorted_nodes.index("shot_1")
    
    def test_detect_cycle(self):
        """Test cycle detection."""
        graph = DependencyGraph()
        
        graph.add_node("a", NodeType.STORY)
        graph.add_node("b", NodeType.BEAT)
        graph.add_node("c", NodeType.SHOT)
        graph.add_edge("a", "b", EdgeType.CONTAINS)
        graph.add_edge("b", "c", EdgeType.GENERATES)
        
        # No cycle
        assert not graph.has_cycle()
        
        # Add cycle
        graph.add_edge("c", "a", EdgeType.REFERENCES)
        
        assert graph.has_cycle()


class TestNodeTypes:
    """Tests for node type handling."""
    
    def test_get_nodes_by_type(self):
        """Test getting nodes by type."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_node("beat_2", NodeType.BEAT)
        graph.add_node("shot_1", NodeType.SHOT)
        
        beats = graph.get_nodes_by_type(NodeType.BEAT)
        
        assert len(beats) == 2
        assert "beat_1" in beats
        assert "beat_2" in beats


class TestEdgeTypes:
    """Tests for edge type handling."""
    
    def test_get_edges_by_type(self):
        """Test getting edges by type."""
        graph = DependencyGraph()
        
        graph.add_node("story_1", NodeType.STORY)
        graph.add_node("beat_1", NodeType.BEAT)
        graph.add_node("char_1", NodeType.CHARACTER)
        graph.add_edge("story_1", "beat_1", EdgeType.CONTAINS)
        graph.add_edge("beat_1", "char_1", EdgeType.REFERENCES)
        
        contains_edges = graph.get_edges_by_type(EdgeType.CONTAINS)
        
        assert len(contains_edges) == 1
        assert ("story_1", "beat_1") in contains_edges


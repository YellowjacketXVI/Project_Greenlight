"""
Pytest Configuration and Fixtures

Shared fixtures for all tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration for testing."""
    return {
        "app_name": "Project Greenlight",
        "version": "2.0.0",
        "llm": {
            "providers": {
                "anthropic": {
                    "api_key": "test-key",
                    "default_model": "claude-sonnet-4-20250514"
                },
                "openai": {
                    "api_key": "test-key",
                    "default_model": "gpt-4"
                }
            }
        }
    }


@pytest.fixture
def sample_tags() -> list:
    """Sample tags for testing."""
    return [
        "[MARCUS]",
        "[ELENA]",
        "[LOC_WAREHOUSE]",
        "[LOC_WAREHOUSE_DIR_N]",
        "[PROP_ARTIFACT]",
        "[CONCEPT_REDEMPTION]",
        "[EVENT_ATTACK]"
    ]


@pytest.fixture
def sample_story_text() -> str:
    """Sample story text with tags."""
    return """
    [MARCUS] enters the [LOC_WAREHOUSE] from the north entrance [LOC_WAREHOUSE_DIR_N].
    He spots [ELENA] near the [PROP_ARTIFACT]. The theme of [CONCEPT_REDEMPTION] 
    is evident as they prepare for the [EVENT_ATTACK].
    """


@pytest.fixture
def sample_graph_nodes() -> list:
    """Sample graph nodes for testing."""
    return [
        {"id": "story_1", "type": "story", "label": "Story 1"},
        {"id": "beat_1", "type": "beat", "label": "Beat 1"},
        {"id": "beat_2", "type": "beat", "label": "Beat 2"},
        {"id": "shot_1", "type": "shot", "label": "Shot 1"},
        {"id": "shot_2", "type": "shot", "label": "Shot 2"},
        {"id": "prompt_1", "type": "prompt", "label": "Prompt 1"},
    ]


@pytest.fixture
def sample_graph_edges() -> list:
    """Sample graph edges for testing."""
    return [
        {"source": "story_1", "target": "beat_1", "type": "contains"},
        {"source": "story_1", "target": "beat_2", "type": "contains"},
        {"source": "beat_1", "target": "shot_1", "type": "generates"},
        {"source": "beat_2", "target": "shot_2", "type": "generates"},
        {"source": "shot_1", "target": "prompt_1", "type": "generates"},
    ]


@pytest.fixture
def sample_world_bible() -> Dict[str, Any]:
    """Sample world bible for testing."""
    return {
        "characters": {
            "MARCUS": {
                "name": "Marcus Kane",
                "role": "protagonist",
                "description": "Former soldier turned scavenger"
            },
            "ELENA": {
                "name": "Elena Voss",
                "role": "ally",
                "description": "Scientist searching for answers"
            }
        },
        "locations": {
            "LOC_WAREHOUSE": {
                "name": "Abandoned Warehouse",
                "description": "Rusted industrial building"
            }
        },
        "props": {
            "PROP_ARTIFACT": {
                "name": "Ancient Artifact",
                "description": "Mysterious glowing object"
            }
        }
    }


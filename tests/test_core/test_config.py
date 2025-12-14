"""
Tests for Configuration Module

Tests for greenlight/core/config.py
"""

import pytest
import json
from pathlib import Path

from greenlight.core.config import (
    GreenlightConfig,
    LLMConfig,
    load_config,
    save_config,
    get_default_config
)


class TestGreenlightConfig:
    """Tests for GreenlightConfig class."""
    
    def test_default_config(self):
        """Test default configuration creation."""
        config = get_default_config()
        
        assert config is not None
        assert config.app_name == "Project Greenlight"
        assert config.version == "2.0.0"
    
    def test_config_from_dict(self, sample_config):
        """Test creating config from dictionary."""
        config = GreenlightConfig.from_dict(sample_config)
        
        assert config.app_name == "Project Greenlight"
        assert config.version == "2.0.0"
    
    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = get_default_config()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert "app_name" in config_dict
        assert "version" in config_dict


class TestLoadSaveConfig:
    """Tests for config loading and saving."""
    
    def test_load_config_from_file(self, temp_dir, sample_config):
        """Test loading config from JSON file."""
        config_path = temp_dir / "test_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(sample_config, f)
        
        config = load_config(str(config_path))
        
        assert config is not None
        assert config.app_name == "Project Greenlight"
    
    def test_load_config_missing_file(self, temp_dir):
        """Test loading config from non-existent file returns default."""
        config_path = temp_dir / "nonexistent.json"
        
        config = load_config(str(config_path))
        
        # Should return default config
        assert config is not None
        assert config.app_name == "Project Greenlight"
    
    def test_save_config(self, temp_dir):
        """Test saving config to file."""
        config = get_default_config()
        config_path = temp_dir / "saved_config.json"
        
        save_config(config, str(config_path))
        
        assert config_path.exists()
        
        with open(config_path) as f:
            saved_data = json.load(f)
        
        assert saved_data["app_name"] == "Project Greenlight"


class TestLLMConfig:
    """Tests for LLM configuration."""
    
    def test_llm_config_creation(self):
        """Test LLM config creation."""
        llm_config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.7
        )
        
        assert llm_config.provider == "anthropic"
        assert llm_config.model == "claude-sonnet-4-20250514"
        assert llm_config.temperature == 0.7
    
    def test_llm_config_defaults(self):
        """Test LLM config default values."""
        llm_config = LLMConfig(
            provider="openai",
            model="gpt-4"
        )
        
        assert llm_config.temperature == 0.7  # Default
        assert llm_config.max_tokens == 4096  # Default


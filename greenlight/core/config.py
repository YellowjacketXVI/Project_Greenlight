"""
Greenlight Configuration Management

Centralized configuration system with JSON loading and validation.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import ConfigurationError, MissingConfigError, InvalidConfigError
from .constants import LLMProvider, LLMFunction


@dataclass
class LLMConfig:
    """Configuration for a specific LLM provider."""
    provider: LLMProvider
    model: str
    api_key_env: str  # Environment variable name for API key
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LLMConfig':
        """Create LLMConfig from dictionary."""
        return cls(
            provider=LLMProvider(data['provider']),
            model=data['model'],
            api_key_env=data['api_key_env'],
            temperature=data.get('temperature', 0.7),
            max_tokens=data.get('max_tokens', 4096),
            timeout=data.get('timeout', 60)
        )


@dataclass
class FunctionLLMMapping:
    """Mapping of functions to their preferred LLM configurations."""
    function: LLMFunction
    primary_config: LLMConfig
    fallback_config: Optional[LLMConfig] = None
    
    @classmethod
    def from_dict(cls, data: dict, llm_configs: Dict[str, LLMConfig]) -> 'FunctionLLMMapping':
        """Create FunctionLLMMapping from dictionary."""
        primary = llm_configs.get(data['primary'])
        if not primary:
            raise InvalidConfigError(f"Unknown LLM config: {data['primary']}")
        
        fallback = None
        if 'fallback' in data:
            fallback = llm_configs.get(data['fallback'])
        
        return cls(
            function=LLMFunction(data['function']),
            primary_config=primary,
            fallback_config=fallback
        )


@dataclass
class UIConfig:
    """UI configuration settings."""
    theme: str = "dark"
    window_width: int = 1600
    window_height: int = 900
    font_family: str = "Segoe UI"
    font_size: int = 11
    panel_ratios: List[float] = field(default_factory=lambda: [0.2, 0.5, 0.3])


@dataclass
class PipelineConfig:
    """Pipeline configuration settings."""
    tag_consensus_threshold: float = 0.8
    max_retries: int = 3
    parallel_agents: int = 5
    chunk_size: int = 2000
    chunk_overlap: int = 200


@dataclass
class GreenlightConfig:
    """Main configuration class for Project Greenlight."""
    
    # Project settings
    project_name: str = "Project Greenlight"
    version: str = "2.0.0"
    
    # Paths
    config_dir: Path = field(default_factory=lambda: Path("config"))
    templates_dir: Path = field(default_factory=lambda: Path("templates"))
    logs_dir: Path = field(default_factory=lambda: Path("logs"))
    
    # LLM configurations
    llm_configs: Dict[str, LLMConfig] = field(default_factory=dict)
    function_mappings: Dict[LLMFunction, FunctionLLMMapping] = field(default_factory=dict)
    
    # Sub-configurations
    ui: UIConfig = field(default_factory=UIConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    
    # Feature flags
    verbose_logging: bool = True
    enable_caching: bool = True
    auto_save: bool = True
    
    def get_llm_for_function(self, function: LLMFunction) -> LLMConfig:
        """Get the LLM configuration for a specific function."""
        mapping = self.function_mappings.get(function)
        if mapping:
            return mapping.primary_config
        # Return first available config as fallback
        if self.llm_configs:
            return next(iter(self.llm_configs.values()))
        raise MissingConfigError(f"No LLM configuration for function: {function.value}")
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GreenlightConfig':
        """Create GreenlightConfig from dictionary."""
        config = cls()
        
        # Basic settings
        config.project_name = data.get('project_name', config.project_name)
        config.version = data.get('version', config.version)
        config.verbose_logging = data.get('verbose_logging', config.verbose_logging)
        config.enable_caching = data.get('enable_caching', config.enable_caching)
        config.auto_save = data.get('auto_save', config.auto_save)
        
        # Paths
        if 'paths' in data:
            paths = data['paths']
            config.config_dir = Path(paths.get('config_dir', 'config'))
            config.templates_dir = Path(paths.get('templates_dir', 'templates'))
            config.logs_dir = Path(paths.get('logs_dir', 'logs'))
        
        # LLM configs
        if 'llm_providers' in data:
            for name, llm_data in data['llm_providers'].items():
                config.llm_configs[name] = LLMConfig.from_dict(llm_data)
        
        # Function mappings
        if 'function_mappings' in data:
            for mapping_data in data['function_mappings']:
                mapping = FunctionLLMMapping.from_dict(mapping_data, config.llm_configs)
                config.function_mappings[mapping.function] = mapping
        
        # UI config
        if 'ui' in data:
            ui_data = data['ui']
            config.ui = UIConfig(
                theme=ui_data.get('theme', 'dark'),
                window_width=ui_data.get('window_width', 1600),
                window_height=ui_data.get('window_height', 900),
                font_family=ui_data.get('font_family', 'Segoe UI'),
                font_size=ui_data.get('font_size', 11),
                panel_ratios=ui_data.get('panel_ratios', [0.2, 0.5, 0.3])
            )
        
        # Pipeline config
        if 'pipeline' in data:
            pipe_data = data['pipeline']
            config.pipeline = PipelineConfig(
                tag_consensus_threshold=pipe_data.get('tag_consensus_threshold', 0.8),
                max_retries=pipe_data.get('max_retries', 3),
                parallel_agents=pipe_data.get('parallel_agents', 5),
                chunk_size=pipe_data.get('chunk_size', 2000),
                chunk_overlap=pipe_data.get('chunk_overlap', 200)
            )
        
        return config


def load_config(config_path: Path = None) -> GreenlightConfig:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to configuration file. If None, uses default.
        
    Returns:
        Loaded GreenlightConfig instance
    """
    if config_path is None:
        config_path = Path("config/greenlight_config.json")
    
    if not config_path.exists():
        # Return default config if file doesn't exist
        return GreenlightConfig()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return GreenlightConfig.from_dict(data)
    except json.JSONDecodeError as e:
        raise InvalidConfigError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load config: {e}")


# Global config instance
_config: Optional[GreenlightConfig] = None


def get_config() -> GreenlightConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: GreenlightConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


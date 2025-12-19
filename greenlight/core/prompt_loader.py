"""
Greenlight Prompt Loader

Loads externalized prompts from markdown files.
Prompts are stored in /prompts/ directories within each feature folder.
TAG_NAMING_RULES is always imported from AgentPromptLibrary (single source of truth).

Prompt File Format:
    # {Agent Name} - {Prompt Purpose}
    
    ## Description
    Brief description of what this prompt does.
    
    ## Variables
    - `{variable_name}`: Description of the variable
    
    ## Prompt
    ```
    The actual prompt text with {variable_name} placeholders
    ```
    
    ## Notes
    - Any special considerations
"""

import re
from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

from greenlight.core.logging_config import get_logger

# Lazy import to avoid circular dependency
if TYPE_CHECKING:
    from greenlight.agents.prompts import AgentPromptLibrary

logger = get_logger("core.prompt_loader")


class PromptLoader:
    """
    Loads and caches prompts from external markdown files.
    
    Usage:
        # Load a prompt
        prompt = PromptLoader.load("tags/characters/prompts/01_extraction", "character_extraction_consensus_prompt")
        
        # Load with TAG_NAMING_RULES injected
        prompt = PromptLoader.load_with_tag_rules("tags/locations/prompts", "location_directional_prompt")
        
        # Render with variables
        rendered = PromptLoader.render(prompt, pitch_text="...", context="...")
    """
    
    _cache: Dict[str, str] = {}
    _base_path: Optional[Path] = None
    
    @classmethod
    def set_base_path(cls, path: Path) -> None:
        """Set the base path for prompt files (usually greenlight/)."""
        cls._base_path = path
        cls._cache.clear()  # Clear cache when base path changes
    
    @classmethod
    def _get_base_path(cls) -> Path:
        """Get the base path, defaulting to greenlight/ directory."""
        if cls._base_path:
            return cls._base_path
        # Default to greenlight/ directory (parent of core/)
        return Path(__file__).parent.parent
    
    @classmethod
    def load(cls, feature_path: str, prompt_name: str) -> str:
        """
        Load a prompt from the feature's prompts directory.
        
        Args:
            feature_path: Path relative to greenlight/, e.g., "tags/characters/prompts/01_extraction"
            prompt_name: Name of the prompt file (without .md extension)
            
        Returns:
            The prompt text extracted from the markdown file
            
        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        cache_key = f"{feature_path}/{prompt_name}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        # Build full path
        prompt_path = cls._get_base_path() / feature_path / f"{prompt_name}.md"
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")
        
        content = prompt_path.read_text(encoding='utf-8')
        
        # Extract prompt section from markdown
        prompt = cls._extract_prompt_section(content)
        
        cls._cache[cache_key] = prompt
        logger.debug(f"Loaded prompt: {cache_key}")
        return prompt
    
    @classmethod
    def load_with_tag_rules(cls, feature_path: str, prompt_name: str) -> str:
        """
        Load a prompt and inject TAG_NAMING_RULES.
        
        The prompt should contain {TAG_NAMING_RULES} placeholder.
        
        Args:
            feature_path: Path relative to greenlight/
            prompt_name: Name of the prompt file
            
        Returns:
            Prompt with TAG_NAMING_RULES injected
        """
        # Lazy import to avoid circular dependency
        from greenlight.agents.prompts import AgentPromptLibrary

        prompt = cls.load(feature_path, prompt_name)
        return prompt.replace("{TAG_NAMING_RULES}", AgentPromptLibrary.TAG_NAMING_RULES)
    
    @classmethod
    def render(cls, prompt: str, **variables: Any) -> str:
        """
        Render a prompt template with variables.
        
        Args:
            prompt: The prompt template
            **variables: Variables to substitute
            
        Returns:
            Rendered prompt
        """
        result = prompt
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result
    
    @classmethod
    def _extract_prompt_section(cls, content: str) -> str:
        """
        Extract the prompt text from markdown file.
        
        Looks for content between ## Prompt and the next ## section or end of file.
        Handles both fenced code blocks and plain text.
        """
        # Try to find fenced code block in Prompt section
        match = re.search(
            r'## Prompt\s*\n+```[^\n]*\n(.*?)```',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        
        # Try to find plain text in Prompt section (until next ## or end)
        match = re.search(
            r'## Prompt\s*\n+(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        
        # Fallback: return entire content (for simple prompt files)
        logger.warning(f"Could not find ## Prompt section, using entire content")
        return content.strip()
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the prompt cache."""
        cls._cache.clear()
        logger.debug("Prompt cache cleared")


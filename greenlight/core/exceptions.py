"""
Greenlight Custom Exceptions

Custom exception classes for error handling throughout the Project Greenlight system.
"""


class GreenlightError(Exception):
    """Base exception for all Greenlight errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================

class ConfigurationError(GreenlightError):
    """Raised when there's an issue with configuration."""
    pass


class MissingConfigError(ConfigurationError):
    """Raised when a required configuration is missing."""
    pass


class InvalidConfigError(ConfigurationError):
    """Raised when a configuration value is invalid."""
    pass


# =============================================================================
# TAG SYSTEM ERRORS
# =============================================================================

class TagError(GreenlightError):
    """Base exception for tag-related errors."""
    pass


class InvalidTagFormatError(TagError):
    """Raised when a tag doesn't match the expected format."""
    
    def __init__(self, tag: str, expected_pattern: str = None):
        message = f"Invalid tag format: '{tag}'"
        details = {"tag": tag}
        if expected_pattern:
            details["expected_pattern"] = expected_pattern
        super().__init__(message, details)


class UnregisteredTagError(TagError):
    """Raised when a tag is not found in the registry."""
    
    def __init__(self, tag: str, registry_type: str = None):
        message = f"Tag not registered: '{tag}'"
        details = {"tag": tag}
        if registry_type:
            details["registry_type"] = registry_type
        super().__init__(message, details)


class TagConsensusError(TagError):
    """Raised when tag validation fails to reach consensus."""
    
    def __init__(self, tag: str, agreement_ratio: float, threshold: float):
        message = f"Tag '{tag}' failed consensus: {agreement_ratio:.1%} < {threshold:.1%}"
        details = {
            "tag": tag,
            "agreement_ratio": agreement_ratio,
            "threshold": threshold
        }
        super().__init__(message, details)


# =============================================================================
# GRAPH ERRORS
# =============================================================================

class GraphError(GreenlightError):
    """Base exception for dependency graph errors."""
    pass


class NodeNotFoundError(GraphError):
    """Raised when a node is not found in the graph."""
    
    def __init__(self, node_id: str):
        message = f"Node not found in graph: '{node_id}'"
        super().__init__(message, {"node_id": node_id})


class CyclicDependencyError(GraphError):
    """Raised when a cyclic dependency is detected."""
    
    def __init__(self, cycle_path: list):
        message = f"Cyclic dependency detected: {' -> '.join(cycle_path)}"
        super().__init__(message, {"cycle_path": cycle_path})


class PropagationError(GraphError):
    """Raised when edit propagation fails."""
    pass


# =============================================================================
# PIPELINE ERRORS
# =============================================================================

class PipelineError(GreenlightError):
    """Base exception for pipeline errors."""
    pass


class PipelineStageError(PipelineError):
    """Raised when a specific pipeline stage fails."""
    
    def __init__(self, stage_name: str, reason: str):
        message = f"Pipeline stage '{stage_name}' failed: {reason}"
        super().__init__(message, {"stage": stage_name, "reason": reason})


class ValidationError(PipelineError):
    """Raised when validation fails in a pipeline."""
    pass


class QualityCheckError(PipelineError):
    """Raised when quality checks fail."""
    
    def __init__(self, issues: list):
        message = f"Quality check failed with {len(issues)} issue(s)"
        super().__init__(message, {"issues": issues})


# =============================================================================
# LLM ERRORS
# =============================================================================

class LLMError(GreenlightError):
    """Base exception for LLM-related errors."""
    pass


class LLMProviderError(LLMError):
    """Raised when there's an issue with an LLM provider."""
    
    def __init__(self, provider: str, reason: str):
        message = f"LLM provider '{provider}' error: {reason}"
        super().__init__(message, {"provider": provider, "reason": reason})


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or unexpected."""
    pass


class TokenLimitError(LLMError):
    """Raised when token limit is exceeded."""

    def __init__(self, tokens_used: int, limit: int):
        message = f"Token limit exceeded: {tokens_used} > {limit}"
        super().__init__(message, {"tokens_used": tokens_used, "limit": limit})


class ContentBlockedError(LLMProviderError):
    """Raised when content is blocked by provider's safety filters."""

    def __init__(self, provider: str, reason: str):
        message = f"Content blocked by {provider}: {reason}"
        super().__init__(provider, reason)
        self.is_content_block = True


# =============================================================================
# CONTEXT ENGINE ERRORS
# =============================================================================

class ContextError(GreenlightError):
    """Base exception for context engine errors."""
    pass


class ContextAssemblyError(ContextError):
    """Raised when context assembly fails."""
    pass


class VectorStoreError(ContextError):
    """Raised when vector store operations fail."""
    pass


# =============================================================================
# PROJECT STRUCTURE ERRORS
# =============================================================================

class ProjectError(GreenlightError):
    """Base exception for project structure errors."""
    pass


class ProjectNotFoundError(ProjectError):
    """Raised when a project is not found."""
    pass


class InvalidProjectStructureError(ProjectError):
    """Raised when project structure is invalid."""
    pass


class WorldBibleError(ProjectError):
    """Raised when there's an issue with the world bible."""
    pass


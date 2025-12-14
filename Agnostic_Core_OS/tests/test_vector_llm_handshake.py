"""
Test Script for Vector-LLM Handshake

Tests the complete flow of:
1. Natural language → Vector notation translation
2. LLM handshake with context
3. Iteration validation (max 100)
4. Developer report generation with documented input/output
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Import from Agnostic_Core_OS
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Agnostic_Core_OS import (
    AgnosticCorePlatform,
    VectorLanguageTranslator,
    VectorNotation,
    LLMHandshake,
    HandshakeConfig,
    HandshakeResult,
    IterationValidator,
    ValidationResult,
    TokenEfficientLogger,
    ContextReport,
    SystemsTranslatorIndex,
    SystemInfo,
    BuildParameters,
    OSType,
    Architecture,
    ShellType,
    get_systems_translator,
)
from Agnostic_Core_OS.translators.vector_language import NotationType, TranslationResult
from Agnostic_Core_OS.validators.iteration_validator import IterationConfig, ValidationStatus
from Agnostic_Core_OS.core.context_logger import CompressionLevel, LogLevel


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_project_path(tmp_path):
    """Create a temporary project path."""
    return tmp_path / "test_project"


@pytest.fixture
def translator():
    """Create a VectorLanguageTranslator."""
    return VectorLanguageTranslator()


@pytest.fixture
def handshake():
    """Create an LLMHandshake."""
    return LLMHandshake(config=HandshakeConfig())


@pytest.fixture
def validator():
    """Create an IterationValidator."""
    return IterationValidator(config=IterationConfig(max_iterations=100))


@pytest.fixture
def logger():
    """Create a TokenEfficientLogger."""
    return TokenEfficientLogger(max_tokens=4096)


@pytest.fixture
def systems_translator():
    """Create a SystemsTranslatorIndex."""
    return SystemsTranslatorIndex()


@pytest.fixture
def platform(temp_project_path):
    """Create an AgnosticCorePlatform."""
    return AgnosticCorePlatform(project_path=temp_project_path)


# =============================================================================
# VECTOR LANGUAGE TRANSLATION TESTS
# =============================================================================

class TestVectorLanguageTranslation:
    """Tests for natural ↔ vector translation."""
    
    def test_natural_to_vector_character(self, translator):
        """Test translating character lookup."""
        result = translator.natural_to_vector("find character Mei")
        
        assert result.success
        assert "@CHAR_MEI" in result.output_text
        assert len(result.notations) > 0
    
    def test_natural_to_vector_pipeline(self, translator):
        """Test translating pipeline command."""
        result = translator.natural_to_vector("run the story pipeline")
        
        assert result.success
        assert ">story" in result.output_text
    
    def test_natural_to_vector_scope(self, translator):
        """Test translating scope filter."""
        result = translator.natural_to_vector("in the world bible")
        
        assert result.success
        assert "#WORLD_BIBLE" in result.output_text
    
    def test_vector_to_natural_tag(self, translator):
        """Test translating vector tag to natural."""
        result = translator.vector_to_natural("@CHAR_MEI")
        
        assert result.success
        assert len(result.notations) > 0
        assert result.notations[0].notation_type == NotationType.TAG
    
    def test_parse_notations(self, translator):
        """Test parsing multiple notations."""
        notations = translator.parse_notations("@CHAR_MEI #STORY >diagnose")
        
        assert len(notations) >= 2
        types = [n.notation_type for n in notations]
        assert NotationType.TAG in types
        assert NotationType.SCOPE in types
    
    def test_translation_history(self, translator):
        """Test translation history tracking."""
        translator.natural_to_vector("find character Mei")
        translator.natural_to_vector("run diagnostics")
        
        history = translator.get_history()
        assert len(history) == 2


# =============================================================================
# LLM HANDSHAKE TESTS
# =============================================================================

class TestLLMHandshake:
    """Tests for LLM handshake protocol."""
    
    def test_handshake_initialization(self, handshake):
        """Test handshake initializes correctly."""
        assert handshake.config is not None
        assert handshake.config.max_retries == 3
    
    def test_load_context(self, handshake):
        """Test loading context vectors."""
        handshake.load_context("character", {"name": "Mei"}, "@CHAR_MEI")
        
        context = handshake.get_active_context()
        assert "character" in context
        assert context["character"].notation == "@CHAR_MEI"
    
    def test_build_system_prompt(self, handshake):
        """Test building system prompt with context."""
        handshake.load_context("character", "Mei data", "@CHAR_MEI")
        
        prompt = handshake.build_system_prompt()
        
        assert "@CHAR_MEI" in prompt
        assert "Context" in prompt or "context" in prompt
    
    @pytest.mark.asyncio
    async def test_execute_mock(self, handshake):
        """Test handshake execution with mock LLM."""
        result = await handshake.execute(
            "Describe the character",
            context={"project": "Test"}
        )

        assert result.handshake_id.startswith("hs_")
        assert result.input_natural == "Describe the character"
        assert "[Mock Response]" in result.output_natural


# =============================================================================
# ITERATION VALIDATOR TESTS
# =============================================================================

class TestIterationValidator:
    """Tests for iteration validation (max 100)."""

    def test_validator_max_iterations(self, validator):
        """Test max iterations is enforced."""
        assert validator.config.max_iterations <= 100

    def test_sync_validation_pass(self, validator):
        """Test synchronous validation that passes."""
        def process(inp):
            return f"Processed: {inp}"

        def validate(out):
            return len(out) > 5, 0.9

        result = validator.run_sync("test input", process, validate)

        assert result.status == ValidationStatus.PASSED
        assert result.score == 0.9

    def test_sync_validation_with_refinement(self, validator):
        """Test validation with refinement."""
        call_count = [0]

        def process(inp):
            call_count[0] += 1
            return f"Output {call_count[0]}: {inp}"

        def validate(out):
            # Pass on 3rd iteration
            return call_count[0] >= 3, call_count[0] / 10

        def refine(inp, out, issues):
            return f"Refined: {inp}"

        result = validator.run_sync("initial", process, validate, refine)

        assert result.status == ValidationStatus.PASSED
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_async_validation(self, validator):
        """Test async validation."""
        async def process(inp):
            return f"Async: {inp}"

        def validate(out):
            return True, 0.95

        result = await validator.run("test", process, validate)

        assert result.status == ValidationStatus.PASSED

    def test_get_stats(self, validator):
        """Test getting validation statistics."""
        def process(inp):
            return inp

        def validate(out):
            return True, 0.8

        validator.run_sync("test", process, validate)
        stats = validator.get_stats()

        assert stats["total"] >= 1
        assert stats["passed"] >= 1


# =============================================================================
# TOKEN-EFFICIENT LOGGER TESTS
# =============================================================================

class TestTokenEfficientLogger:
    """Tests for token-efficient logging."""

    def test_log_entry(self, logger):
        """Test logging an entry."""
        entry = logger.log("character", "Mei is a warrior", "@CHAR_MEI")

        assert entry.key == "character"
        assert entry.notation == "@CHAR_MEI"
        assert entry.tokens > 0

    def test_compression_levels(self, logger):
        """Test different compression levels."""
        text = "This is a character description with personality traits"

        none = logger._compress(text, CompressionLevel.NONE)
        medium = logger._compress(text, CompressionLevel.MEDIUM)
        extreme = logger._compress(text, CompressionLevel.EXTREME)

        assert len(none) >= len(medium)
        assert len(medium) >= len(extreme)

    def test_generate_report(self, logger):
        """Test generating context report."""
        logger.log("char1", "Character 1 data", "@CHAR_1")
        logger.log("char2", "Character 2 data", "@CHAR_2")

        report = logger.generate_report()

        assert report.report_id.startswith("ctx_")
        assert len(report.entries) == 2
        assert report.system_prompt != ""

    def test_token_usage(self, logger):
        """Test token usage tracking."""
        logger.log("test", "Some test data here", "@TEST")

        usage = logger.get_token_usage()

        assert usage["total_entries"] == 1
        assert usage["total_tokens"] > 0

    def test_developer_report(self, logger):
        """Test developer report generation."""
        logger.log("test", "Test data", "@TEST")

        report = logger.generate_developer_report()

        assert "Token-Efficient Context Report" in report
        assert "@TEST" in report


# =============================================================================
# PLATFORM INTEGRATION TESTS
# =============================================================================

class TestAgnosticCorePlatform:
    """Tests for the complete platform."""

    def test_platform_initialization(self, platform):
        """Test platform initializes correctly."""
        assert platform.translator is not None
        assert platform.handshake is not None
        assert platform.validator is not None
        assert platform.logger is not None

    def test_translate_to_vector(self, platform):
        """Test translation through platform."""
        result = platform.translate("find character Mei", to_vector=True)

        assert result.success
        assert "@CHAR_MEI" in result.output_text

    def test_load_context(self, platform):
        """Test loading context through platform."""
        platform.load_context("character", "Mei data", "@CHAR_MEI")

        context = platform.handshake.get_active_context()
        assert "character" in context

    @pytest.mark.asyncio
    async def test_execute_session(self, platform):
        """Test executing a complete session."""
        session = await platform.execute(
            "Describe the character Mei",
            context={"project": "Test Project"}
        )

        assert session.session_id.startswith("sess_")
        assert session.natural_input == "Describe the character Mei"
        assert session.tokens_used > 0

    def test_developer_report(self, platform):
        """Test generating developer report."""
        report = platform.generate_developer_report()

        assert "Agnostic Core OS" in report
        assert "Platform Configuration" in report


# =============================================================================
# DOCUMENTED INPUT/OUTPUT TEST
# =============================================================================

class TestDocumentedInputOutput:
    """Tests that document natural language input and vector output."""

    def test_documented_translation_flow(self, translator):
        """
        Document the complete translation flow.

        This test demonstrates and documents:
        1. Natural language input
        2. Vector notation output
        3. Back-translation to natural language
        """
        # Input: Natural language
        natural_input = "Find character Mei in the story"

        # Step 1: Translate to vector
        to_vector = translator.natural_to_vector(natural_input)

        # Document the translation
        print("\n" + "="*60)
        print("DOCUMENTED TRANSLATION FLOW")
        print("="*60)
        print(f"Natural Input:  {natural_input}")
        print(f"Vector Output:  {to_vector.output_text}")
        print(f"Success:        {to_vector.success}")
        print(f"Notations:      {[n.to_dict() for n in to_vector.notations]}")

        # Step 2: Translate back to natural
        back_to_natural = translator.vector_to_natural(to_vector.output_text)

        print(f"Back to Natural: {back_to_natural.output_text}")
        print("="*60 + "\n")

        # Assertions
        assert to_vector.success
        assert "@CHAR_MEI" in to_vector.output_text

    @pytest.mark.asyncio
    async def test_documented_handshake_flow(self, platform):
        """
        Document the complete handshake flow.

        This test demonstrates and documents:
        1. Context loading
        2. LLM handshake execution
        3. Session result with all data
        """
        # Load context
        platform.load_context(
            "character",
            {"name": "Mei", "role": "protagonist", "motivation": "honor"},
            "@CHAR_MEI"
        )

        # Execute handshake
        session = await platform.execute(
            "What is Mei's primary motivation?",
            context={"project": "Go for Orchid", "scene": "1"}
        )

        # Document the session
        print("\n" + "="*60)
        print("DOCUMENTED HANDSHAKE FLOW")
        print("="*60)
        print(f"Session ID:     {session.session_id}")
        print(f"Natural Input:  {session.natural_input}")
        print(f"Vector Input:   {session.vector_input}")
        print(f"Natural Output: {session.natural_output[:100]}...")
        print(f"Vector Output:  {session.vector_output}")
        print(f"Iterations:     {session.iterations}")
        print(f"Tokens Used:    {session.tokens_used}")
        print("="*60 + "\n")

        # Generate developer report
        report = platform.generate_developer_report()
        print("\nDEVELOPER REPORT:")
        print(report)

        # Assertions
        assert session.session_id is not None
        assert session.tokens_used > 0


# =============================================================================
# SYSTEMS TRANSLATOR TESTS
# =============================================================================

class TestSystemsTranslatorIndex:
    """Tests for the Systems Translator Index."""

    def test_detect_os_type(self, systems_translator):
        """Test OS type detection."""
        os_type = systems_translator.detect_os_type()

        assert os_type in [OSType.WINDOWS, OSType.MACOS, OSType.LINUX, OSType.BSD, OSType.UNKNOWN]
        # On Windows, should detect Windows
        import sys
        if sys.platform == 'win32':
            assert os_type == OSType.WINDOWS

    def test_detect_architecture(self, systems_translator):
        """Test architecture detection."""
        arch = systems_translator.detect_architecture()

        assert arch in [Architecture.X86, Architecture.X64, Architecture.ARM, Architecture.ARM64, Architecture.UNKNOWN]

    def test_detect_shell_type(self, systems_translator):
        """Test shell type detection."""
        shell = systems_translator.detect_shell_type()

        assert shell in [ShellType.POWERSHELL, ShellType.CMD, ShellType.BASH, ShellType.ZSH, ShellType.SH, ShellType.UNKNOWN]

    def test_get_system_info(self, systems_translator):
        """Test getting comprehensive system info."""
        info = systems_translator.get_system_info()

        assert isinstance(info, SystemInfo)
        assert info.os_type is not None
        assert info.architecture is not None
        assert info.python_version is not None
        assert info.cpu_count >= 1
        assert info.home_dir.exists()

    def test_get_build_parameters(self, systems_translator):
        """Test getting self-building parameters."""
        params = systems_translator.get_build_parameters()

        assert isinstance(params, BuildParameters)
        assert params.parallel_workers >= 1
        assert params.max_memory_mb > 0
        assert params.chunk_size > 0
        assert params.recommended_batch_size > 0

    def test_translate_command(self, systems_translator):
        """Test command translation."""
        # Test list_files command
        cmd = systems_translator.translate_command("list_files")

        info = systems_translator.get_system_info()
        if info.os_type == OSType.WINDOWS:
            assert cmd == "dir"
        else:
            assert cmd == "ls -la"

    def test_translate_command_with_args(self, systems_translator):
        """Test command translation with arguments."""
        cmd = systems_translator.translate_command("list_files", "*.py")

        info = systems_translator.get_system_info()
        if info.os_type == OSType.WINDOWS:
            assert cmd == "dir *.py"
        else:
            assert cmd == "ls -la *.py"

    def test_get_python_command(self, systems_translator):
        """Test getting Python command."""
        python_cmd = systems_translator.get_python_command()

        info = systems_translator.get_system_info()
        if info.os_type == OSType.WINDOWS:
            assert python_cmd == "py"
        else:
            assert python_cmd == "python3"

    def test_normalize_path(self, systems_translator):
        """Test path normalization."""
        path = "foo/bar/baz"
        normalized = systems_translator.normalize_path(path)

        info = systems_translator.get_system_info()
        if info.os_type == OSType.WINDOWS:
            assert "\\" in normalized
        else:
            assert "/" in normalized

    def test_generate_system_report(self, systems_translator):
        """Test system report generation."""
        report = systems_translator.generate_system_report()

        assert "Systems Translator Index Report" in report
        assert "System Information" in report
        assert "Build Parameters" in report
        assert "Command Translations" in report

    def test_to_dict(self, systems_translator):
        """Test exporting to dictionary."""
        data = systems_translator.to_dict()

        assert "system_info" in data
        assert "build_parameters" in data
        assert "command_index" in data

    def test_singleton_accessor(self):
        """Test the singleton accessor function."""
        translator1 = get_systems_translator()
        translator2 = get_systems_translator()

        # Should return same instance
        assert translator1 is translator2

    def test_system_info_caching(self, systems_translator):
        """Test that system info is cached."""
        info1 = systems_translator.get_system_info()
        info2 = systems_translator.get_system_info()

        # Should return same cached instance
        assert info1 is info2

        # Force refresh should return new instance
        info3 = systems_translator.get_system_info(refresh=True)
        assert info3 is not info1

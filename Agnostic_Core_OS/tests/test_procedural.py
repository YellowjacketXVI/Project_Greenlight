"""
Tests for Agnostic_Core_OS Procedural System

Tests:
- VectorKeyAuth: authentication, key management
- CoreLock: file protection, integrity validation
- NotationLibrary: notation registration, search
- VectorFileBrowser: file browsing, indexing
- ContextIndex: code indexing, search
"""

import pytest
import tempfile
from pathlib import Path

from Agnostic_Core_OS.core.vector_auth import (
    VectorKeyAuth,
    VectorKey,
    AccessLevel,
    AuthResult,
)
from Agnostic_Core_OS.core.core_lock import (
    CoreLock,
    CoreScope,
    Capability,
    CORE_FILES,
    CORE_GUIDELINES,
)
from Agnostic_Core_OS.procedural.notation_library import (
    NotationLibrary,
    NotationType,
    NotationScope,
)
from Agnostic_Core_OS.procedural.file_browser import (
    VectorFileBrowser,
    FileCategory,
)
from Agnostic_Core_OS.procedural.context_index import (
    ContextIndex,
    IndexScope,
    IndexEntryType,
)


# =============================================================================
# VECTOR KEY AUTH TESTS
# =============================================================================

class TestVectorKeyAuth:
    """Tests for VectorKeyAuth."""
    
    @pytest.fixture
    def auth(self, tmp_path):
        """Create a VectorKeyAuth instance."""
        return VectorKeyAuth(tmp_path)
    
    def test_initialize(self, auth):
        """Test auth initialization."""
        master_key = auth.initialize()
        
        assert master_key is not None
        assert len(master_key) > 20
        assert auth.is_initialized()
    
    def test_authenticate(self, auth):
        """Test authentication."""
        master_key = auth.initialize()
        
        result = auth.authenticate(master_key)
        assert result == AuthResult.SUCCESS
        
        result = auth.authenticate("invalid_key")
        assert result == AuthResult.INVALID_KEY
    
    def test_create_key(self, auth):
        """Test key creation."""
        master_key = auth.initialize()
        
        new_key = auth.create_key(
            master_key=master_key,
            access_level=AccessLevel.READ,
        )
        
        assert new_key is not None
        assert auth.authenticate(new_key) == AuthResult.SUCCESS
    
    def test_check_access(self, auth):
        """Test access checking."""
        master_key = auth.initialize()
        
        result = auth.check_access(master_key, "some/path", "read")
        assert result == AuthResult.SUCCESS
    
    def test_lock_path(self, auth):
        """Test path locking."""
        master_key = auth.initialize()
        
        assert auth.lock_path(master_key, "protected/path")
        
        result = auth.check_access(master_key, "protected/path", "write")
        assert result == AuthResult.LOCKED_RESOURCE


# =============================================================================
# CORE LOCK TESTS
# =============================================================================

class TestCoreLock:
    """Tests for CoreLock."""
    
    @pytest.fixture
    def lock(self, tmp_path):
        """Create a CoreLock instance."""
        return CoreLock(tmp_path)
    
    def test_core_files_defined(self):
        """Test that core files are defined."""
        assert len(CORE_FILES) > 0
    
    def test_guidelines_defined(self):
        """Test that guidelines are defined."""
        assert len(CORE_GUIDELINES) > 0
        assert "NO_EXTERNAL_EDIT" in CORE_GUIDELINES
    
    def test_is_core_file(self, lock):
        """Test core file detection."""
        assert lock.is_core_file("Agnostic_Core_OS/core/vector_auth.py")
        assert not lock.is_core_file("some/random/file.py")
    
    def test_can_modify(self, lock):
        """Test modification check."""
        assert not lock.can_modify("Agnostic_Core_OS/core/vector_auth.py")
        assert lock.can_modify("some/random/file.py")
    
    def test_get_protected_paths(self, lock):
        """Test getting protected paths."""
        paths = lock.get_protected_paths()
        assert len(paths) > 0
        assert "Agnostic_Core_OS/core/vector_auth.py" in paths


# =============================================================================
# NOTATION LIBRARY TESTS
# =============================================================================

class TestNotationLibrary:
    """Tests for NotationLibrary."""
    
    @pytest.fixture
    def library(self, tmp_path):
        """Create a NotationLibrary instance."""
        return NotationLibrary(tmp_path / "notation")
    
    def test_core_notations_initialized(self, library):
        """Test that core notations are initialized."""
        stats = library.get_stats()
        assert stats["total"] > 0
        assert stats["immutable"] > 0
    
    def test_register_notation(self, library):
        """Test notation registration."""
        entry = library.register(
            symbol="@CUSTOM_TEST",
            notation_type=NotationType.TAG,
            scope=NotationScope.PROJECT,
            definition="A custom test notation",
            pattern="@CUSTOM_TEST",
        )
        
        assert entry is not None
        assert entry.symbol == "@CUSTOM_TEST"
    
    def test_get_notation(self, library):
        """Test getting notation by symbol."""
        entry = library.get("@TAG")
        assert entry is not None
        assert entry.is_immutable
    
    def test_search_notations(self, library):
        """Test notation search."""
        results = library.search("tag")
        assert len(results) > 0

    def test_query_by_type(self, library):
        """Test querying by type."""
        results = library.query_by_type(NotationType.TAG)
        assert len(results) > 0


# =============================================================================
# FILE BROWSER TESTS
# =============================================================================

class TestVectorFileBrowser:
    """Tests for VectorFileBrowser."""

    @pytest.fixture
    def browser(self, tmp_path):
        """Create a VectorFileBrowser instance."""
        # Create some test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "data.json").write_text('{"key": "value"}')
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.txt").write_text("nested content")

        return VectorFileBrowser(tmp_path, tmp_path / ".index")

    def test_vectorize_file(self, browser, tmp_path):
        """Test file vectorization."""
        fv = browser.vectorize_file(tmp_path / "test.py")

        assert fv is not None
        assert fv.category == FileCategory.CODE
        assert fv.extension == ".py"
        assert "@FILE_" in fv.vector_notation

    def test_browse(self, browser):
        """Test directory browsing."""
        result = browser.browse("")

        assert result.total_items > 0
        assert len(result.files) >= 2
        assert len(result.directories) >= 1

    def test_search(self, browser, tmp_path):
        """Test file search."""
        # Index files first
        browser.browse("")

        results = browser.search("test")
        assert len(results) > 0

    def test_read_file(self, browser):
        """Test file reading."""
        content = browser.read_file("test.py")
        assert content == "print('hello')"

    def test_write_file(self, browser, tmp_path):
        """Test file writing."""
        assert browser.write_file("new_file.txt", "new content")
        assert (tmp_path / "new_file.txt").read_text() == "new content"

    def test_get_stats(self, browser):
        """Test browser statistics."""
        browser.browse("")
        stats = browser.get_stats()

        assert stats["total_files"] > 0


# =============================================================================
# CONTEXT INDEX TESTS
# =============================================================================

class TestContextIndex:
    """Tests for ContextIndex."""

    @pytest.fixture
    def index(self, tmp_path):
        """Create a ContextIndex instance."""
        return ContextIndex(tmp_path / ".context")

    def test_index_file(self, index):
        """Test file indexing."""
        content = '''
def hello():
    print("Hello")

class MyClass:
    pass
'''
        entries = index.index_file("test.py", content)

        assert len(entries) >= 3  # file + function + class

    def test_search(self, index):
        """Test search."""
        index.index_file("test.py", "def hello(): pass")

        result = index.search("hello")
        assert result.total_matches > 0

    def test_get_functions(self, index):
        """Test getting functions."""
        index.index_file("test.py", "def foo(): pass\ndef bar(): pass")

        funcs = index.get_functions()
        assert len(funcs) >= 2

    def test_get_classes(self, index):
        """Test getting classes."""
        index.index_file("test.py", "class Foo: pass\nclass Bar: pass")

        classes = index.get_classes()
        assert len(classes) >= 2

    def test_get_stats(self, index):
        """Test index statistics."""
        index.index_file("test.py", "def foo(): pass")

        stats = index.get_stats()
        assert stats["total_entries"] > 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestProceduralIntegration:
    """Integration tests for the procedural system."""

    def test_full_workflow(self, tmp_path):
        """Test full procedural workflow."""
        # 1. Initialize auth
        auth = VectorKeyAuth(tmp_path)
        master_key = auth.initialize()

        # 2. Create notation library
        library = NotationLibrary(tmp_path / "notation")
        library.register(
            symbol="@PROJECT_FILE",
            notation_type=NotationType.TAG,
            scope=NotationScope.PROJECT,
            definition="Project file reference",
            pattern="@PROJECT_FILE_.*",
        )

        # 3. Create file browser
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("def main(): pass")

        browser = VectorFileBrowser(tmp_path, tmp_path / ".index")
        browser.browse("src")

        # 4. Create context index
        index = ContextIndex(tmp_path / ".context")
        content = browser.read_file("src/main.py")
        index.index_file("src/main.py", content)

        # 5. Search
        result = index.search("main")
        assert result.total_matches > 0

        # 6. Verify auth still works
        assert auth.authenticate(master_key) == AuthResult.SUCCESS


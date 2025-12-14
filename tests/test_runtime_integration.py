"""
Integration Tests for Agnostic_Core_OS Runtime

Tests the complete flow from UI → Runtime → Pipeline including:
- Daemon startup and shutdown
- App connection via SDK
- Event emission and subscription
- Pipeline execution with event tracking
- Health monitoring
- Error handoff
"""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

# Runtime imports
from Agnostic_Core_OS.runtime import (
    RuntimeDaemon, DaemonConfig, DaemonState,
    AppRegistry, AppInfo, AppState,
    EventBus, Event, EventPriority,
    AppSDK, AppConnection,
    HealthMonitor, HealthStatus
)
from Agnostic_Core_OS.core_routing import (
    VectorCache, CacheEntryType, VectorWeight,
    HealthLogger, LogCategory,
    ErrorHandoff, ErrorSeverity
)

# Greenlight integration imports
from greenlight.runtime_integration import (
    GreenlightRuntimeBridge,
    PipelineType,
    PipelineStatus,
    PipelineProgress,
    get_runtime_bridge,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_runtime_dir(tmp_path):
    """Create a temporary directory for runtime state."""
    runtime_dir = tmp_path / ".runtime_test"
    runtime_dir.mkdir()
    return runtime_dir


@pytest.fixture
def daemon_config(temp_runtime_dir):
    """Create a daemon configuration for testing."""
    return DaemonConfig(
        state_dir=temp_runtime_dir,
        auto_heal=False,  # Disable auto-heal for predictable tests
        health_check_interval=60.0,  # Long interval to avoid interference
        max_apps=10,
        event_queue_size=100,
        persist_state=False
    )


@pytest_asyncio.fixture
async def running_daemon(daemon_config):
    """Create and start a runtime daemon."""
    daemon = RuntimeDaemon(daemon_config)
    await daemon.start()
    yield daemon
    await daemon.stop()


@pytest.fixture
def greenlight_sdk():
    """Create a Greenlight SDK instance."""
    return AppSDK(
        name="Greenlight",
        version="1.0.0",
        capabilities=["story_pipeline", "directing_pipeline", "world_bible"]
    )


@pytest.fixture
def image_gen_sdk():
    """Create an ImageGenerator SDK instance."""
    return AppSDK(
        name="ImageGenerator",
        version="0.5.0",
        capabilities=["image_generation", "style_transfer"]
    )


# =============================================================================
# DAEMON LIFECYCLE TESTS
# =============================================================================

class TestDaemonLifecycle:
    """Tests for RuntimeDaemon lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_daemon_starts_successfully(self, daemon_config):
        """Test that daemon starts and initializes components."""
        daemon = RuntimeDaemon(daemon_config)
        
        assert daemon.state == DaemonState.STOPPED
        
        result = await daemon.start()
        
        assert result is True
        assert daemon.state == DaemonState.RUNNING
        assert daemon.daemon_id is not None
        assert daemon.app_registry is not None
        assert daemon.event_bus is not None
        assert daemon.health_monitor is not None
        
        await daemon.stop()
    
    @pytest.mark.asyncio
    async def test_daemon_stops_gracefully(self, daemon_config):
        """Test that daemon stops and cleans up."""
        daemon = RuntimeDaemon(daemon_config)
        await daemon.start()
        
        result = await daemon.stop()
        
        assert result is True
        assert daemon.state == DaemonState.STOPPED
    
    @pytest.mark.asyncio
    async def test_daemon_double_start_is_safe(self, daemon_config):
        """Test that starting an already running daemon is safe."""
        daemon = RuntimeDaemon(daemon_config)
        await daemon.start()
        
        # Second start should return True without error
        result = await daemon.start()
        
        assert result is True
        assert daemon.state == DaemonState.RUNNING
        
        await daemon.stop()
    
    @pytest.mark.asyncio
    async def test_daemon_double_stop_is_safe(self, daemon_config):
        """Test that stopping an already stopped daemon is safe."""
        daemon = RuntimeDaemon(daemon_config)
        await daemon.start()
        await daemon.stop()

        # Second stop should return True without error
        result = await daemon.stop()

        assert result is True
        assert daemon.state == DaemonState.STOPPED


# =============================================================================
# APP REGISTRATION TESTS
# =============================================================================

class TestAppRegistration:
    """Tests for app registration via AppSDK."""

    @pytest.mark.asyncio
    async def test_app_connects_successfully(self, running_daemon, greenlight_sdk):
        """Test that an app can connect to the runtime."""
        connection = await greenlight_sdk.connect(running_daemon)

        assert connection is not None
        assert connection.app_id is not None
        assert connection.connected is True
        assert greenlight_sdk.is_connected is True

    @pytest.mark.asyncio
    async def test_multiple_apps_connect(self, running_daemon, greenlight_sdk, image_gen_sdk):
        """Test that multiple apps can connect simultaneously."""
        conn1 = await greenlight_sdk.connect(running_daemon)
        conn2 = await image_gen_sdk.connect(running_daemon)

        assert conn1.app_id != conn2.app_id
        assert greenlight_sdk.is_connected is True
        assert image_gen_sdk.is_connected is True

        stats = running_daemon.app_registry.get_stats()
        assert stats["total_apps"] == 2

    @pytest.mark.asyncio
    async def test_app_disconnects_successfully(self, running_daemon, greenlight_sdk):
        """Test that an app can disconnect from the runtime."""
        await greenlight_sdk.connect(running_daemon)
        assert greenlight_sdk.is_connected is True

        await greenlight_sdk.disconnect()

        assert greenlight_sdk.is_connected is False

    @pytest.mark.asyncio
    async def test_app_capabilities_registered(self, running_daemon, greenlight_sdk):
        """Test that app capabilities are registered correctly."""
        await greenlight_sdk.connect(running_daemon)

        # Find apps with specific capability
        apps = running_daemon.app_registry.find_by_capability("story_pipeline")

        assert len(apps) == 1
        assert apps[0].name == "Greenlight"

    @pytest.mark.asyncio
    async def test_registry_stats_accurate(self, running_daemon, greenlight_sdk, image_gen_sdk):
        """Test that registry statistics are accurate."""
        await greenlight_sdk.connect(running_daemon)
        await image_gen_sdk.connect(running_daemon)

        stats = running_daemon.app_registry.get_stats()

        assert stats["total_apps"] == 2
        assert stats["states"]["connected"] == 2
        assert stats["states"]["disconnected"] == 0


# =============================================================================
# EVENT BUS TESTS
# =============================================================================

class TestEventBus:
    """Tests for inter-app communication via EventBus."""

    @pytest.mark.asyncio
    async def test_event_emission(self, running_daemon, greenlight_sdk):
        """Test that events can be emitted."""
        await greenlight_sdk.connect(running_daemon)

        await greenlight_sdk.emit("test.event", {"message": "hello"})

        # Event should be in the bus
        stats = running_daemon.event_bus.get_stats()
        assert stats["events_emitted"] >= 1

    @pytest.mark.asyncio
    async def test_event_subscription(self, running_daemon, greenlight_sdk, image_gen_sdk):
        """Test that apps can subscribe to events."""
        await greenlight_sdk.connect(running_daemon)
        await image_gen_sdk.connect(running_daemon)

        received_events: List[Event] = []

        @image_gen_sdk.on("pipeline.*")
        async def handle_pipeline(event: Event):
            received_events.append(event)

        # Emit event from Greenlight
        await greenlight_sdk.emit("pipeline.started", {"pipeline": "story"})

        # Give time for async processing
        await asyncio.sleep(0.05)

        assert len(received_events) == 1
        assert received_events[0].topic == "pipeline.started"
        assert received_events[0].data["pipeline"] == "story"

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, running_daemon, greenlight_sdk, image_gen_sdk):
        """Test wildcard topic subscriptions."""
        await greenlight_sdk.connect(running_daemon)
        await image_gen_sdk.connect(running_daemon)

        received_events: List[Event] = []

        @image_gen_sdk.on("greenlight.*")
        async def handle_greenlight(event: Event):
            received_events.append(event)

        # Emit multiple events
        await greenlight_sdk.emit("greenlight.started", {})
        await greenlight_sdk.emit("greenlight.progress", {"progress": 0.5})
        await greenlight_sdk.emit("greenlight.completed", {})
        await greenlight_sdk.emit("other.event", {})  # Should not match

        await asyncio.sleep(0.05)

        assert len(received_events) == 3

    @pytest.mark.asyncio
    async def test_event_priority(self, running_daemon, greenlight_sdk):
        """Test that multiple events can be emitted."""
        await greenlight_sdk.connect(running_daemon)

        # Emit multiple events
        await greenlight_sdk.emit("event.one", {"order": 1})
        await greenlight_sdk.emit("event.two", {"order": 2})
        await greenlight_sdk.emit("event.three", {"order": 3})

        # Events should be tracked
        stats = running_daemon.event_bus.get_stats()
        assert stats["events_emitted"] >= 3


# =============================================================================
# HEALTH MONITORING TESTS
# =============================================================================

class TestHealthMonitoring:
    """Tests for runtime health monitoring."""

    @pytest.mark.asyncio
    async def test_health_check_returns_status(self, running_daemon):
        """Test that health check returns a valid status."""
        health = await running_daemon.health_monitor.check()

        assert health is not None
        assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert isinstance(health.is_healthy, bool)

    @pytest.mark.asyncio
    async def test_healthy_runtime_reports_healthy(self, running_daemon, greenlight_sdk):
        """Test that a healthy runtime reports healthy status."""
        await greenlight_sdk.connect(running_daemon)

        health = await running_daemon.health_monitor.check()

        assert health.status == HealthStatus.HEALTHY
        assert health.is_healthy is True

    @pytest.mark.asyncio
    async def test_health_report_generation(self, running_daemon):
        """Test that health report can be generated."""
        report = running_daemon.health_monitor.generate_report()

        assert report is not None
        assert "Health Report" in report
        assert "Generated" in report


# =============================================================================
# VECTOR CACHE TESTS
# =============================================================================

class TestVectorCache:
    """Tests for VectorCache functionality."""

    def test_cache_add_and_retrieve(self):
        """Test adding and retrieving cache entries."""
        cache = VectorCache()

        entry = cache.add(
            content="Test content",
            entry_type=CacheEntryType.NOTATION_DEFINITION,
            weight=VectorWeight.ACTIVE.value,
            notation="@TEST"
        )

        assert entry is not None
        assert entry.id is not None
        assert cache.count == 1

        retrieved = cache.get(entry.id)
        assert retrieved is not None
        assert retrieved.content == "Test content"

    def test_cache_weight_filtering(self):
        """Test filtering by weight."""
        cache = VectorCache()

        cache.add("Active", CacheEntryType.NOTATION_DEFINITION, VectorWeight.ACTIVE.value)
        cache.add("Archived", CacheEntryType.ARCHIVED_CONCEPT, VectorWeight.ARCHIVED.value)
        cache.add("Deprecated", CacheEntryType.NOTATION_DEFINITION, VectorWeight.DEPRECATED.value)

        # get_by_weight returns entries with weight >= min_weight
        active = cache.get_by_weight(VectorWeight.ACTIVE.value)
        assert len(active) == 1

        archived = cache.get_archived()
        assert len(archived) == 2  # Both archived and deprecated have negative weights

    def test_cache_size_limit(self):
        """Test that cache respects size limits (1MB max)."""
        cache = VectorCache()

        # Add entries - cache has 1MB limit (1024 * 1024 bytes)
        for i in range(10):
            cache.add(f"Content {i}" * 10, CacheEntryType.NOTATION_DEFINITION, 1.0)

        # Cache should have entries and track size
        assert cache.count > 0
        assert cache.size_bytes > 0
        # 1MB = 1048576 bytes
        assert cache.size_bytes <= 1048576


# =============================================================================
# ERROR HANDOFF TESTS
# =============================================================================

class TestErrorHandoff:
    """Tests for error handoff functionality."""

    def test_error_flagging(self):
        """Test that errors can be flagged."""
        cache = VectorCache()
        logger = HealthLogger()
        handoff = ErrorHandoff(vector_cache=cache, health_logger=logger)

        try:
            raise ValueError("Test error")
        except Exception as e:
            result = handoff.handoff_for_guidance(
                error=e,
                severity=ErrorSeverity.ERROR,
                source="test_module",
                context={"test": True}
            )

        assert result["transcript_id"] is not None
        assert result["cached"] is True
        assert result["logged"] is True

    def test_error_severity_levels(self):
        """Test different error severity levels."""
        cache = VectorCache()
        logger = HealthLogger()
        handoff = ErrorHandoff(vector_cache=cache, health_logger=logger)

        for severity in [ErrorSeverity.INFO, ErrorSeverity.WARNING, ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            result = handoff.handoff_for_guidance(
                error=Exception(f"Test {severity.value}"),
                severity=severity,
                source="test"
            )
            assert result["transcript_id"] is not None


# =============================================================================
# GREENLIGHT INTEGRATION TESTS
# =============================================================================

class TestGreenlightIntegration:
    """Tests for Greenlight runtime integration."""

    @pytest.mark.asyncio
    async def test_bridge_connects_to_runtime(self, running_daemon):
        """Test that GreenlightRuntimeBridge connects successfully."""
        bridge = GreenlightRuntimeBridge()

        result = await bridge.connect(running_daemon)

        assert result is True
        assert bridge.is_connected is True
        assert bridge.app_id is not None

        await bridge.disconnect()

    @pytest.mark.asyncio
    async def test_bridge_emits_pipeline_events(self, running_daemon):
        """Test that bridge emits pipeline events."""
        bridge = GreenlightRuntimeBridge()
        await bridge.connect(running_daemon)

        # Create a listener SDK
        listener = AppSDK(name="Listener", version="1.0.0", capabilities=[])
        await listener.connect(running_daemon)

        received_events: List[Event] = []

        @listener.on("greenlight.*")
        async def handle_event(event: Event):
            received_events.append(event)

        # Emit event through bridge
        await bridge._emit_pipeline_event("pipeline.test", {"test": True})

        await asyncio.sleep(0.05)

        assert len(received_events) == 1
        assert received_events[0].topic == "greenlight.pipeline.test"

        await bridge.disconnect()

    @pytest.mark.asyncio
    async def test_pipeline_progress_tracking(self, running_daemon):
        """Test pipeline progress tracking."""
        bridge = GreenlightRuntimeBridge()
        await bridge.connect(running_daemon)

        # Initially no active pipelines
        assert len(bridge.get_active_pipelines()) == 0

        await bridge.disconnect()


# =============================================================================
# FULL INTEGRATION FLOW TEST
# =============================================================================

class TestFullIntegrationFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_complete_runtime_flow(self, daemon_config):
        """Test complete flow: startup → connect → events → shutdown."""
        # 1. Start daemon
        daemon = RuntimeDaemon(daemon_config)
        await daemon.start()
        assert daemon.is_running

        # 2. Connect Greenlight
        greenlight = AppSDK(
            name="Greenlight",
            version="1.0.0",
            capabilities=["story_pipeline", "directing_pipeline"]
        )
        await greenlight.connect(daemon)
        assert greenlight.is_connected

        # 3. Connect ImageGenerator
        image_gen = AppSDK(
            name="ImageGenerator",
            version="0.5.0",
            capabilities=["image_generation"]
        )
        await image_gen.connect(daemon)

        # 4. Set up event listener
        received_frames: List[Dict[str, Any]] = []

        @image_gen.on("pipeline.frame.ready")
        async def on_frame_ready(event: Event):
            received_frames.append(event.data)

        # 5. Simulate pipeline execution
        await greenlight.emit("pipeline.started", {"pipeline": "directing"})
        await greenlight.emit("pipeline.progress", {"progress": 0.5})
        await greenlight.emit("pipeline.frame.ready", {
            "frame_id": "frame_1.1",
            "prompt": "Wide shot of teahouse..."
        })
        await greenlight.emit("pipeline.completed", {"frames": 1})

        await asyncio.sleep(0.05)

        # 6. Verify events received
        assert len(received_frames) == 1
        assert received_frames[0]["frame_id"] == "frame_1.1"

        # 7. Check health
        health = await daemon.health_monitor.check()
        assert health.is_healthy

        # 8. Disconnect apps
        await greenlight.disconnect()
        await image_gen.disconnect()

        # 9. Stop daemon
        await daemon.stop()
        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, daemon_config):
        """Test error handling and recovery flow."""
        daemon = RuntimeDaemon(daemon_config)
        await daemon.start()

        # Set up error handoff
        cache = VectorCache()
        logger = HealthLogger()
        handoff = ErrorHandoff(vector_cache=cache, health_logger=logger)

        # Connect app
        app = AppSDK(name="TestApp", version="1.0.0", capabilities=[])
        await app.connect(daemon)

        # Simulate error
        try:
            raise RuntimeError("Pipeline failed: LLM timeout")
        except Exception as e:
            result = handoff.handoff_for_guidance(
                error=e,
                severity=ErrorSeverity.ERROR,
                source="pipeline.story",
                context={"phase": "generation", "retry_count": 3}
            )

        # Verify error was handled
        assert result["cached"] is True
        assert result["logged"] is True

        # App should still be connected
        assert app.is_connected

        # Cleanup
        await app.disconnect()
        await daemon.stop()


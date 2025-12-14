"""
Agnostic_Core_OS Runtime Demo

Demonstrates the Vector-Native Runtime Environment:
1. Starting the Runtime Daemon
2. Registering Apps via AppSDK
3. Inter-app communication via EventBus
4. Health monitoring and self-healing
5. Greenlight as the first integrated app

Run: py -m Agnostic_Core_OS.demo.runtime_demo
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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


class DemoApp:
    """Demo application showing runtime integration."""
    
    def __init__(self, name: str, sdk: AppSDK):
        self.name = name
        self.sdk = sdk
        self.messages_received = []
    
    async def handle_message(self, event: Event):
        """Handle incoming messages."""
        print(f"  [{self.name}] Received: {event.topic} -> {event.data}")
        self.messages_received.append(event)


async def demo_runtime_startup():
    """Demo 1: Starting the Runtime Daemon."""
    print("\n" + "="*60)
    print("DEMO 1: Runtime Daemon Startup")
    print("="*60)
    
    # Create daemon with config
    config = DaemonConfig(
        state_dir=Path(".runtime_demo"),
        auto_heal=True,
        health_check_interval=5.0
    )
    
    daemon = RuntimeDaemon(config)
    print(f"✓ Created RuntimeDaemon with config: {config}")
    
    # Start the daemon
    await daemon.start()
    print(f"✓ Daemon started: {daemon.state.value}")
    print(f"  - Daemon ID: {daemon.daemon_id}")
    print(f"  - State: {daemon.state.value}")
    
    return daemon


async def demo_app_registration(daemon: RuntimeDaemon):
    """Demo 2: App Registration via AppSDK."""
    print("\n" + "="*60)
    print("DEMO 2: App Registration via AppSDK")
    print("="*60)

    # Create SDK instances for two apps
    sdk1 = AppSDK(
        name="Greenlight",
        version="1.0.0",
        capabilities=["story_pipeline", "directing_pipeline", "world_bible"]
    )
    sdk2 = AppSDK(
        name="ImageGenerator",
        version="0.5.0",
        capabilities=["image_generation", "style_transfer"]
    )

    # Connect apps to daemon
    conn1 = await sdk1.connect(daemon)
    print(f"✓ Connected: {sdk1.name} v{sdk1.version}")
    print(f"  - App ID: {conn1.app_id}")
    print(f"  - Capabilities: {sdk1.capabilities}")

    conn2 = await sdk2.connect(daemon)
    print(f"✓ Connected: {sdk2.name} v{sdk2.version}")
    print(f"  - App ID: {conn2.app_id}")
    
    # Show registry stats
    stats = daemon.app_registry.get_stats()
    print(f"\n📊 Registry Stats:")
    print(f"  - Total Apps: {stats['total_apps']}")
    print(f"  - States: {stats['states']}")

    return sdk1, sdk2


async def demo_event_communication(sdk1: AppSDK, sdk2: AppSDK):
    """Demo 3: Inter-app Communication via EventBus."""
    print("\n" + "="*60)
    print("DEMO 3: Inter-app Communication via EventBus")
    print("="*60)
    
    received_events = []
    
    # Subscribe sdk2 to pipeline events
    @sdk2.on("pipeline.*")
    async def handle_pipeline_event(event: Event):
        print(f"  [ImageGenerator] Received pipeline event: {event.topic}")
        received_events.append(event)
    
    # Subscribe to specific topic
    @sdk2.on("storyboard.frame.ready")
    async def handle_frame_ready(event: Event):
        print(f"  [ImageGenerator] Frame ready for generation: {event.data}")
        received_events.append(event)
    
    # Emit events from Greenlight
    print("\n📤 Greenlight emitting events...")
    
    await sdk1.emit("pipeline.started", {
        "pipeline": "directing",
        "project": "Go for Orchid"
    })
    
    await sdk1.emit("pipeline.progress", {
        "pipeline": "directing",
        "progress": 0.5,
        "current_beat": "B03"
    })
    
    await sdk1.emit("storyboard.frame.ready", {
        "frame_id": "frame_1.3",
        "prompt": "Wide shot of ancient teahouse at dawn...",
        "camera": "[CAM: WIDE, EYE_LEVEL, STATIC, NORMAL]"
    })
    
    await sdk1.emit("pipeline.completed", {
        "pipeline": "directing",
        "total_frames": 24
    })
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    print(f"\n📥 ImageGenerator received {len(received_events)} events")
    return received_events


async def demo_health_monitoring(daemon: RuntimeDaemon):
    """Demo 4: Health Monitoring and Self-Healing."""
    print("\n" + "="*60)
    print("DEMO 4: Health Monitoring and Self-Healing")
    print("="*60)

    monitor = daemon.health_monitor

    # Run health check
    health = await monitor.check()
    print(f"✓ Health Check Complete")
    print(f"  - Status: {health.status.value.upper()}")
    print(f"  - Is Healthy: {health.is_healthy}")
    print(f"  - Metrics: {health.metrics}")

    if health.issues:
        print(f"  - Issues Found: {len(health.issues)}")
        for issue in health.issues:
            print(f"    • [{issue.severity}] {issue.component}: {issue.message}")

        # Attempt self-healing
        print("\n🔧 Attempting self-healing...")
        heal_result = await monitor.heal()
        print(f"  - Fixed: {len(heal_result['fixed'])}")
        print(f"  - Failed: {len(heal_result['failed'])}")

    # Generate health report
    report = monitor.generate_report()
    print(f"\n📋 Health Report Preview:")
    print("-" * 40)
    for line in report.split("\n")[:15]:
        print(f"  {line}")
    print("  ...")

    return health


async def demo_vector_routing():
    """Demo 5: Vector Routing and Error Handoff."""
    print("\n" + "="*60)
    print("DEMO 5: Vector Routing and Error Handoff")
    print("="*60)

    # Create core routing components
    cache = VectorCache()
    health_logger = HealthLogger()
    error_handoff = ErrorHandoff(vector_cache=cache, health_logger=health_logger)

    print("✓ Created Core Routing components")

    # Add some entries to vector cache
    cache.add(
        content="@CHAR_MEI → Character lookup for Mei",
        entry_type=CacheEntryType.NOTATION_DEFINITION,
        weight=VectorWeight.ACTIVE.value,
        notation="@CHAR_MEI"
    )

    cache.add(
        content=">story standard → Run standard story pipeline",
        entry_type=CacheEntryType.NOTATION_DEFINITION,
        weight=VectorWeight.ACTIVE.value,
        notation=">story standard"
    )

    print(f"✓ Added {cache.count} entries to VectorCache")
    print(f"  - Cache size: {cache.size_bytes} bytes")

    # Simulate an error and handoff
    print("\n🚨 Simulating error handoff...")
    try:
        raise ValueError("Pipeline configuration missing: 'llm_model' not specified")
    except Exception as e:
        result = error_handoff.handoff_for_guidance(
            error=e,
            severity=ErrorSeverity.ERROR,
            source="demo_pipeline",
            context={"pipeline": "story", "phase": "initialization"}
        )

        print(f"✓ Error Handoff Complete")
        print(f"  - Transcript ID: {result['transcript_id']}")
        print(f"  - Task ID: {result.get('task_id', 'N/A')}")
        print(f"  - Cached: {result['cached']}")
        print(f"  - Logged: {result['logged']}")

    # Log notation definition
    health_logger.log_notation(
        notation="@CHAR_MEI",
        translation="Look up character Mei in world bible",
        scope="WORLD_BIBLE",
        examples=["@CHAR_MEI #STORY", "@CHAR_MEI +relationships"]
    )

    print(f"\n📊 Health Logger Stats: {health_logger.get_stats()}")

    return cache, health_logger, error_handoff


async def demo_greenlight_integration(daemon: RuntimeDaemon):
    """Demo 6: Greenlight as First Integrated App."""
    print("\n" + "="*60)
    print("DEMO 6: Greenlight Integration Preview")
    print("="*60)

    # Create SDK with full Greenlight capabilities
    sdk = AppSDK(
        name="Project Greenlight",
        version="1.0.0",
        capabilities=[
            "story_pipeline",
            "directing_pipeline",
            "world_bible",
            "tag_extraction",
            "multi_agent_consensus",
            "procedural_generation"
        ]
    )

    # Connect to daemon
    conn = await sdk.connect(daemon)

    print(f"✓ Greenlight Connected")
    print(f"  - App ID: {conn.app_id}")
    print(f"  - Capabilities: {len(sdk.capabilities)}")

    # Simulate pipeline events that would be emitted
    pipeline_events = [
        ("greenlight.project.loaded", {"project": "Go for Orchid", "path": "projects/Go for Orchid"}),
        ("greenlight.pipeline.writer.started", {"input": "A story about honor and redemption..."}),
        ("greenlight.pipeline.writer.progress", {"phase": "story_generation", "progress": 0.3}),
        ("greenlight.pipeline.writer.progress", {"phase": "beat_extraction", "progress": 0.6}),
        ("greenlight.pipeline.writer.progress", {"phase": "tag_consensus", "progress": 0.8}),
        ("greenlight.pipeline.writer.completed", {"beats": 24, "tags": 156}),
        ("greenlight.pipeline.director.started", {"beats": 24}),
        ("greenlight.pipeline.director.frame_ready", {"frame_id": "frame_1.1", "prompt": "..."}),
        ("greenlight.pipeline.director.completed", {"frames": 72}),
    ]

    print(f"\n📤 Simulating Greenlight pipeline events...")
    for topic, data in pipeline_events:
        await sdk.emit(topic, data)
        print(f"  → {topic}")

    print(f"\n✓ Emitted {len(pipeline_events)} events")

    return sdk


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  AGNOSTIC_CORE_OS RUNTIME DEMO")
    print("  Vector-Native Runtime Environment")
    print("="*60)

    try:
        # Demo 1: Start daemon
        daemon = await demo_runtime_startup()

        # Demo 2: Register apps
        sdk1, sdk2 = await demo_app_registration(daemon)

        # Demo 3: Event communication
        await demo_event_communication(sdk1, sdk2)

        # Demo 4: Health monitoring
        await demo_health_monitoring(daemon)

        # Demo 5: Vector routing
        await demo_vector_routing()

        # Demo 6: Greenlight integration
        await demo_greenlight_integration(daemon)

        # Cleanup
        print("\n" + "="*60)
        print("CLEANUP")
        print("="*60)
        await daemon.stop()
        print(f"✓ Daemon stopped: {daemon.state.value}")

        print("\n" + "="*60)
        print("  DEMO COMPLETE!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


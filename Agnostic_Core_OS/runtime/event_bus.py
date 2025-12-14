"""
Agnostic_Core_OS Event Bus

Inter-application communication via pub/sub messaging.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union
from datetime import datetime
from enum import Enum
import asyncio
import logging
import uuid

logger = logging.getLogger("agnostic_core_os.runtime.event_bus")


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """An event in the event bus."""
    event_id: str
    topic: str
    data: Any
    source_app: str
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "data": self.data,
            "source_app": self.source_app,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


@dataclass
class Subscription:
    """A subscription to an event topic."""
    sub_id: str
    topic: str
    handler: EventHandler
    app_id: str
    filter_fn: Optional[Callable[[Event], bool]] = None
    created_at: datetime = field(default_factory=datetime.now)


class EventBus:
    """
    Event Bus for inter-app communication.
    
    Features:
    - Pub/sub messaging
    - Topic-based routing
    - Priority queuing
    - Async event handling
    - Event filtering
    
    Usage:
        bus = EventBus()
        
        # Subscribe to events
        async def handler(event: Event):
            print(f"Received: {event.data}")
        
        sub_id = bus.subscribe("my_topic", handler, app_id="my_app")
        
        # Emit events
        await bus.emit("my_topic", {"message": "hello"}, source_app="sender")
    """
    
    def __init__(self, queue_size: int = 1000):
        self.queue_size = queue_size
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._processing = False
        self._process_task: Optional[asyncio.Task] = None
        self._events_processed = 0
        self._events_emitted = 0
        self._next_sub_id = 0
    
    @property
    def pending_count(self) -> int:
        return self._event_queue.qsize()
    
    def _generate_event_id(self) -> str:
        return f"evt_{uuid.uuid4().hex[:12]}"
    
    def _generate_sub_id(self) -> str:
        self._next_sub_id += 1
        return f"sub_{self._next_sub_id:06d}"
    
    def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        app_id: str,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """
        Subscribe to a topic.
        
        Args:
            topic: Topic to subscribe to (supports wildcards: "app.*")
            handler: Async function to handle events
            app_id: ID of the subscribing app
            filter_fn: Optional filter function
            
        Returns:
            Subscription ID
        """
        sub_id = self._generate_sub_id()
        subscription = Subscription(
            sub_id=sub_id,
            topic=topic,
            handler=handler,
            app_id=app_id,
            filter_fn=filter_fn,
        )
        
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        
        self._subscriptions[topic].append(subscription)
        logger.debug(f"Subscription created: {sub_id} for topic '{topic}'")
        return sub_id
    
    def unsubscribe(self, sub_id: str) -> bool:
        """Unsubscribe by subscription ID."""
        for topic, subs in self._subscriptions.items():
            for sub in subs:
                if sub.sub_id == sub_id:
                    subs.remove(sub)
                    logger.debug(f"Subscription removed: {sub_id}")
                    return True
        return False
    
    def unsubscribe_app(self, app_id: str) -> int:
        """Unsubscribe all subscriptions for an app."""
        count = 0
        for topic, subs in self._subscriptions.items():
            to_remove = [s for s in subs if s.app_id == app_id]
            for sub in to_remove:
                subs.remove(sub)
                count += 1
        logger.debug(f"Removed {count} subscriptions for app {app_id}")
        return count

    async def emit(
        self,
        topic: str,
        data: Any,
        source_app: str,
        priority: EventPriority = EventPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Emit an event to a topic.

        Args:
            topic: Topic to emit to
            data: Event data
            source_app: ID of the emitting app
            priority: Event priority
            metadata: Additional metadata

        Returns:
            Event ID
        """
        event = Event(
            event_id=self._generate_event_id(),
            topic=topic,
            data=data,
            source_app=source_app,
            priority=priority,
            metadata=metadata or {},
        )

        await self._event_queue.put(event)
        self._events_emitted += 1
        logger.debug(f"Event emitted: {event.event_id} to '{topic}'")

        # Process immediately if not in background mode
        if not self._processing:
            await self._process_event(event)

        return event.event_id

    async def emit_sync(
        self,
        topic: str,
        data: Any,
        source_app: str,
    ) -> List[Any]:
        """Emit and wait for all handlers to complete."""
        event = Event(
            event_id=self._generate_event_id(),
            topic=topic,
            data=data,
            source_app=source_app,
        )

        results = await self._process_event(event)
        return results

    async def _process_event(self, event: Event) -> List[Any]:
        """Process a single event."""
        results = []
        handlers = self._get_handlers(event.topic)

        for sub in handlers:
            try:
                # Apply filter if present
                if sub.filter_fn and not sub.filter_fn(event):
                    continue

                result = await sub.handler(event)
                results.append(result)

            except Exception as e:
                logger.error(f"Handler error for {sub.sub_id}: {e}")

        self._events_processed += 1
        return results

    def _get_handlers(self, topic: str) -> List[Subscription]:
        """Get all handlers for a topic (including wildcards)."""
        handlers = []

        # Exact match
        if topic in self._subscriptions:
            handlers.extend(self._subscriptions[topic])

        # Wildcard matches
        for sub_topic, subs in self._subscriptions.items():
            if sub_topic.endswith(".*"):
                prefix = sub_topic[:-2]
                if topic.startswith(prefix):
                    handlers.extend(subs)
            elif sub_topic == "*":
                handlers.extend(subs)

        return handlers

    async def start_processing(self) -> None:
        """Start background event processing."""
        if self._processing:
            return

        self._processing = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("Event bus processing started")

    async def stop_processing(self) -> None:
        """Stop background event processing."""
        self._processing = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus processing stopped")

    async def _process_loop(self) -> None:
        """Background processing loop."""
        while self._processing:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        topic_counts = {
            topic: len(subs) for topic, subs in self._subscriptions.items()
        }

        return {
            "events_emitted": self._events_emitted,
            "events_processed": self._events_processed,
            "pending": self.pending_count,
            "queue_size": self.queue_size,
            "topics": list(self._subscriptions.keys()),
            "subscriptions_by_topic": topic_counts,
            "processing": self._processing,
        }


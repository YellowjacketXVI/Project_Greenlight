"""SSE (Server-Sent Events) router for real-time pipeline updates.

Provides streaming endpoints for clients to receive real-time updates
during pipeline execution (story phase, storyboard phase, etc.).
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Optional, AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from greenlight.core.logging_config import get_logger

logger = get_logger("api.sse")

router = APIRouter()

# Global event queues per pipeline
# Key: pipeline_id, Value: asyncio.Queue of SSE events
_event_queues: Dict[str, asyncio.Queue] = {}

# Pipeline completion flags
_pipeline_complete: Dict[str, bool] = {}


class SSEEvent(BaseModel):
    """SSE event structure."""
    event: str  # Event type: pass_start, pass_complete, reference_generated, etc.
    data: dict  # Event payload


def create_event_queue(pipeline_id: str) -> asyncio.Queue:
    """Create a new event queue for a pipeline."""
    queue = asyncio.Queue()
    _event_queues[pipeline_id] = queue
    _pipeline_complete[pipeline_id] = False
    return queue


def get_event_queue(pipeline_id: str) -> Optional[asyncio.Queue]:
    """Get the event queue for a pipeline."""
    return _event_queues.get(pipeline_id)


async def emit_event(pipeline_id: str, event_type: str, data: dict):
    """Emit an event to all listeners for a pipeline.

    This is the callback function passed to pipeline methods.
    """
    queue = _event_queues.get(pipeline_id)
    if queue:
        event = SSEEvent(event=event_type, data=data)
        await queue.put(event)

        # Mark pipeline complete on terminal events
        if event_type in ("story_phase_complete", "storyboard_complete", "error"):
            _pipeline_complete[pipeline_id] = True


def cleanup_pipeline(pipeline_id: str):
    """Clean up resources for a completed pipeline."""
    if pipeline_id in _event_queues:
        del _event_queues[pipeline_id]
    if pipeline_id in _pipeline_complete:
        del _pipeline_complete[pipeline_id]


async def event_generator(pipeline_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Generate SSE events for a pipeline."""
    queue = get_event_queue(pipeline_id)

    if not queue:
        # Pipeline not found or already completed
        yield f"event: error\ndata: {json.dumps({'message': 'Pipeline not found'})}\n\n"
        return

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"SSE client disconnected from pipeline {pipeline_id}")
                break

            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(queue.get(), timeout=30.0)

                # Format as SSE
                event_str = f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
                yield event_str

                # Check if pipeline is complete
                if _pipeline_complete.get(pipeline_id, False) and queue.empty():
                    logger.info(f"Pipeline {pipeline_id} complete, closing SSE stream")
                    break

            except asyncio.TimeoutError:
                # Send keepalive ping
                yield f": keepalive\n\n"

    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for pipeline {pipeline_id}")
    finally:
        # Don't cleanup here - let the pipeline runner do it
        pass


@router.get("/stream/{pipeline_id:path}")
async def stream_pipeline_events(pipeline_id: str, request: Request):
    """Stream SSE events for a pipeline.

    Event types:
    - pass_start: Pipeline pass starting
    - pass_complete: Pipeline pass completed
    - reference_generated: Reference image generated
    - keyframe_generated: Key frame generated
    - prompt_written: Frame prompt written
    - frame_generated: Fill frame generated
    - story_phase_complete: Story phase finished
    - storyboard_complete: Storyboard phase finished
    - error: Pipeline error occurred
    - paused: Pipeline paused for user input
    """
    return StreamingResponse(
        event_generator(pipeline_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/status/{pipeline_id:path}")
async def get_pipeline_sse_status(pipeline_id: str):
    """Check if a pipeline has an active SSE stream."""
    is_active = pipeline_id in _event_queues
    is_complete = _pipeline_complete.get(pipeline_id, False)

    return {
        "pipeline_id": pipeline_id,
        "active": is_active,
        "complete": is_complete
    }

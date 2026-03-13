"""
SSE (Server-Sent Events) queue management.

Each active pipeline session gets its own asyncio.Queue.  Tools and the
background pipeline task push events; the FastAPI SSE generator consumes them.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

_queues: dict[str, asyncio.Queue] = {}


def create_queue(session_id: str) -> asyncio.Queue:
    """Create and register a new SSE queue for a session."""
    q: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = q
    return q


def get_queue(session_id: str) -> asyncio.Queue | None:
    return _queues.get(session_id)


async def stream_to_client(session_id: str, event: dict) -> None:
    """
    Push an SSE event dict to the session's queue.

    Silently no-ops if no queue exists (e.g. during unit tests or
    after the SSE connection has been closed).
    """
    q = _queues.get(session_id)
    if q is not None:
        await q.put(event)
    else:
        logger.debug("No SSE queue for session %s (event: %s)", session_id, event.get("type"))


def remove_queue(session_id: str) -> None:
    _queues.pop(session_id, None)

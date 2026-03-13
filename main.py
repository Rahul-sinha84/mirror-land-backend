"""
Mirror Land Backend — FastAPI server with SSE streaming.

Endpoints:
  POST /api/create-story   — Start the ADK pipeline, returns SSE stream
  POST /api/next-chapter   — Fetch pre-generated level data for a chapter
  GET  /api/assets/{path}  — Serve generated asset files (images, audio, JSON)
"""

import asyncio
import json
import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from sse_starlette.sse import EventSourceResponse

from agent.agent import creative_director
from agent.tools import _safe_parse_json, prefetch_chapter_level
from sse import create_queue, remove_queue, stream_to_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

APP_NAME = "mirror_land"
ASSETS_DIR = os.path.join("static", "assets")
PIPELINE_TIMEOUT = 600  # 10 minutes

os.makedirs(ASSETS_DIR, exist_ok=True)

app = FastAPI(title="Mirror Land Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------

async def _prefetch_remaining_chapters(session_id: str) -> None:
    """Pre-fetch chapters 2 and 3 in the background (bypasses ADK overhead)."""
    try:
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id="web",
            session_id=session_id,
        )
        if session is None:
            logger.warning("[%s] Prefetch: session not found", session_id)
            return

        story_plan = _safe_parse_json(session.state.get("story_plan", "{}"))
        story_pack = _safe_parse_json(session.state.get("story_pack", "{}"))

        if not story_plan:
            logger.warning("[%s] Prefetch: no story_plan in state", session_id)
            return

        for ch_num in (2, 3):
            level_file = os.path.join(ASSETS_DIR, session_id, f"level_ch{ch_num:02d}.json")
            if os.path.exists(level_file):
                logger.info("[%s] Prefetch: ch%d already on disk, skipping", session_id, ch_num)
                continue

            await prefetch_chapter_level(ch_num, session_id, story_plan, story_pack)

    except Exception as e:
        logger.error("[%s] Prefetch failed: %s", session_id, e, exc_info=True)


async def _run_pipeline(session_id: str, prompt: str) -> None:
    """Run the full CreativeDirector pipeline and push SSE events."""
    try:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id="web",
            session_id=session_id,
            state={"session_id": session_id},
        )

        runner = Runner(
            agent=creative_director,
            app_name=APP_NAME,
            session_service=session_service,
        )

        content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        logger.info("[%s] Pipeline started — prompt: %s", session_id, prompt[:80])

        async for event in runner.run_async(
            user_id="web",
            session_id=session.id,
            new_message=content,
        ):
            pass  # Tools push granular SSE events; we just drain the runner.

        logger.info("[%s] Pipeline completed", session_id)
        await stream_to_client(session_id, {"type": "complete", "data": {}})

        asyncio.create_task(_prefetch_remaining_chapters(session_id))

    except Exception as e:
        logger.error("[%s] Pipeline failed: %s", session_id, e, exc_info=True)
        await stream_to_client(session_id, {
            "type": "error",
            "data": {"message": str(e)},
        })
        await stream_to_client(session_id, {"type": "complete", "data": {}})


# ---------------------------------------------------------------------------
# POST /api/create-story
# ---------------------------------------------------------------------------

@app.post("/api/create-story")
async def create_story(request: Request):
    """
    Start a new story generation pipeline.

    Request body: {"prompt": "A tiny astronaut exploring candy planets"}
    Response: SSE stream of generation events.
    """
    body = await request.json()
    prompt = body.get("prompt", "").strip()

    if not prompt:
        return JSONResponse(
            status_code=400,
            content={"error": "prompt is required"},
        )

    session_id = str(uuid.uuid4())[:8]
    queue = create_queue(session_id)

    await stream_to_client(session_id, {
        "type": "session",
        "data": {"session_id": session_id},
    })

    asyncio.create_task(_run_pipeline(session_id, prompt))

    async def event_generator():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=PIPELINE_TIMEOUT)
                yield {
                    "event": event["type"],
                    "data": json.dumps(event.get("data", {})),
                }
                if event["type"] == "complete":
                    break
        except asyncio.TimeoutError:
            yield {
                "event": "error",
                "data": json.dumps({"message": "Pipeline timed out"}),
            }
        finally:
            remove_queue(session_id)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# POST /api/next-chapter
# ---------------------------------------------------------------------------

def _build_chapter_response(session_id: str, chapter_number: int) -> dict | None:
    """Read pre-generated chapter data from disk. Returns None if not found."""
    session_dir = os.path.join(ASSETS_DIR, session_id)
    level_file = os.path.join(session_dir, f"level_ch{chapter_number:02d}.json")

    if not os.path.exists(level_file):
        return None

    with open(level_file) as f:
        level_json = json.load(f)

    bg_file = os.path.join(session_dir, f"ch{chapter_number:02d}_bg.png")
    music_file = os.path.join(session_dir, f"ch{chapter_number:02d}_ambient.wav")

    return {
        "chapter_number": chapter_number,
        "level_json": level_json,
        "background_url": (
            f"/api/assets/{session_id}/ch{chapter_number:02d}_bg.png"
            if os.path.exists(bg_file)
            else None
        ),
        "music_url": (
            f"/api/assets/{session_id}/ch{chapter_number:02d}_ambient.wav"
            if os.path.exists(music_file)
            else None
        ),
    }


@app.post("/api/next-chapter")
async def next_chapter(request: Request):
    """
    Return level data for a specific chapter.

    Checks disk first (pre-fetched or pipeline-generated).
    Falls back to on-demand generation if not yet available.

    Request body: {"session_id": "abc123", "chapter_number": 2}
    Response: JSON with level_json, background_url, music_url.
    """
    body = await request.json()
    session_id = body.get("session_id", "")
    chapter_number = body.get("chapter_number", 0)

    if not session_id or not chapter_number:
        return JSONResponse(
            status_code=400,
            content={"error": "session_id and chapter_number are required"},
        )

    cached = _build_chapter_response(session_id, chapter_number)
    if cached is not None:
        return JSONResponse(content=cached)

    # On-demand fallback: generate the chapter directly
    logger.info("[%s] On-demand generation for chapter %d", session_id, chapter_number)

    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id="web",
        session_id=session_id,
    )
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found. Create a story first."},
        )

    story_plan = _safe_parse_json(session.state.get("story_plan", "{}"))
    story_pack = _safe_parse_json(session.state.get("story_pack", "{}"))

    if not story_plan:
        return JSONResponse(
            status_code=404,
            content={"error": "Story plan not available. Pipeline may still be running."},
        )

    result = await prefetch_chapter_level(
        chapter_number, session_id, story_plan, story_pack,
    )

    if result.get("status") == "error":
        return JSONResponse(status_code=500, content=result)

    generated = _build_chapter_response(session_id, chapter_number)
    if generated is not None:
        return JSONResponse(content=generated)

    return JSONResponse(status_code=500, content={
        "error": "Chapter generation completed but level file not found on disk.",
    })


# ---------------------------------------------------------------------------
# GET /api/assets/{path}  — static file serving
# ---------------------------------------------------------------------------

@app.get("/api/assets/{path:path}")
async def serve_asset(path: str):
    """Serve a generated asset file (image, audio, JSON)."""
    file_path = os.path.realpath(os.path.join(ASSETS_DIR, path))
    safe_root = os.path.realpath(ASSETS_DIR)

    if not file_path.startswith(safe_root):
        return JSONResponse(status_code=403, content={"error": "Forbidden"})

    if not os.path.isfile(file_path):
        return JSONResponse(status_code=404, content={"error": "Asset not found"})

    return FileResponse(file_path)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}

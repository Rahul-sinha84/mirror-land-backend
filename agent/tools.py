"""
ADK tool functions for the CreativeDirector pipeline.

These are called by LlmAgents via ToolContext. Each tool reads shared
session state (story_plan, story_pack) and writes results back.
SSE events are pushed to the client queue as assets are generated.
"""

import asyncio
import json
import logging
import os

from google.adk.tools import ToolContext

from services.audio_gen import generate_ambient_music
from services.image_gen import generate_story_assets
from services.level_gen import generate_chapter_background, generate_level_json
from sse import stream_to_client

logger = logging.getLogger(__name__)

ASSETS_ROOT = "static/assets"


def _get_output_dir(tool_context: ToolContext) -> str:
    session_id = tool_context.state.get("session_id", "default")
    output_dir = os.path.join(ASSETS_ROOT, session_id)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _safe_parse_json(raw) -> dict:
    """Parse a JSON string or return it if already a dict."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _asset_url(session_id: str, filepath: str) -> str:
    return f"/api/assets/{session_id}/{os.path.basename(filepath)}"


async def generate_assets(tool_context: ToolContext) -> dict:
    """
    Generate all game sprites and background art for the story.

    Reads story_plan from session state, generates 5 game assets
    (character, enemy_1, platform, npc, background) via Gemini image model,
    runs sprite background removal, and saves everything to disk.

    Returns:
        dict with status and asset file paths.
    """
    story_plan = _safe_parse_json(tool_context.state.get("story_plan", "{}"))
    if not story_plan:
        return {"status": "error", "message": "story_plan missing or invalid in session state"}

    session_id = tool_context.state.get("session_id", "default")

    await stream_to_client(session_id, {
        "type": "story_plan",
        "data": story_plan,
    })

    output_dir = _get_output_dir(tool_context)

    try:
        assets = await generate_story_assets(story_plan, output_dir)
        tool_context.state["asset_paths"] = json.dumps(assets)

        for role, path in assets.items():
            await stream_to_client(session_id, {
                "type": "image",
                "data": {"role": role, "url": _asset_url(session_id, path)},
            })

        return {"status": "success", "assets": assets}
    except Exception as e:
        logger.error("Asset generation failed: %s", e, exc_info=True)
        await stream_to_client(session_id, {
            "type": "error",
            "data": {"message": f"Asset generation failed: {e}"},
        })
        return {"status": "error", "message": str(e)}


async def generate_chapter_level(chapter_number: int, tool_context: ToolContext) -> dict:
    """
    Generate a complete playable level for a specific chapter.

    Runs level JSON generation, chapter background image, and ambient music
    in parallel. Reads story_plan and story_pack from session state.

    Args:
        chapter_number: The chapter number (1, 2, or 3) to generate.

    Returns:
        dict with level_json, background_url, music_url, and level_path.
    """
    story_plan = _safe_parse_json(tool_context.state.get("story_plan", "{}"))
    story_pack = _safe_parse_json(tool_context.state.get("story_pack", "{}"))
    session_id = tool_context.state.get("session_id", "default")

    chapters = story_plan.get("chapters", [])
    chapter = None
    for ch in chapters:
        if ch.get("chapter_number") == chapter_number:
            chapter = ch
            break

    if chapter is None:
        return {"status": "error", "message": f"Chapter {chapter_number} not found in story plan"}

    output_dir = _get_output_dir(tool_context)
    art_style = story_plan.get("art_style", "retro_pixel")
    mood = story_plan.get("mood", "adventure")
    setting = chapter.get("setting", "a game world")

    music_path = os.path.join(output_dir, f"ch{chapter_number:02d}_ambient.wav")
    music_prompt = f"{setting}, {art_style} aesthetic"

    level_task = generate_level_json(chapter, story_plan, story_pack)
    bg_task = generate_chapter_background(chapter, art_style, output_dir)
    music_task = generate_ambient_music(music_prompt, mood, music_path)

    level_json, bg_path, music_result = await asyncio.gather(
        level_task, bg_task, music_task,
        return_exceptions=True,
    )

    result: dict = {"status": "success", "chapter_number": chapter_number}

    if isinstance(level_json, Exception):
        logger.error("Level JSON failed for ch%d: %s", chapter_number, level_json)
        result["level_json"] = None
        result["level_error"] = str(level_json)
    else:
        level_path = os.path.join(output_dir, f"level_ch{chapter_number:02d}.json")
        with open(level_path, "w") as f:
            json.dump(level_json, f, indent=2)
        result["level_json"] = level_json
        result["level_path"] = level_path

    bg_url = None
    if isinstance(bg_path, Exception):
        logger.error("Background failed for ch%d: %s", chapter_number, bg_path)
    else:
        bg_url = _asset_url(session_id, bg_path)
        result["background_url"] = bg_path

    music_url = None
    if isinstance(music_result, Exception) or music_result is None:
        result["music_url"] = None
    else:
        music_url = _asset_url(session_id, music_result)
        result["music_url"] = music_result

    if not isinstance(level_json, Exception):
        await stream_to_client(session_id, {
            "type": "level_ready",
            "data": {
                "chapter_number": chapter_number,
                "level_json": level_json,
                "background_url": bg_url,
                "music_url": music_url,
            },
        })

    if music_url:
        await stream_to_client(session_id, {
            "type": "audio",
            "data": {"role": f"ch{chapter_number:02d}_ambient", "url": music_url},
        })

    return result

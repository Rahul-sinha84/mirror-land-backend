"""
Level generation service.

- generate_level_json: calls Gemini to produce a complete level layout JSON
  for a given chapter, then validates and auto-fixes it.
- generate_chapter_background: generates a chapter-specific background image
  via Gemini image model, resized to 1920x1080.
"""

import io
import json
import logging
import os

from PIL import Image
from google.genai import types

from agent.prompts import LEVEL_BUILDER_INSTRUCTION
from level_validator import validate_and_fix_level
from services.gemini_client import get_client
from services.image_gen import (
    ART_STYLE_DESCRIPTIONS,
    ART_STYLE_NAMES,
    BACKGROUND_SIZE,
    IMAGE_MODEL,
)

logger = logging.getLogger(__name__)

LEVEL_MODEL = "gemini-2.5-flash"


async def generate_level_json(
    chapter: dict,
    story_plan: dict,
    story_pack: dict,
) -> dict:
    """
    Generate a validated level layout JSON for a single chapter.

    Calls Gemini in JSON mode with the LEVEL_BUILDER_INSTRUCTION, feeds it
    the chapter details and story context, then runs validate_and_fix_level.
    """
    client = get_client()

    chapter_num = chapter.get("chapter_number", 1)
    art_style = story_plan.get("art_style", "retro_pixel")
    characters = story_plan.get("characters", {})

    user_message = (
        f"Generate a level layout for Chapter {chapter_num}: "
        f'"{chapter.get("title", "Untitled")}"\n\n'
        f"Setting: {chapter.get('setting', 'a game world')}\n"
        f"Narration: {chapter.get('narration', '')}\n"
        f"Art style: {art_style}\n"
        f"Difficulty: {chapter.get('difficulty', 'easy')}\n\n"
        f"Mission: {json.dumps(chapter.get('mission', {}))}\n"
        f"Mechanics: {json.dumps(chapter.get('mechanics', {}))}\n\n"
        f"Characters: {json.dumps(characters)}\n"
        f"Available assets: {json.dumps(story_pack)}\n"
    )

    logger.info("Generating level JSON for chapter %d with model %s...", chapter_num, LEVEL_MODEL)

    response = await client.aio.models.generate_content(
        model=LEVEL_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=LEVEL_BUILDER_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )

    level = json.loads(response.text)
    logger.info("Raw level JSON received for chapter %d (%d platforms, %d enemies)",
                chapter_num,
                len(level.get("platforms", [])),
                len(level.get("enemies", [])))

    level = validate_and_fix_level(level)
    logger.info("Level validated and fixed for chapter %d", chapter_num)

    return level


async def generate_chapter_background(
    chapter: dict,
    art_style: str,
    output_dir: str,
) -> str:
    """
    Generate a wide background image for a specific chapter.

    Returns the saved file path.
    """
    client = get_client()
    os.makedirs(output_dir, exist_ok=True)

    style_name = ART_STYLE_NAMES.get(art_style, f"{art_style} art")
    style_desc = ART_STYLE_DESCRIPTIONS.get(art_style, art_style)
    chapter_num = chapter.get("chapter_number", 1)
    setting = chapter.get("setting", "a game world")

    prompt = (
        f"Wide 2D side-scrolling game background, 1920x1080. "
        f"Minimalist {style_name}, clean lines, simple shapes. "
        f"Art style: {style_desc}. "
        f"Scene: {setting}. "
        f"Top 20-30%: decorative elements only (sky, distant shapes, 2-4 simple objects). "
        f"Middle 40-50%: plain, low detail, empty for gameplay. "
        f"Bottom 20-30%: ground shapes only. "
        f"Max 2-4 decorative objects per side. No texture-heavy details in middle lane. "
        f"Sparse, lots of empty space. Seamless horizontal tile for parallax. "
        f"No characters, no UI, no text."
    )

    logger.info("Generating chapter %d background...", chapter_num)
    response = await client.aio.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            temperature=1.0,
        ),
    )

    image_data = None
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_data = part.inline_data.data
            break

    if not image_data:
        raise RuntimeError(f"Gemini returned no image for chapter {chapter_num} background.")

    img = Image.open(io.BytesIO(image_data)).convert("RGB")
    if img.size != BACKGROUND_SIZE:
        img = img.resize(BACKGROUND_SIZE, Image.Resampling.LANCZOS)
        logger.info("Resized chapter %d background to %s", chapter_num, BACKGROUND_SIZE)

    filename = f"ch{chapter_num:02d}_bg.png"
    out_path = os.path.join(output_dir, filename)
    img.save(out_path, "PNG")
    logger.info("Saved chapter %d background -> %s (%dx%d)", chapter_num, out_path, img.width, img.height)

    return out_path

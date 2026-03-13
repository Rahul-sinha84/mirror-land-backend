"""
Image generation service using Gemini interleaved output (TEXT + IMAGE).

Generates 5 game assets in a single Gemini call:
  - character  (hero sprite, white bg, 1024x1024)
  - enemy_1    (enemy sprite, white bg, 1024x1024)
  - platform   (tile sprite, white bg, 1024x1024)
  - npc        (NPC sprite, white bg, 1024x1024)
  - background (full scene, 1920x1080, no cleanup)

Uses [ASSET: role_name] labels in the prompt so the backend can identify each image.
Sprites use solid white #FFFFFF background for reliable rembg cleanup.
"""

import io
import logging
import os
import re

from PIL import Image
from google.genai import types

from services.gemini_client import get_client
from services.sprite_cleaner import remove_background

logger = logging.getLogger(__name__)

IMAGE_MODEL = "gemini-2.5-flash-image"
SPRITE_ROLES = {"character", "enemy_1", "platform", "npc"}
ALL_ROLES = {"character", "enemy_1", "platform", "npc", "background"}
BACKGROUND_SIZE = (1920, 1080)

ART_STYLE_NAMES = {
    "retro_pixel": "retro pixel art",
    "flat_vector": "flat vector art",
    "neon_cyberpunk": "neon cyberpunk art",
    "watercolor": "watercolor art",
    "ink_manga": "ink manga art",
    "chalk": "chalk art",
    "gothic": "gothic art",
}

ART_STYLE_DESCRIPTIONS = {
    "retro_pixel": "8-bit pixel art, bold primary colors, chunky outlines, nostalgic NES feel",
    "flat_vector": "clean geometric shapes, smooth gradients, no outlines, atmospheric lighting",
    "neon_cyberpunk": "pure black background, glowing neon outlines in pink/cyan/purple, synthwave aesthetic",
    "watercolor": "soft bleeding edges, pastel washes, paper texture feel, dreamy",
    "ink_manga": "bold black ink strokes on white/cream, halftone dot shading, high contrast",
    "chalk": "colorful chalk strokes on dark blackboard background, hand-drawn feel",
    "gothic": "dark and moody, deep reds/blacks/grays, stone textures, dramatic shadows",
}

SPRITE_CONSTRAINTS = """\
side profile strictly facing right, full body visible, centered, \
solid opaque body, simple round compact silhouette, minimal detail, \
no thin strands/particles/fog, \
solid flat white #FFFFFF background edge-to-edge, 1024x1024, game sprite."""

PLATFORM_CONSTRAINTS = """\
side view with clear top surface, simple readable shape, tileable horizontally, \
solid opaque, solid flat white #FFFFFF background edge-to-edge, 1024x1024, game sprite."""


def _derive_theme_name(story_plan: dict) -> str:
    """Derive a short theme name from the story plan for use in prompts."""
    ch1 = story_plan.get("chapters", [{}])[0]
    setting = ch1.get("setting", "")
    title = story_plan.get("title", "")
    if setting:
        words = setting.split()[:4]
        return " ".join(words).rstrip(",.")
    return title.lower()


def _build_asset_prompt(story_plan: dict) -> str:
    """Build the interleaved generation prompt with [ASSET: role] labels."""
    art_style = story_plan.get("art_style", "retro_pixel")
    style_name = ART_STYLE_NAMES.get(art_style, f"{art_style} art")
    characters = story_plan.get("characters", {})
    ch1_setting = story_plan.get("chapters", [{}])[0].get("setting", "a game world")
    theme = _derive_theme_name(story_plan)

    return f"""\
{style_name} style: clean lines, simple shapes, minimal objects. White background (#FFFFFF) for sprites. Generate at 1024x1024 for sprites.

Generate the following 5 assets in this EXACT order.
Before each image, write the label on its own line: [ASSET: role_name]
After writing each label, generate the image immediately.

1. [ASSET: character]
3D mascot cartoon hero character for 2D platformer, \
{characters.get("hero", "a brave hero character")}, \
{theme} theme, {style_name} style, {SPRITE_CONSTRAINTS}

2. [ASSET: enemy_1]
3D mascot cartoon enemy sprite for 2D platformer, \
{characters.get("enemy_1", "a menacing enemy creature")}, \
{theme} theme, {style_name} style, {SPRITE_CONSTRAINTS}

3. [ASSET: platform]
3D mascot platform tile for 2D platformer, \
{characters.get("platform", "stone platform blocks")}, \
{theme} theme, {style_name} style, {PLATFORM_CONSTRAINTS}

4. [ASSET: npc]
3D mascot cartoon NPC sprite for 2D platformer, \
{characters.get("npc", "a friendly guide character")}, \
{theme} theme, {style_name} style, {SPRITE_CONSTRAINTS}

5. [ASSET: background]
Wide 2D side-scrolling game background, 1920x1080. Minimalist {style_name}, clean lines, simple shapes. \
{ch1_setting}. \
Top 20–30%: decorative elements only (sky, distant shapes, 2–4 simple objects). \
Middle 40–50%: plain, low detail, empty for gameplay. \
Bottom 20–30%: ground shapes only. \
Max 2–4 decorative objects per side. No texture-heavy details in middle lane. \
Sparse, lots of empty space. Seamless horizontal tile for parallax. \
No characters, no UI, no text.
"""


def _parse_response_parts(response) -> dict[str, bytes]:
    """Parse interleaved response parts, matching [ASSET: role] labels to images."""
    assets: dict[str, bytes] = {}
    current_role: str | None = None
    asset_pattern = re.compile(r"\[ASSET:\s*(\w+)\]")
    image_index = 0

    ordered_roles = ["character", "enemy_1", "platform", "npc", "background"]

    for part in response.candidates[0].content.parts:
        if part.text:
            match = asset_pattern.search(part.text)
            if match:
                current_role = match.group(1)
        elif part.inline_data:
            role = current_role or (
                ordered_roles[image_index]
                if image_index < len(ordered_roles)
                else f"unknown_{image_index}"
            )
            assets[role] = part.inline_data.data
            logger.info("Captured image for role: %s (%d bytes)", role, len(part.inline_data.data))
            current_role = None
            image_index += 1

    return assets


async def generate_story_assets(
    story_plan: dict,
    output_dir: str,
) -> dict[str, str]:
    """
    Generate 5 game assets via Gemini interleaved output.

    Returns a dict mapping role -> saved file path.
    Sprites (character, enemy_1, platform, npc) have backgrounds removed.
    Background is saved as-is.
    """
    os.makedirs(output_dir, exist_ok=True)
    client = get_client()
    prompt = _build_asset_prompt(story_plan)

    logger.info("Generating assets with model %s...", IMAGE_MODEL)
    response = await client.aio.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            temperature=1.0,
        ),
    )

    raw_assets = _parse_response_parts(response)

    if not raw_assets:
        raise RuntimeError("Gemini returned no images. Response may have been filtered.")

    saved: dict[str, str] = {}
    for role, image_data in raw_assets.items():
        if role in SPRITE_ROLES:
            cleaned = remove_background(image_data)
        else:
            cleaned = Image.open(io.BytesIO(image_data)).convert("RGB")
            if cleaned.size != BACKGROUND_SIZE:
                cleaned = cleaned.resize(BACKGROUND_SIZE, Image.Resampling.LANCZOS)
                logger.info("Resized background to %s", BACKGROUND_SIZE)

        out_path = os.path.join(output_dir, f"{role}.png")
        cleaned.save(out_path, "PNG")
        saved[role] = out_path
        logger.info("Saved %s -> %s (%dx%d)", role, out_path, cleaned.width, cleaned.height)

    missing = ALL_ROLES - set(saved.keys())
    if missing:
        logger.warning("Missing assets (model may not have generated all 5): %s", missing)

    return saved

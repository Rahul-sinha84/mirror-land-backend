"""
Image generation service using Gemini interleaved output (TEXT + IMAGE).

Generates 5 game assets via 5 parallel Gemini calls (one per asset):
  - character  (hero sprite, white bg, 1024x1024)
  - enemy_1    (enemy sprite, white bg, 1024x1024)
  - platform   (tile sprite, white bg, 1024x1024)
  - npc        (NPC sprite, white bg, 1024x1024)
  - background (full scene, 1920x1080, no cleanup)

Each call uses [ASSET: role_name] in the prompt. Isolated calls avoid first-in-batch compositing.
Sprites use solid white #FFFFFF background for reliable rembg cleanup.
"""

import asyncio
import io
import logging
import os

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
ONLY one single character, no other characters or creatures or objects in the image, \
The character's body/clothing must NOT be white or near-white — use vibrant saturated colors so it contrasts with the white background, \
side profile strictly facing right, full body visible, centered, \
solid opaque body, simple round compact silhouette, minimal detail, \
no thin strands/particles/fog, \
solid flat white #FFFFFF background edge-to-edge, 1024x1024, game sprite."""

PLATFORM_CONSTRAINTS = """\
The platform must NOT be white or near-white — use vibrant saturated colors so it contrasts with the white background, \
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


# Role -> (characters key, intro line, constraints)
_SPRITE_CONFIG = {
    "character": ("hero", "3D mascot cartoon hero sprite for 2D platformer", SPRITE_CONSTRAINTS),
    "enemy_1": ("enemy_1", "3D mascot cartoon enemy sprite for 2D platformer", SPRITE_CONSTRAINTS),
    "npc": ("npc", "3D mascot cartoon NPC sprite for 2D platformer", SPRITE_CONSTRAINTS),
    "platform": ("platform", "3D mascot platform tile for 2D platformer", PLATFORM_CONSTRAINTS),
}

DEFAULT_DESCRIPTIONS = {
    "hero": "a brave hero character",
    "enemy_1": "a menacing enemy creature",
    "npc": "a friendly guide character",
    "platform": "stone platform blocks",
}


def _build_sprite_prompt(story_plan: dict, role: str) -> str:
    """Build a standalone prompt for a single sprite (character, enemy_1, npc, or platform)."""
    if role not in _SPRITE_CONFIG:
        raise ValueError(f"Unknown sprite role: {role}")
    char_key, intro, constraints = _SPRITE_CONFIG[role]
    art_style = story_plan.get("art_style", "retro_pixel")
    style_name = ART_STYLE_NAMES.get(art_style, f"{art_style} art")
    characters = story_plan.get("characters", {})
    theme = _derive_theme_name(story_plan)
    description = characters.get(char_key, DEFAULT_DESCRIPTIONS.get(char_key, ""))
    return f"""\
{style_name} style: clean lines, simple shapes, minimal objects. White background (#FFFFFF) for sprites. Generate at 1024x1024.

Generate exactly one image:

[ASSET: {role}]
{intro}, {description}, {theme} theme, {style_name} style, {constraints}
"""


def _build_background_prompt(story_plan: dict) -> str:
    """Build a standalone prompt for the background image."""
    art_style = story_plan.get("art_style", "retro_pixel")
    style_name = ART_STYLE_NAMES.get(art_style, f"{art_style} art")
    ch1_setting = story_plan.get("chapters", [{}])[0].get("setting", "a game world")
    return f"""\
{style_name} style: clean lines, simple shapes, minimal objects.

Generate exactly one image:

[ASSET: background]
Wide 2D side-scrolling game background, 1920x1080. Minimalist {style_name}, clean lines, simple shapes. \
{ch1_setting}. \
Top 20–30%: decorative elements only (sky, distant shapes, 2–4 simple objects). \
Middle 40–50%: plain, low detail, empty for gameplay. \
Bottom 20–30%: ground shapes only. \
Max 2–4 decorative objects per side. No texture-heavy details in middle lane. \
Sparse, lots of empty space. Seamless horizontal tile for parallax. \
No characters, no UI, no text.
"""


def _extract_single_image(response, role: str) -> bytes | None:
    """Extract the first image from an interleaved response (single-asset call)."""
    if not response.candidates:
        return None
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            return part.inline_data.data
    return None


async def generate_story_assets(
    story_plan: dict,
    output_dir: str,
) -> dict[str, str]:
    """
    Generate 5 game assets via 5 parallel Gemini calls (one per asset).

    Returns a dict mapping role -> saved file path.
    Sprites (character, enemy_1, platform, npc) have backgrounds removed.
    Background is saved as-is.
    """
    os.makedirs(output_dir, exist_ok=True)
    client = get_client()
    gen_config = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        temperature=1.0,
    )

    sprite_roles = ["character", "enemy_1", "platform", "npc"]
    prompts = (
        [_build_sprite_prompt(story_plan, r) for r in sprite_roles]
        + [_build_background_prompt(story_plan)]
    )
    roles = sprite_roles + ["background"]

    logger.info("Generating 5 assets in parallel with model %s...", IMAGE_MODEL)
    responses = await asyncio.gather(
        *[
            client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=prompt,
                config=gen_config,
            )
            for prompt in prompts
        ]
    )

    raw_assets: dict[str, bytes] = {}
    for role, response in zip(roles, responses):
        data = _extract_single_image(response, role)
        if data:
            raw_assets[role] = data
            logger.info("Captured image for role: %s (%d bytes)", role, len(data))
        else:
            logger.warning("No image in response for role: %s", role)

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

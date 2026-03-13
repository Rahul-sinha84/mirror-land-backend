"""
Phase 4 test: Level generation + validation.

Usage:
    python tests/test_level_gen.py                       # generates story plan first
    python tests/test_level_gen.py path/to/plan.json     # uses saved story plan

Generates a level JSON for chapter 1, validates it, generates a chapter background,
and also tests the validator independently with a deliberately broken level.
"""

import asyncio
import json
import os
import sys

from level_validator import validate_and_fix_level
from services.level_gen import generate_chapter_background, generate_level_json
from services.story_planner import generate_story_plan

OUTPUT_DIR = os.path.join("static", "test_assets")

REQUIRED_KEYS = {
    "level_id", "world", "platforms", "pickups", "enemies",
    "exit", "player_spawn", "physics", "mechanics", "mission",
}


def test_validator_with_broken_level():
    """Test the validator independently with a deliberately broken level."""
    print("\n=== Validator Unit Test (broken level) ===")
    broken = {
        "world": {"width": 500, "height": 900},
        "platforms": [],
        "pickups": [],
        "enemies": [
            {"role": "enemy_1", "x": 300, "y": 200, "patrol": [200, 400], "behavior": "patrol"},
        ],
        "blocks": [],
        "hazards": [],
        "bounce_pads": [],
        "teleporters": [],
        "npcs": [],
        "mission": {"type": "find_key_exit", "description": "Find the key", "target_count": 1,
                     "success_text": "Done", "fail_text": "Fail"},
        "mechanics": {"double_jump": False},
        "physics": {"gravity": 2000, "jump_force": -100, "move_speed": 50},
    }

    fixed = validate_and_fix_level(broken)

    errors = []
    grounds = [p for p in fixed["platforms"] if p.get("role") == "ground"]
    if not grounds:
        errors.append("No ground after fix")
    if "player_spawn" not in fixed:
        errors.append("No player_spawn after fix")
    if fixed["world"]["width"] < 2000:
        errors.append(f"World width still too small: {fixed['world']['width']}")
    if fixed["world"]["height"] != 1080:
        errors.append(f"World height not 1080: {fixed['world']['height']}")

    phys = fixed["physics"]
    if not (800 <= phys["gravity"] <= 1600):
        errors.append(f"Gravity out of range: {phys['gravity']}")
    if not (-900 <= phys["jump_force"] <= -400):
        errors.append(f"Jump force out of range: {phys['jump_force']}")
    if not (150 <= phys["move_speed"] <= 500):
        errors.append(f"Move speed out of range: {phys['move_speed']}")

    keys = [p for p in fixed["pickups"] if p.get("role") == "key"]
    if not keys:
        errors.append("No key added for find_key_exit mission")

    if not fixed.get("exit"):
        errors.append("No exit after fix")

    if errors:
        print("VALIDATOR ISSUES:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("VALIDATOR PASSED — all broken fields auto-fixed correctly")

    return len(errors) == 0


async def main():
    plan_path = sys.argv[1] if len(sys.argv) > 1 else None

    saved_plan = os.path.join(OUTPUT_DIR, "story_plan.json")
    if plan_path and os.path.exists(plan_path):
        print(f"Loading story plan from {plan_path}...")
        with open(plan_path) as f:
            story_plan = json.load(f)
    elif os.path.exists(saved_plan):
        print(f"Loading story plan from {saved_plan}...")
        with open(saved_plan) as f:
            story_plan = json.load(f)
    else:
        prompt = "A tiny astronaut exploring candy planets"
        print(f"Generating story plan for: {prompt}")
        story_plan = await generate_story_plan(prompt)

    print(f"Story: {story_plan['title']} (art_style: {story_plan['art_style']})")

    validator_ok = test_validator_with_broken_level()

    chapter = story_plan["chapters"][0]
    story_pack = {}

    print(f"\n=== Level Generation (Chapter 1) ===")
    print(f"Generating level JSON for: {chapter['title']}...")

    level = await generate_level_json(chapter, story_plan, story_pack)

    print(f"\n--- Level JSON Validation ---")
    missing_keys = REQUIRED_KEYS - set(level.keys())
    gen_errors = []
    if missing_keys:
        gen_errors.append(f"Missing required keys: {missing_keys}")

    platforms = level.get("platforms", [])
    grounds = [p for p in platforms if p.get("role") == "ground"]
    if not grounds:
        gen_errors.append("No ground platform")

    spawn = level.get("player_spawn", {})
    spawn_x, spawn_y = spawn.get("x", 0), spawn.get("y", 0)
    on_ground = any(
        g["x"] <= spawn_x <= g["x"] + g.get("w", 192)
        and spawn_y <= g["y"]
        for g in grounds
    )
    if not on_ground and grounds:
        gen_errors.append(f"Player spawn ({spawn_x}, {spawn_y}) not above ground")

    phys = level.get("physics", {})
    if not (800 <= phys.get("gravity", 0) <= 1600):
        gen_errors.append(f"Gravity out of range: {phys.get('gravity')}")
    if not (-900 <= phys.get("jump_force", 0) <= -400):
        gen_errors.append(f"Jump force out of range: {phys.get('jump_force')}")

    print(f"  Platforms: {len(platforms)} ({len(grounds)} ground)")
    print(f"  Enemies: {len(level.get('enemies', []))}")
    print(f"  Pickups: {len(level.get('pickups', []))}")
    print(f"  Hazards: {len(level.get('hazards', []))}")
    print(f"  World: {level.get('world', {}).get('width')}x{level.get('world', {}).get('height')}")
    print(f"  Mission: {level.get('mission', {}).get('type')}")
    print(f"  Spawn: ({spawn_x}, {spawn_y})")

    level_out = os.path.join(OUTPUT_DIR, "level_ch01.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(level_out, "w") as f:
        json.dump(level, f, indent=2)
    print(f"\n  Level JSON saved to {level_out}")

    print(f"\n=== Chapter Background Generation ===")
    bg_path = await generate_chapter_background(
        chapter, story_plan["art_style"], OUTPUT_DIR,
    )
    from PIL import Image
    bg = Image.open(bg_path)
    print(f"  Background: {bg.size[0]}x{bg.size[1]}, path={bg_path}")
    if bg.size[0] < 800 or bg.size[1] < 400:
        gen_errors.append(f"Background too small: {bg.size}")

    print(f"\n--- Final Results ---")
    if gen_errors:
        print(f"ISSUES ({len(gen_errors)}):")
        for e in gen_errors:
            print(f"  - {e}")
    else:
        print("PASSED — level JSON valid, background generated, validator working")

    if not validator_ok:
        print("(Note: validator unit test had issues — see above)")


if __name__ == "__main__":
    asyncio.run(main())

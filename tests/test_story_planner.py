"""
Phase 2 test: StoryPlanner service.

Usage:
    python tests/test_story_planner.py "A tiny pirate searching for cursed treasure"
    python tests/test_story_planner.py  # uses default prompt
"""

import asyncio
import json
import sys

from services.story_planner import generate_story_plan

VALID_ART_STYLES = {
    "retro_pixel", "flat_vector", "neon_cyberpunk",
    "watercolor", "ink_manga", "chalk", "gothic",
}
VALID_MISSION_TYPES = {
    "find_key_exit", "collect_all", "kill_all", "survive", "reach_exit",
}
VALID_PLAYER_ACTIONS = {"none", "laser_shot", "sword_slash"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_WEATHER = {"none", "rain", "snow", "fog", "embers"}
VALID_SOUND_PACKS = {"retro", "sci_fi", "fantasy"}

REQUIRED_CHARACTER_KEYS = {
    "hero", "enemy_1", "enemy_2", "npc", "coin",
    "health", "key", "platform", "breakable", "exit_door",
}


def validate_story_plan(plan: dict) -> list[str]:
    """Return a list of validation errors. Empty list means valid."""
    errors = []

    for field in ("story_id", "title", "premise", "art_style", "mood", "sound_pack"):
        if field not in plan:
            errors.append(f"Missing top-level field: {field}")

    if plan.get("art_style") not in VALID_ART_STYLES:
        errors.append(f"Invalid art_style: {plan.get('art_style')}. Must be one of {VALID_ART_STYLES}")

    if plan.get("sound_pack") not in VALID_SOUND_PACKS:
        errors.append(f"Invalid sound_pack: {plan.get('sound_pack')}. Must be one of {VALID_SOUND_PACKS}")

    chapters = plan.get("chapters", [])
    if len(chapters) != 3:
        errors.append(f"Expected 3 chapters, got {len(chapters)}")
        return errors

    expected_difficulties = ["easy", "medium", "hard"]
    for i, ch in enumerate(chapters):
        prefix = f"Chapter {i+1}"

        if ch.get("chapter_number") != i + 1:
            errors.append(f"{prefix}: chapter_number should be {i+1}, got {ch.get('chapter_number')}")

        for field in ("title", "setting", "narration"):
            if not ch.get(field):
                errors.append(f"{prefix}: missing or empty '{field}'")

        if ch.get("difficulty") != expected_difficulties[i]:
            errors.append(f"{prefix}: difficulty should be '{expected_difficulties[i]}', got '{ch.get('difficulty')}'")

        mission = ch.get("mission", {})
        if mission.get("type") not in VALID_MISSION_TYPES:
            errors.append(f"{prefix}: invalid mission type '{mission.get('type')}'")
        for mf in ("description", "target_count", "success_text", "fail_text"):
            if mf not in mission:
                errors.append(f"{prefix}: mission missing '{mf}'")

        mech = ch.get("mechanics", {})
        if mech.get("player_action") not in VALID_PLAYER_ACTIONS:
            errors.append(f"{prefix}: invalid player_action '{mech.get('player_action')}'")
        weather = mech.get("weather", "none")
        if weather not in VALID_WEATHER:
            errors.append(f"{prefix}: invalid weather '{weather}'")
        for bool_field in ("auto_run", "double_jump", "dark_mode"):
            if bool_field in mech and not isinstance(mech[bool_field], bool):
                errors.append(f"{prefix}: '{bool_field}' should be boolean")
        gs = mech.get("gravity_scale", 1.0)
        if not (0.3 <= gs <= 2.0):
            errors.append(f"{prefix}: gravity_scale {gs} out of range [0.3, 2.0]")

    characters = plan.get("characters", {})
    missing_chars = REQUIRED_CHARACTER_KEYS - set(characters.keys())
    if missing_chars:
        errors.append(f"Characters missing keys: {missing_chars}")
    for key, val in characters.items():
        if not val or not isinstance(val, str) or len(val) < 5:
            errors.append(f"Character '{key}' description too short or empty")

    return errors


async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "A tiny pirate searching for cursed treasure"
    print(f"Prompt: {prompt}")
    print("Generating story plan...\n")

    plan = await generate_story_plan(prompt)

    print(json.dumps(plan, indent=2))
    print("\n--- Validation ---")

    errors = validate_story_plan(plan)
    if errors:
        print(f"FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("PASSED — story plan is valid")
        print(f"  Title: {plan['title']}")
        print(f"  Art style: {plan['art_style']}")
        print(f"  Chapters: {', '.join(ch['title'] for ch in plan['chapters'])}")
        print(f"  Missions: {', '.join(ch['mission']['type'] for ch in plan['chapters'])}")


if __name__ == "__main__":
    asyncio.run(main())

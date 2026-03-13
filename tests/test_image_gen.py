"""
Phase 3 test: Image generation + sprite cleaning.

Usage:
    python tests/test_image_gen.py                     # uses default pirate story plan
    python tests/test_image_gen.py path/to/plan.json   # uses saved story plan

Generates 5 assets, removes sprite backgrounds, saves to static/test_assets/.
"""

import asyncio
import json
import os
import sys

from PIL import Image

from services.story_planner import generate_story_plan
from services.image_gen import generate_story_assets

OUTPUT_DIR = os.path.join("static", "test_assets")
EXPECTED_ROLES = {"character", "enemy_1", "platform", "npc", "background"}
SPRITE_ROLES = {"character", "enemy_1", "platform", "npc"}


async def main():
    plan_path = sys.argv[1] if len(sys.argv) > 1 else None

    if plan_path and os.path.exists(plan_path):
        print(f"Loading story plan from {plan_path}...")
        with open(plan_path) as f:
            story_plan = json.load(f)
    else:
        prompt = "A tiny astronaut exploring candy planets"
        # prompt = "A tiny pirate searching for cursed treasure"
        print(f"Generating story plan for: {prompt}")
        story_plan = await generate_story_plan(prompt)

    print(f"Story: {story_plan['title']} (art_style: {story_plan['art_style']})")
    print(f"\nGenerating 5 assets via Gemini interleaved output...")
    print(f"Output directory: {OUTPUT_DIR}\n")

    saved = await generate_story_assets(story_plan, OUTPUT_DIR)

    print(f"\n--- Results ---")
    print(f"Assets generated: {len(saved)}")

    errors = []
    for role in EXPECTED_ROLES:
        if role not in saved:
            errors.append(f"Missing asset: {role}")
            continue

        path = saved[role]
        if not os.path.exists(path):
            errors.append(f"{role}: file not found at {path}")
            continue

        img = Image.open(path)
        print(f"  {role}: {img.size[0]}x{img.size[1]}, mode={img.mode}, path={path}")

        if role in SPRITE_ROLES:
            if img.mode != "RGBA":
                errors.append(f"{role}: expected RGBA mode, got {img.mode}")
            else:
                import numpy as np
                alpha = np.array(img.split()[3])
                transparent_pct = (alpha < 10).sum() / alpha.size * 100
                opaque_pct = (alpha > 245).sum() / alpha.size * 100
                print(f"           transparent: {transparent_pct:.1f}%, opaque: {opaque_pct:.1f}%")
                if transparent_pct < 5:
                    errors.append(f"{role}: very little transparency ({transparent_pct:.1f}%) — background removal may have failed")
        else:
            min_w, min_h = 800, 400
            if img.size[0] < min_w or img.size[1] < min_h:
                errors.append(f"background: too small ({img.size[0]}x{img.size[1]}), expected at least {min_w}x{min_h}")

    print(f"\n--- Validation ---")
    if errors:
        print(f"ISSUES ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("PASSED — all 5 assets generated and processed correctly")

    plan_out = os.path.join(OUTPUT_DIR, "story_plan.json")
    with open(plan_out, "w") as f:
        json.dump(story_plan, f, indent=2)
    print(f"\nStory plan saved to {plan_out} (reuse with: python tests/test_image_gen.py {plan_out})")


if __name__ == "__main__":
    asyncio.run(main())

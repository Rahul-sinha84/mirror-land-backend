#!/usr/bin/env python3
"""
End-to-end test for the ADK CreativeDirector pipeline.

Usage:
    PYTHONPATH=. python tests/test_adk_pipeline.py "A tiny astronaut exploring candy planets"

Runs the full pipeline: StoryPlanner -> StoryArchitect -> LevelBuilder
and verifies that session state and output files are produced correctly.
"""

import asyncio
import json
import logging
import os
import sys
import uuid

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

APP_NAME = "mirror_land"
USER_ID = "test_user"


async def run_pipeline(prompt: str):
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from agent.agent import creative_director

    session_id = str(uuid.uuid4())[:8]
    logger.info("Session ID: %s", session_id)
    logger.info("Prompt: %s", prompt)

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
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

    print("\n" + "=" * 60)
    print("  ADK Pipeline: CreativeDirector")
    print("=" * 60)

    final_text = None
    event_count = 0

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=content,
    ):
        event_count += 1
        author = getattr(event, "author", "unknown")

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    snippet = part.text[:150].replace("\n", " ")
                    logger.info("[%s] %s...", author, snippet)
                if hasattr(part, "function_call") and part.function_call:
                    logger.info("[%s] -> tool call: %s", author, part.function_call.name)
                if hasattr(part, "function_response") and part.function_response:
                    logger.info("[%s] <- tool response", author)

        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    logger.info("Pipeline complete. Total events: %d", event_count)

    # Retrieve session to inspect final state
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )
    state = session.state

    # --- Verify story_plan ---
    print("\n=== Story Plan ===")
    story_plan_raw = state.get("story_plan")
    if story_plan_raw:
        try:
            sp = json.loads(story_plan_raw)
            print(f"  Title:     {sp.get('title', 'N/A')}")
            print(f"  Art style: {sp.get('art_style', 'N/A')}")
            print(f"  Mood:      {sp.get('mood', 'N/A')}")
            print(f"  Chapters:  {len(sp.get('chapters', []))}")
            chars = sp.get("characters", {})
            print(f"  Characters: {', '.join(chars.keys())}")
            print("  [OK]")
        except json.JSONDecodeError:
            print(f"  [WARN] Not valid JSON: {story_plan_raw[:200]}")
    else:
        print("  [MISSING] story_plan not in state")

    # --- Verify story_pack ---
    print("\n=== Story Pack (Assets) ===")
    story_pack_raw = state.get("story_pack")
    if story_pack_raw:
        try:
            pack = json.loads(story_pack_raw)
            assets = pack.get("assets", {})
            for role, path in assets.items():
                exists = os.path.exists(path) if path else False
                status = "[EXISTS]" if exists else "[MISSING]"
                print(f"  {role}: {path} {status}")
            print("  [OK]")
        except json.JSONDecodeError:
            print(f"  [TEXT] {story_pack_raw[:300]}")
    else:
        print("  [MISSING] story_pack not in state")

    # --- Verify level_data ---
    print("\n=== Level Data ===")
    level_data_raw = state.get("level_data")
    if level_data_raw:
        try:
            ld = json.loads(level_data_raw)
            for ch in ld.get("chapters", []):
                num = ch.get("chapter_number")
                print(f"  Chapter {num}:")
                print(f"    Level:      {ch.get('level_path', 'N/A')}")
                print(f"    Background: {ch.get('background_url', 'N/A')}")
                print(f"    Music:      {ch.get('music_url', 'N/A')}")
            print("  [OK]")
        except json.JSONDecodeError:
            print(f"  [TEXT] {level_data_raw[:300]}")
    else:
        print("  [MISSING] level_data not in state")

    # --- List output directory ---
    output_dir = os.path.join("static/assets", session_id)
    print(f"\n=== Output Directory: {output_dir} ===")
    if os.path.exists(output_dir):
        for f in sorted(os.listdir(output_dir)):
            fpath = os.path.join(output_dir, f)
            size = os.path.getsize(fpath)
            print(f"  {f} ({size:,} bytes)")
    else:
        print("  Directory does not exist")

    # --- Final response ---
    if final_text:
        print(f"\n=== Final Agent Response (truncated) ===\n{final_text[:500]}")

    print("\n" + "=" * 60)
    print("  Pipeline finished.")
    print("=" * 60)


if __name__ == "__main__":
    prompt = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "A tiny astronaut exploring candy planets"
    )
    asyncio.run(run_pipeline(prompt))

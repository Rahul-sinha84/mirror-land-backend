import json
from google.genai import types

from services.gemini_client import get_client
from agent.prompts import STORY_PLANNER_INSTRUCTION

STORY_PLANNER_MODEL = "gemini-2.5-flash"


async def generate_story_plan(prompt: str) -> dict:
    """Generate a complete story plan JSON from a user's story prompt."""
    client = get_client()

    response = await client.aio.models.generate_content(
        model=STORY_PLANNER_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=STORY_PLANNER_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )

    story_plan = json.loads(response.text)
    return story_plan

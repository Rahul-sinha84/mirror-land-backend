"""
ADK agent definitions for the CreativeDirector pipeline.

Pipeline: StoryPlanner -> StoryArchitect -> LevelBuilder
Orchestrated by a SequentialAgent (CreativeDirector).
"""

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.genai import types

from agent.prompts import (
    LEVEL_BUILDER_AGENT_INSTRUCTION,
    STORY_ARCHITECT_INSTRUCTION,
    STORY_PLANNER_INSTRUCTION,
)
from agent.tools import generate_assets, generate_chapter_level

GEMINI_MODEL = "gemini-2.5-flash"

story_planner = LlmAgent(
    name="StoryPlanner",
    model=GEMINI_MODEL,
    description="Generates a complete 3-chapter story plan with characters, art style, and mechanics.",
    instruction=STORY_PLANNER_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.8,
    ),
    output_key="story_plan",
)

story_architect = LlmAgent(
    name="StoryArchitect",
    model=GEMINI_MODEL,
    description="Generates game art assets (sprites and backgrounds) based on the story plan.",
    instruction=STORY_ARCHITECT_INSTRUCTION,
    tools=[generate_assets],
    output_key="story_pack",
)

level_builder = LlmAgent(
    name="LevelBuilder",
    model=GEMINI_MODEL,
    description="Generates playable level layouts, chapter backgrounds, and music for each chapter.",
    instruction=LEVEL_BUILDER_AGENT_INSTRUCTION,
    tools=[generate_chapter_level],
    output_key="level_data",
)

creative_director = SequentialAgent(
    name="CreativeDirector",
    description="Orchestrates the full story-to-game pipeline: plan -> assets -> levels.",
    sub_agents=[story_planner, story_architect, level_builder],
)

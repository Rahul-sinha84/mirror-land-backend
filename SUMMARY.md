# Playable Storybook — Summary

## What Is It?

A platform where you type one sentence and an AI creates a complete, playable 2D platformer game from it. Different prompts produce completely different games — different art, enemies, mechanics, music, and missions.

**Example:** "A tiny pirate searching for cursed treasure" → retro pixel art, sword combat, fog weather, find-the-key missions across 3 chapters.

**Example:** "A wanderer fleeing moonlit shadows" → flat vector art, auto-runner with laser, snow weather, survive-the-assault gameplay.

Same engine. Completely different games. The AI is a creative director, not just an image generator.

## How It Works

```
User types prompt → AI generates story + art + levels → Player plays the game
```

1. **User types a story prompt** on the landing screen and clicks GO.
2. **AI generates everything** — story plan, character sprites, enemies, coins, backgrounds, ambient music, level layouts, and game mechanics. The user watches this happen live on a storyboard.
3. **Game launches** — a fully playable platformer with 3 chapters, each with unique missions, enemies, and atmosphere.
4. **Next chapters pre-load** in the background while the player is still playing, so transitions are instant.

## What Makes It Special?

- **Every game is unique** — art style, mechanics, mission type, weather, and difficulty are all AI-selected per story
- **The loading screen IS the experience** — users watch their world being created in real-time (text + images appearing together)
- **Not just Mario with AI images** — the AI picks from ~15 game mechanics (laser/sword, auto-run, dark spotlight, low gravity, teleporters, bounce pads, etc.) creating infinite combinations
- **Interleaved Gemini output** — one API call returns narration + sprites + audio together, showcasing Gemini's multimodal capabilities

## Tech Stack

| What | Technology |
|------|-----------|
| Game engine | Vanilla JS + HTML5 Canvas |
| Backend | Python + FastAPI |
| AI agents | Google ADK (3 agents: StoryPlanner, StoryArchitect, LevelBuilder) |
| Image generation | Gemini 2.5 Flash Image (interleaved text + image) |
| Music generation | Lyria (lyria-002) on Vertex AI (ambient loops per chapter) |
| NPC voice | Gemini TTS (gemini-2.5-flash-preview-tts) |
| Game SFX | Procedural Web Audio (zero latency, no AI needed) |
| Streaming | Server-Sent Events (SSE) |
| Deploy | Google Cloud Run + Cloud Build CI/CD |

## AI Architecture (Simple)

**Agent 1: StoryPlanner** — Fast text-only (~2-3s). Generates story plan JSON (title, chapters, mechanics, character descriptions).

**Agent 2: StoryArchitect** — Generates 5 assets in parallel: character, enemy_1, platform, npc, background. Uses white #FFFFFF background + rembg for reliable sprite extraction.

**Agent 3: LevelBuilder** — For each chapter, generates level layout JSON, chapter background image, ambient music (Lyria), and NPC dialogue audio (Gemini TTS) in parallel.

**Safety nets:**
- 9-rule Level Validator auto-fixes unplayable layouts (gaps too wide, enemies floating, missing items)
- rembg + alpha-threshold crop for sprite background removal
- Graceful fallbacks if generation fails

## Game Features Built

**Entities:** Player, platforms (static/moving), enemies (patrol/chase/shoot), pickups (coin/key/health), breakable blocks, hazards (spikes/lava/acid), bounce pads, teleporters, NPCs with dialogue, exit doors.

**Mechanics (AI picks per chapter):** Auto-run mode, laser shot, sword slash, double jump, dark mode spotlight, gravity scaling, weather (rain/snow/fog/embers).

**Missions (AI picks per chapter):** Find key + exit, collect all items, kill all enemies, survive timer, reach exit.

**Art styles (AI picks per story):** Retro pixel, flat vector, neon cyberpunk, watercolor, ink manga, chalk, gothic.

**Effects:** Particles, ambient motes, flying creatures, screen shake, fade transitions, toast notifications, contact shadows, invincibility flicker.

**Audio:** 13 procedural sound effects (jump, coin, stomp, laser, etc.) + AI-generated ambient music per level.

## Project Status

- Frontend game engine: **DONE**
- Backend (ADK pipeline): **DONE**
- Deployment (Cloud Run + Cloud Build): **DONE**
- NPC voice (Gemini TTS): **DONE**
- Ambient music (Lyria): **DONE**

## File Guide

| File | What's in it |
|------|-------------|
| `README.md` | Full project documentation with architecture, API, and deployment |
| `AI.md` | AI-only reference (agent flow, prompts, constraints, validation) |
| `SUMMARY.md` | This file — human-readable overview |
| `cloudbuild.yaml` | Cloud Build CI/CD config |
| `deploy.sh` | Manual Cloud Run deployment script |
| `Dockerfile` | Container setup (Python 3.12-slim + rembg) |

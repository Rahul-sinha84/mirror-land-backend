# Playable Storybook — AI-Generated Interactive Storybook Platform

A multimodal interactive storybook where a **Creative Director Agent** powered by Gemini transforms a single user prompt into a complete, playable platformer. The agent uses **Gemini's native interleaved output** to generate narration, illustrations, ambient music, and level design — all woven together in a single cohesive creative flow — then assembles them into a playable game world.

---

## Problem Statement Alignment

> **Creative Storyteller**: Build an agent that thinks and creates like a creative director, seamlessly weaving together text, images, audio, and video in a single, fluid output stream. Leverage Gemini's native interleaved output.

| Requirement | How We Deliver |
|-------------|---------------|
| Agent that thinks like a creative director | Creative Director Agent plans story arc, selects art style, chooses game mechanics, designs levels — all creative decisions |
| Interleaved output (text + image + audio) | Single Gemini call returns narration text interleaved with inline generated scene illustrations, character sprites, and ambient music |
| Interactive storybook | Playable platformer — the most interactive storybook possible |
| Every story is unique | AI selects art style, mechanics, mission types, weather, enemies, and physics per story — infinite combinations from a finite engine |
| Hosted on Google Cloud | Cloud Run + Gemini API |

---

## Product Vision

> User types one sentence. A Creative Director Agent generates a complete, playable storybook — narration, illustrations, sprites, ambient music, and themed game mechanics — all from interleaved Gemini output. Every story looks, sounds, and plays differently.

### Player Experience

```
1. User types: "A tiny astronaut exploring candy planets"

2. CREATION PHASE — visible to user as a live storyboard stream:
   Agent streams interleaved output:
     "Title: Sugar Galaxy Adventures"
     [generated character illustration — small astronaut in candy suit]
     "Chapter 1: The Gumdrop Crater"
     [generated scene — colorful candy landscape with lollipop trees]
     "Your enemies: the Sour Patrol — angry gumdrops that..."
     [generated enemy sprite — angry gumdrop with legs]
     [generated ambient music — bubbly electronic loop]

   User watches their world being created in real-time (~30 sec)

3. Game launches:
   - Background: candy landscape (from interleaved image)
   - Player: candy astronaut (from interleaved image)
   - Enemies: angry gumdrops (from interleaved image)
   - Music: bubbly ambient loop (from interleaved audio)
   - Mechanics: laser_shot + low gravity + double_jump (AI-selected)
   - Mission: "Collect all 5 sugar crystals" (AI-designed)
   - Weather: embers (rising candy sparkles)

4. Player runs, jumps, shoots, collects — mechanics adapt to the story
5. Exit triggers next chapter — agent generates next scene
6. Story unfolds across 3 chapters, each a unique level
```

---

## What Makes This NOT "Just Mario"

The engine has a finite set of mechanics (~15), but the combinations the AI creates are practically infinite:

| Story Prompt | Art Style | Mechanics | Mission | Weather |
|-------------|-----------|-----------|---------|---------|
| "A pirate searching for cursed treasure" | Retro pixel | sword_slash, patrol enemies, find_key_exit | Find the Skull Key | fog |
| "A wanderer fleeing moonlit shadows" | Flat vector | auto_run, laser_shot, double_jump | Survive 90 seconds | snow |
| "A hacker escaping a digital maze" | Neon/cyberpunk | laser_shot, dark_mode, chase enemies | Kill all sentinels | embers |
| "A fairy exploring an enchanted garden" | Watercolor | no weapon, bounce pads, teleporters | Collect all petals | rain |
| "A ninja infiltrating a forbidden temple" | Ink/manga | sword_slash, shooting turrets, hazards | Reach the exit | none |

Same engine. Completely different games. The AI is a creative director, not just an asset generator.

---

## Architecture Overview

```
+------------------------------------------------------+
|                     FRONTEND                          |
|                                                       |
|  Landing -> Prompt -> Live Storyboard -> Game Canvas  |
|                                                       |
|  Game Engine:                                         |
|  +-- GameLoop, Input, Camera, Physics                 |
|  +-- Player (movement, jump, attack, auto_run)        |
|  +-- Platform (static, moving, colored)               |
|  +-- Enemy (patrol, chase, shoot)                     |
|  +-- Pickup (coin, key, health)                       |
|  +-- Block (breakable, item spawn)                    |
|  +-- Projectile (laser, sword, enemy_shot)            |
|  +-- Hazard (spikes, lava, acid)                      |
|  +-- BouncePad, Teleporter                            |
|  +-- ParticleSystem, AmbientParticles, FlyingCreatures|
|  +-- Weather (rain, snow, fog, embers)                |
|  +-- SoundManager (procedural Web Audio SFX)          |
|  +-- MusicPlayer (ambient loops per level)            |
|                                                       |
|  UI:                                                  |
|  +-- MenuScreen (title + prompt input)                |
|  +-- Storyboard (renders SSE stream live)             |
|  +-- Dialogue (NPC text bubble on proximity)          |
|  +-- HUD (health, coins, mission tracker)             |
|                                                       |
+-------------------------+----------------------------+
                          | SSE (Server-Sent Events)
                          | + REST API
+-------------------------v----------------------------+
|               BACKEND (Python + FastAPI + ADK)        |
|                                                       |
|  POST /api/create-story  -> starts agent, returns SSE |
|  POST /api/next-chapter  -> agent generates next level|
|  GET  /api/session/:id   -> session state             |
|                                                       |
|  ADK Agents (SequentialAgent):                        |
|  +-- CreativeDirector (root)                          |
|      +-- StoryPlanner   (text-only: story plan JSON)  |
|      +-- StoryArchitect (interleaved: 4 sprites)     |
|      +-- LevelBuilder   (interleaved: bg + level JSON)|
|                                                       |
|  ADK Tools:                                           |
|  +-- generate_interleaved_assets (sprites + music)    |
|  +-- generate_chapter_level      (bg + layout JSON)   |
|                                                       |
+-------------------------+----------------------------+
                          |
+-------------------------v----------------------------+
|               GEMINI AI + ADK ORCHESTRATION           |
|                                                       |
|  Interleaved output (via ADK tool calls):             |
|    model: gemini-2.5-flash-preview-image-generation   |
|    response_modalities: ["TEXT", "IMAGE"]              |
|    - Narration text + inline scene illustrations      |
|    - Character art + enemy sprites + item icons       |
|    - Multi-turn chat for visual consistency            |
|                                                       |
|  Audio generation:                                    |
|    model: gemini-2.5-flash-preview-native-audio       |
|    response_modalities: ["AUDIO"]                     |
|    - Ambient music loop per chapter                   |
|    - Game SFX: procedural (Web Audio, no AI needed)   |
|                                                       |
|  ADK features used:                                   |
|    - SequentialAgent (pipeline orchestration)          |
|    - LlmAgent (per-step reasoning)                    |
|    - output_key (state passing between agents)        |
|    - InMemorySessionService (sessions)                |
|                                                       |
+------------------------------------------------------+
```

---

## The Creative Director Agent (ADK)

A **3-agent pipeline** built with Google's Agent Development Kit (ADK). A `SequentialAgent` chains three specialized agents: StoryPlanner (fast text-only), StoryArchitect (4 sprites), LevelBuilder (per-chapter). Each agent's output flows into the next via `output_key`.

### ADK Agent Definitions

```python
from google.adk.agents import LlmAgent, SequentialAgent

# -- Sub-Agent 1: Story Planner --
# Fast text-only: story plan JSON. Decouples planning from image generation.
story_planner = LlmAgent(
    name="StoryPlanner",
    model="gemini-2.5-flash",
    instruction="""Given the user's prompt, create a story plan as JSON:
    title, premise, art_style, mood, sound_pack, 3 chapters with
    setting, narration, mission, mechanics, difficulty.
    Include characters object: hero, enemy_1, platform descriptions.""",
    output_key="story_plan"
)

# -- Sub-Agent 2: Story Architect --
# Generates 4 assets: character, enemy_1, platform, background.
story_architect = LlmAgent(
    name="StoryArchitect",
    model="gemini-2.5-flash-preview-image-generation",
    instruction="""Using the story_plan, generate 4 game assets via interleaved output:
    character, enemy_1, platform, background.
    All sprites: 3D mascot style, solid opaque body, simple silhouette,
    magenta #ff00ff background edge-to-edge, 1024x1024.
    Pickups (coin, health, key) and NPC/exit/breakable use procedural/dummy assets.""",
    tools=[generate_interleaved_assets],
    output_key="story_pack"
)

# -- Sub-Agent 3: Level Builder --
# Generates per-chapter background + level layout JSON.
level_builder = LlmAgent(
    name="LevelBuilder",
    model="gemini-2.5-flash",
    instruction="""You are a Level Designer. Using story_plan and story_pack:

    For the current chapter, generate:
    1. Background scene (interleaved image, wide landscape)
    2. Ambient music loop (interleaved audio, 15-30 seconds, matching mood)
    3. A complete level layout JSON with:
       - platforms (ground + floating, optional moving)
       - pickups (coins, key, health) placed along the path
       - enemies with behaviors (patrol, chase, shoot)
       - blocks (breakable, with items)
       - hazards (spikes, lava, acid) where appropriate
       - bounce_pads and teleporters if the story calls for it
       - NPCs with story-relevant dialogue
       - exit with unlock condition matching the mission
       - player_spawn position
       - physics config (gravity, jump_force, move_speed, friction)
       - mechanics config (from story_pack chapter plan)
       - mission config (type, description, target_count, success_text)
       - ground_color matching the art style

    Design levels that teach mechanics progressively:
    Ch1 = movement + story setup
    Ch2 = combat + rising tension
    Ch3 = challenge + climax""",
    tools=[generate_chapter_level],
    output_key="level_data"
)

# -- Root Agent: Creative Director --
creative_director = SequentialAgent(
    name="CreativeDirector",
    sub_agents=[story_planner, story_architect, level_builder]
)
```

### Agent Pipeline Flow

```
User Prompt: "A tiny pirate searching for cursed treasure"
    |
    v
+--------------------------------------------------+
|  StoryPlanner (LlmAgent, text-only)                |
|  ~2-3s: story plan JSON                            |
|  output_key: story_plan                            |
+-------------------+------------------------------+
                    |
                    v
+--------------------------------------------------+
|  StoryArchitect (LlmAgent, interleaved)            |
|  4 assets: character, enemy_1, platform, background|
|  ~15-25s (parallel or 2 batches)                   |
|  Each sprite: Gemini -> rembg -> crop -> save -> SSE|
|  output_key: story_pack                            |
+-------------------+------------------------------+
                    |
                    v
+--------------------------------------------------+
|  LevelBuilder (per chapter, pre-fetched)           |
|                                                    |
|  3 parallel calls:                                |
|  - Background image (interleaved, ~5-7s)           |
|  - Ambient music loop (audio model, ~5-10s)        |
|  - Level layout JSON (JSON mode, ~2-3s)            |
|                                                    |
|  Level JSON -> validator + fixer -> level_ready    |
|                                                    |
|  output_key: level_data                            |
+-------------------+------------------------------+
                    |
                    v
        SSE stream to Frontend
        (live storyboard -> play)

  Pre-fetching:
  Ch1 sent to player -> Ch2 generates in background
  Ch2 sent to player -> Ch3 generates in background
  Result: zero wait between chapters
```

### ADK Tool: generate_interleaved_assets

Generates 4 assets (character, enemy_1, platform, background). Uses magenta background + rembg for reliable extraction.

```python
async def generate_interleaved_assets(story_plan: dict) -> dict:
    """Generate 4 theme sprites. Story plan provides art_style and character descriptions."""

    art_style = story_plan["art_style"]
    chars = story_plan.get("characters", {})

    # 4 parallel calls or 2 batches of 2
    prompts = [
        (f"[ASSET: character] 3D mascot {chars.get('hero','hero')}, magenta bg, 1024x1024", "character"),
        (f"[ASSET: enemy_1] 3D mascot enemy {chars.get('enemy_1','enemy')}, magenta bg, 1024x1024", "enemy_1"),
        (f"[ASSET: platform] 3D mascot platform tile, magenta bg, 1024x1024", "platform"),
        (f"[ASSET: background] Wide landscape {story_plan['chapters'][0]['setting']}, 1920x1080", "background"),
    ]

    assets = {}
    for prompt, role in prompts:
        img_data = await generate_image(prompt, art_style)
        if role != "background":
            img_data = rembg_remove(img_data)  # rembg
            img_data = crop_transparent_padding(img_data)  # alpha threshold crop
        url = save_asset(img_data, role)
        assets[role] = url
        stream_to_client(session_id, {"type": "image", "role": role, "url": url})

    return {"status": "success", "assets": assets}
```

### ADK Tool: generate_chapter_level

Runs 3 calls in parallel per chapter, then validates the level:

```python
async def generate_chapter_level(chapter: dict, art_style: str, story_pack: dict) -> dict:
    """Generate background + music + level JSON in parallel, then validate."""

    # All 3 run concurrently
    bg_task = asyncio.create_task(generate_background(chapter, art_style))
    music_task = asyncio.create_task(generate_ambient_music(chapter))
    layout_task = asyncio.create_task(generate_level_json(chapter, story_pack))

    bg_url, music_url, level_json = await asyncio.gather(bg_task, music_task, layout_task)

    # Validate and auto-fix the level layout
    level_json = validate_and_fix_level(level_json)

    return {"background_url": bg_url, "music_url": music_url, "level_json": level_json}
```

### Content Safety Fallback

If Gemini refuses to generate due to content filters:

```python
try:
    response = chat.send_message(prompt)
except Exception:
    softened = soften_prompt(prompt)  # strip violent/mature keywords
    try:
        response = chat.send_message(softened)
    except Exception:
        return load_fallback_theme()  # use mock pirate theme as safe default
```

---

## Game Engine — Features Built

### Core Systems

| System | File | Description |
|--------|------|-------------|
| Game Loop | `GameLoop.js` | `requestAnimationFrame`, dt capping, FPS tracking |
| Input | `Input.js` | WASD/Arrows + Space/X/Z/C, ignores input during text entry |
| Physics | `Physics.js` | Gravity, friction, jump force, coyote time, jump buffer, gravity_scale |
| Camera | `Camera.js` | Horizontal follow with easing, clamped to world bounds |
| Scene Loader | `SceneLoader.js` | Loads theme + level JSON, per-level asset overrides, graceful fallbacks |
| Renderer | `Renderer.js` | Background (parallax), HUD (hearts, coins, mission) |

### Game Entities

| Entity | File | Features |
|--------|------|----------|
| Player | `Player.js` | Movement, jump, double jump, auto_run mode, attack cooldown, invincibility, respawn |
| Platform | `Platform.js` | Static, moving (x/y axis), ground with custom colors, tile repeat |
| Enemy | `Enemy.js` | Patrol, chase (detect range), shoot (projectiles at player), stomp kill, death animation |
| Pickup | `Pickup.js` | Coin, key, health; bob animation, glow, collect |
| Block | `Block.js` | Hit from below or shoot, bounce animation, spawn item, gold glow for item blocks |
| Projectile | `Projectile.js` | Laser shot, sword slash, enemy shot; trails, hit detection |
| Hazard | `Hazard.js` | Spikes (metallic, danger stripes), lava (bubbles, glow), acid (bubbles, glow) |
| Bounce Pad | `BouncePad.js` | High bounce, compress animation, resets double jump, animated arrows |
| Teleporter | `Teleporter.js` | Linked pairs by link_id, swirl animation, pulsing glow, cooldown |
| NPC | `Dialogue.js` | Proximity trigger, typewriter text, speaker labels, system messages |

### Visual Effects

| Effect | Description |
|--------|-------------|
| Particles | Dust (landing), sparkle (pickup/double jump), hit (damage), enemy_dust (turn) |
| Ambient Particles | 30 floating motes (firefly/dust), wobble, pulse |
| Flying Creatures | Background birds/bats with wing animation |
| Weather | Rain (streaks), snow (drifting), fog (clouds), embers (rising) |
| Dark Mode Spotlight | Radial gradient around player, offscreen canvas compositing |
| Screen Shake | On damage and hazard contact |
| Contact Shadow | Ellipse under player and enemies |
| Fade Transitions | Between all game states |
| Toast Notifications | "Gold Doubloon +1", "Skull Key acquired!" |
| Invincibility Flicker | Player alpha flash when damaged |

### Audio System

| Layer | Implementation |
|-------|---------------|
| Game SFX | `SoundManager.js` — 13 procedural Web Audio synthesized sounds (jump, land, coin, key, health, stomp, damage, laser, sword, bounce, enemy_shot, level_complete, teleport) |
| Background Music | `MusicPlayer` — ambient loop per level, crossfade between levels, Gemini-generated per chapter |
| Sound Packs | Theme-selectable: retro, sci_fi, fantasy (affects SFX tone) |

### Theme-Adaptive Mechanics

The AI selects mechanics per chapter. The engine supports all combinations:

| Mechanic | JSON Config | Effect |
|----------|------------|--------|
| Auto-run | `auto_run: true` | Player runs right automatically (endless runner style) |
| Player action | `player_action: "laser_shot"` | Laser, sword, or none |
| Double jump | `double_jump: true` | Mid-air second jump |
| Dark mode | `dark_mode: true, spotlight_radius: 140` | Spotlight around player, rest is dark |
| Gravity scale | `gravity_scale: 0.6` | Low gravity (space), high gravity (underground) |
| Weather | `weather: "snow", weather_intensity: 0.5` | Atmospheric particles |
| Ground color | Platform `color: "#0f0f2e"` | Matches level art style |

### Per-Level Asset Overrides

Each level can override theme sprites — enabling different art styles per chapter:

```json
{
  "level_id": "level_000",
  "assets": {
    "character": "backgrounds/character01.png",
    "enemy_1": "backgrounds/enemy_1.png",
    "enemy_2": "backgrounds/enemy_2.png",
    "health": "backgrounds/health.png"
  }
}
```

The `SceneLoader` merges `level.assets` over `theme.assets`. Missing images fall back gracefully to programmatic shapes.

### Art Styles

The AI selects an art style per story. The engine renders whatever PNGs it receives:

| Style | Description | Story Examples |
|-------|-------------|----------------|
| Retro pixel | 8-bit pixel art, bold colors | Pirate, dungeon, classic adventure |
| Flat vector | Clean shapes, atmospheric gradients | Nature, journey, night scenes |
| Neon/cyberpunk | Dark backgrounds, glowing neon outlines | Sci-fi, hacker, space |
| Watercolor | Soft edges, pastel washes | Fairy tale, garden, dream |
| Ink/manga | Bold black strokes, halftone shading | Ninja, samurai, action |
| Chalk | Colorful chalk on dark background | School, childhood, whimsical |
| Gothic | Dark, moody, deep reds and blacks | Horror, vampire, dungeon |

---

## Mission System

Each level has a mission type that the AI selects based on the story:

| Mission Type | How It Works | Example |
|-------------|-------------|---------|
| `find_key_exit` | Find the key, then reach the exit door | "Find the Skull Key and escape the ruins" |
| `collect_all` | Collect N specific items to complete | "Gather all 5 moonstone fragments" |
| `kill_all` | Defeat all enemies in the level | "Clear the cave of shadow creatures" |
| `survive` | Stay alive for N seconds (great for auto_run) | "Survive the shadow assault for 90 seconds" |
| `reach_exit` | Just reach the exit, no key needed | "Escape the collapsing temple" |

### Level JSON Mission Config

```json
{
  "mission": {
    "type": "kill_all",
    "description": "Defeat all 8 shadow creatures",
    "target_count": 8,
    "success_text": "The shadows retreat. The path is clear.",
    "fail_text": "The darkness overwhelms you..."
  }
}
```

### Mission HUD (during gameplay)

- `kill_all`: "Shadows: 3/8"
- `collect_all`: "Crystals: 2/5"
- `survive`: "Survive: 0:45"
- `find_key_exit`: "Find the key" / "Reach the exit"

---

## Game States and Flow

```
menu
  -> (submit prompt or SPACE) -> storyboard
  -> (SPACE/X when ready) -> chapter_intro
  -> (SPACE/X) -> playing
  -> (mission complete) -> level_complete
  -> (SPACE/X) -> next chapter_intro OR story_complete
  -> (SPACE/X) -> menu
```

| State | What Happens |
|-------|-------------|
| `menu` | Title screen, starfield, prompt input (HTML overlay), GO button |
| `storyboard` | Live SSE stream: narration, sprites, music appear in real-time |
| `chapter_intro` | Chapter title, narration, mission briefing, background preview |
| `playing` | Full gameplay with mission tracking |
| `level_complete` | Success text, coin count, next chapter button |
| `story_complete` | Final screen, total coins, play again |

---

## Level JSON Schema

Complete schema that the AI generates per chapter:

```json
{
  "level_id": "level_001",
  "chapter": "The Cursed Shore",
  "chapter_number": 1,
  "narration": "You arrive at the cursed island as the fog thickens...",
  "background": "backgrounds/ch01_bg.png",
  "bg_music": "audio/ch01_ambient.mp3",
  "world": { "width": 3840, "height": 1080 },

  "assets": {
    "character": "sprites/character.png",
    "enemy_1": "sprites/enemy_1.png"
  },

  "mission": {
    "type": "find_key_exit",
    "description": "Find the Skull Key and escape through the ancient gate",
    "target_count": 1,
    "success_text": "The gate creaks open. Beyond lies the sunken caves...",
    "fail_text": "The curse tightens its grip..."
  },

  "platforms": [
    { "x": 0, "y": 850, "w": 900, "h": 230, "role": "ground", "color": "#3d2b1f" },
    { "x": 400, "y": 720, "w": 192, "h": 48, "role": "platform", "repeat": 1 },
    { "x": 1200, "y": 700, "w": 192, "h": 48, "role": "platform",
      "moving": true, "move_axis": "y", "move_range": 80, "move_speed": 60 }
  ],

  "pickups": [
    { "role": "coin", "x": 250, "y": 820 },
    { "role": "key", "x": 3180, "y": 535 },
    { "role": "health", "x": 1500, "y": 670 }
  ],

  "enemies": [
    { "role": "enemy_1", "x": 1200, "y": 806, "patrol": [1100, 1400], "behavior": "patrol" },
    { "role": "enemy_2", "x": 2500, "y": 806, "patrol": [2400, 2700],
      "behavior": "chase", "detect_range": 300, "chase_speed": 200 },
    { "role": "enemy_1", "x": 3000, "y": 750, "patrol": [2900, 3200],
      "behavior": "shoot", "shoot_interval": 2, "shoot_range": 400 }
  ],

  "blocks": [
    { "x": 450, "y": 620, "w": 48, "h": 48, "role": "breakable",
      "has_item": true, "item": "coin" }
  ],

  "hazards": [
    { "x": 920, "y": 840, "w": 140, "h": 12, "type": "spikes" },
    { "x": 1800, "y": 830, "w": 200, "h": 20, "type": "lava" }
  ],

  "bounce_pads": [
    { "x": 1350, "y": 836, "w": 64, "h": 16, "bounce_force": -900 }
  ],

  "teleporters": [
    { "x": 600, "y": 780, "w": 48, "h": 70, "link_id": "warp_a", "color": "#3498db" },
    { "x": 2800, "y": 780, "w": 48, "h": 70, "link_id": "warp_a", "color": "#3498db" }
  ],

  "npcs": [
    {
      "role": "npc", "x": 100, "y": 790, "name": "Old Parrot",
      "dialogue": [
        { "speaker": "Old Parrot", "text": "The key is hidden high up, landlubber!" },
        { "speaker": "system", "text": "Quest: Find the Skull Key" }
      ]
    }
  ],

  "exit": {
    "role": "exit_door", "x": 3700, "y": 658, "w": 128, "h": 192,
    "unlock_condition": "has_key",
    "locked_dialogue": "The gate is sealed. You need a key.",
    "target_level": "level_002"
  },

  "player_spawn": { "x": 60, "y": 780 },

  "physics": {
    "gravity": 1200,
    "jump_force": -700,
    "move_speed": 300,
    "max_fall_speed": 600,
    "friction": 800,
    "coyote_time_ms": 80,
    "jump_buffer_ms": 100
  },

  "mechanics": {
    "auto_run": false,
    "player_action": "laser_shot",
    "gravity_scale": 1.0,
    "double_jump": false,
    "dark_mode": false,
    "spotlight_radius": 140,
    "weather": "fog",
    "weather_intensity": 0.6
  }
}
```

---

## Gemini Interleaved Output — How It Works

### Story Plan First, Then 4 Assets

StoryPlanner produces the story plan (text-only, JSON mode). StoryArchitect then generates **4 assets** in parallel or 2 batches: character, enemy_1, platform, background. All use magenta #ff00ff background for reliable rembg extraction.

```
StoryPlanner: gemini-2.5-flash (JSON mode)
  -> story_plan JSON

StoryArchitect: gemini-2.5-flash-preview-image-generation
  responseModalities: ["TEXT", "IMAGE"]

  [ASSET: character] — 3D mascot hero, magenta bg, 1024x1024
  [ASSET: enemy_1] — 3D mascot enemy, magenta bg, 1024x1024
  [ASSET: platform] — platform tile, magenta bg, 1024x1024
  [ASSET: background] — wide landscape, 1920x1080 (no magenta)
```

### Why 4 Assets Instead of 10?

| Previous (10 assets) | Current (4 assets) |
|---------------------|---------------------|
| Longer generation time | ~15-25s total |
| More rembg failures (watercolor, soft edges) | 3D mascot style = reliable rembg |
| Coin/health/key as images | Procedural per-theme drawing |
| NPC, exit, breakable as images | Dummy/placeholder assets |

### Interleaved Output Calls Summary

**StoryPlanner (~2-3s):** Story plan JSON (title, chapters, mechanics, character descriptions)

**StoryArchitect (~15-25s):** 4 assets — character, enemy_1, platform, background. Each sprite: rembg + crop. Pickups (coin, health, key) and NPC/exit/breakable use procedural/dummy assets.

**LevelBuilder (per chapter, ~8-10s):** Produces 3 things per chapter (run in parallel):
- Background scene (interleaved image, 1920×540)
- Ambient music loop (audio model, 15-30s loop)
- Level layout JSON (JSON mode, validated + auto-fixed)

---

## Audio Architecture

### Two-Layer System

```
+-- Background Music (MusicPlayer) --------+
|  Source: Gemini-generated ambient loop    |
|  One track per level                      |
|  Plays on loop at ~30% volume            |
|  Crossfades between levels               |
|  Mood matches the story theme            |
+------------------------------------------+

+-- Game SFX (SoundManager) ----------------+
|  Source: Procedural Web Audio synthesis    |
|  13 sounds: jump, land, coin, key,        |
|    health, stomp, damage, laser, sword,   |
|    bounce, enemy_shot, level_complete,     |
|    teleport                               |
|  Zero latency, works offline              |
|  Theme-selectable: retro, sci_fi, fantasy |
+------------------------------------------+
```

### Why This Split?

- **Background music** benefits from AI generation — each story gets a unique soundtrack
- **Game SFX** need zero latency — procedural synthesis is instant, no loading
- Background music is non-critical — if generation takes a few seconds, it plays after the storyboard phase
- SFX must be theme-consistent but not unique per story — a "coin collect" sound is always satisfying regardless of theme

---

## Stream Processing — Backend (FastAPI + ADK)

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import json, asyncio

app = FastAPI()
session_service = InMemorySessionService()
runner = Runner(
    agent=creative_director,
    session_service=session_service,
    app_name="playable-storybook"
)

sse_queues: dict[str, asyncio.Queue] = {}

def stream_to_client(session_id: str, event: dict):
    if session_id in sse_queues:
        sse_queues[session_id].put_nowait(event)

@app.post("/api/create-story")
async def create_story(request: Request):
    body = await request.json()
    prompt = body["prompt"]
    session_id = generate_session_id()
    sse_queues[session_id] = asyncio.Queue()

    async def run_agent():
        session = await session_service.create_session(
            app_name="playable-storybook", user_id=session_id
        )
        async for event in runner.run(
            user_id=session_id, session_id=session.id,
            new_message=types.Content(parts=[types.Part(text=prompt)])
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        parsed = try_parse_json(part.text)
                        if parsed and "level_id" in parsed:
                            stream_to_client(session_id,
                                {"type": "level_ready", "data": parsed})
                        elif parsed and "title" in parsed:
                            stream_to_client(session_id,
                                {"type": "story_plan", "data": parsed})
                        else:
                            stream_to_client(session_id,
                                {"type": "narration", "text": part.text})
        stream_to_client(session_id, {"type": "complete"})

    asyncio.create_task(run_agent())

    async def sse_generator():
        queue = sse_queues[session_id]
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
        while True:
            event = await queue.get()
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            if event.get("type") == "complete":
                break

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.post("/api/next-chapter")
async def next_chapter(request: Request):
    # Re-runs LevelBuilder for the next chapter
    # with the same story_pack from the session
    ...

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    ...

app.mount("/", StaticFiles(directory="frontend/dist", html=True))
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Vanilla JS + HTML5 Canvas | Full control, no framework overhead |
| Build tool | Vite | Fast dev server |
| Backend | Python + FastAPI | Async-native, SSE streaming, ADK ecosystem |
| Agent Framework | Google ADK | SequentialAgent, LlmAgent, tools, sessions |
| AI — Sprites | Gemini 2.5 Flash (interleaved image) | Text + images in one call |
| AI — Music | Gemini 2.5 Flash (native audio) | Ambient loops per chapter |
| AI — Level Design | Gemini 2.5 Flash (JSON mode) | Structured level layout generation |
| Streaming | SSE (Server-Sent Events) | Real-time interleaved stream to client |
| Game SFX | Web Audio API (procedural) | Zero latency, theme-selectable |
| Deploy | Google Cloud Run | Scales to zero, Google ecosystem |
| Package Manager | uv | Fast Python dependency management |

---

## Project Structure

```
playable-storybook/
+-- requirements.txt
+-- .env                              <- GEMINI_API_KEY
|
+-- backend/
|   +-- main.py                       <- FastAPI app: serves static + SSE API
|   +-- agent/
|   |   +-- __init__.py
|   |   +-- agent.py                  <- CreativeDirector SequentialAgent
|   |   +-- tools.py                  <- ADK tools (interleaved, chapter, audio)
|   +-- stream_parser.py              <- Extract text/image/audio from response
|   +-- sprite_cleaner.py             <- rembg + crop; chroma key fallback
|   +-- level_validator.py            <- Level JSON validator + auto-fixer
|
+-- frontend/
|   +-- package.json
|   +-- vite.config.js
|   +-- index.html
|   +-- src/
|   |   +-- main.js                   <- Entry point, game loop orchestration
|   |   +-- game/
|   |   |   +-- GameLoop.js
|   |   |   +-- Input.js
|   |   |   +-- Camera.js
|   |   |   +-- Physics.js
|   |   |   +-- Player.js
|   |   |   +-- Enemy.js
|   |   |   +-- Pickup.js
|   |   |   +-- Platform.js
|   |   |   +-- Block.js
|   |   |   +-- Projectile.js
|   |   |   +-- Hazard.js
|   |   |   +-- BouncePad.js
|   |   |   +-- Teleporter.js
|   |   |   +-- Particles.js
|   |   |   +-- Weather.js
|   |   |   +-- SoundManager.js       <- Procedural Web Audio SFX
|   |   |   +-- MusicPlayer.js        <- Ambient music loops
|   |   +-- scene/
|   |   |   +-- SceneLoader.js        <- Loads theme + level, per-level overrides
|   |   |   +-- Renderer.js
|   |   +-- story/
|   |   |   +-- Dialogue.js
|   |   +-- ui/
|   |   |   +-- Storyboard.js         <- Live storyboard (SSE stream)
|   |   |   +-- MenuScreen.js         <- Title + prompt input
|   |   +-- api/
|   |       +-- client.js             <- SSE client + REST fetch
|   +-- dist/                         <- Vite build output
|
+-- mock/                             <- Mock data for development
|   +-- theme.json
|   +-- level_000.json                <- Flat vector, auto-runner
|   +-- level_001.json                <- Retro pixel, platformer
|   +-- level_002.json                <- Retro pixel, combat
|   +-- level_003.json                <- Retro pixel, challenge
|   +-- sprites/                      <- Retro theme sprites
|   +-- backgrounds/                  <- Flat vector theme assets
|
+-- SPEC.md                           <- Full technical specification
+-- AI.md                             <- AI architecture reference (for LLMs)
+-- SUMMARY.md                        <- Human-readable project overview
```

---

## Generation Timeline

```
0:00  User types story prompt, clicks GO
0:03  StoryPlanner: story plan JSON
0:03  StoryArchitect: 4 assets (character, enemy, platform, background)
0:03  Live storyboard begins — sprites stream in
0:25  rembg + crop applied to sprites
0:28  LevelBuilder: Ch1 background + music + level JSON (parallel)
0:28  Level JSON validated and auto-fixed
0:32  "Play Now" button appears — total wait ~30-40s

0:32  Player starts Chapter 1
      Background music loops, procedural SFX play on events

      Meanwhile: LevelBuilder pre-generates Chapter 2 in background

      Player finishes Chapter 1:
      -> Chapter 2 already ready -> instant transition (0s wait)
      -> New ambient music crossfades in
      -> Player starts Chapter 2

      Meanwhile: LevelBuilder pre-generates Chapter 3

      Player finishes Chapter 2:
      -> Chapter 3 already ready -> instant transition (0s wait)
      -> Player starts Chapter 3
      -> Story resolution screen
```

---

## Build Order

### Tier 1: Core Game Engine (DONE)
1. Canvas game loop + input handler
2. Player movement + gravity + jump
3. Platform collision (rect-based)
4. Camera follow
5. Background rendering

### Tier 2: Gameplay Mechanics (DONE)
6. Coin/item pickup + blocks
7. Enemy patrol + stomp kill
8. Health system + damage
9. Exit zone + level transition
10. Projectiles (laser/sword)
11. Enemy behaviors (chase, shoot)
12. Hazards, bounce pads, teleporters

### Tier 3: Theme-Adaptive Engine (DONE)
13. Auto-run mode
14. Dark mode spotlight
15. Weather system
16. Per-level asset overrides
17. Ground color theming
18. Multiple art styles (retro, flat vector)
19. Procedural SFX (SoundManager)

### Tier 4: Story & Mission System (DONE)
20. Mission types (collect_all, kill_all, survive, find_key_exit, reach_exit)
21. Mission HUD tracker
22. Chapter intro with mission briefing
23. Background music player (MusicPlayer)
24. Story-connected narration between levels

### Tier 5: ADK Backend (NEXT)
25. FastAPI project setup + ADK dependencies
26. StoryPlanner agent (text-only, JSON mode)
27. StoryArchitect agent + 4-asset generation (character, enemy, platform, background)
28. LevelBuilder agent + parallel bg/music/layout generation
29. Sprite background removal (rembg + crop; magenta chroma key fallback)
30. Level Validator + auto-fixer
31. SSE endpoint streaming agent output to frontend
32. Content safety fallback (soften prompt → retry → mock data)
33. Chapter pre-fetching (generate Ch N+1 while player plays Ch N)
34. Connect: prompt -> StoryPlanner -> StoryArchitect -> LevelBuilder -> SSE -> storyboard -> play

### Tier 6: Polish
35. Smooth transitions between all states
36. Error handling (stream failures, retries, fallbacks)
37. Loading states and progress indicators

---

## Server-Side Processing

### Level Validator + Auto-Fixer

Gemini-generated level JSONs are validated and auto-fixed before sending to the frontend:

| Check | Auto-Fix |
|-------|----------|
| Platform gaps > max jump distance (350px) | Insert bridge platform |
| Enemies floating (no platform below) | Snap to nearest platform surface |
| Pickups floating (no platform below) | Snap to nearest platform surface |
| Exit unreachable | Add stepping-stone platforms |
| Missing ground platform | Add default ground at y=850 |
| Missing player_spawn | Default to {x: 60, y: 780} |
| Missing exit | Add exit at far-right of world |
| Platform height gaps > max jump height (200px) | Add intermediate platforms |
| Mission target_count > actual entities | Adjust target_count to match |

### Sprite Background Removal (rembg + crop)

Sprites are generated with solid magenta (#ff00ff) background. Server-side pipeline:

1. **rembg** — `rembg.remove(img)` using U2Net ONNX model. Works best on 3D mascot / solid-opaque sprites.
2. **Crop** — Alpha-threshold crop to trim transparent padding (`mask.getbbox()` with `a > 10`).
3. **Fallback** — For watercolor/soft-edge art, rembg may over-remove; use chroma key (sample border color, key on that) instead.

Frontend `spriteCleaner.js` has `gl-chromakey` fallback for any remaining solid-color bleed. Applied to character, enemy_1, platform (not background).

---

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Agent count | 3 agents (StoryPlanner + StoryArchitect + LevelBuilder) | StoryPlanner decouples planning; enables future parallelism |
| Generation approach | Gemini interleaved output | Mandatory — single call returns text + images together |
| Sprite generation | 4 assets (character, enemy, platform, background) | Procedural pickups; dummy NPC/exit/breakable; rembg-friendly magenta bg |
| Asset labeling | `[ASSET: role_name]` in narration | Reliable identification of which image is which |
| Background removal | Server-side rembg + crop | Magenta bg → rembg → alpha-threshold crop; chroma key fallback |
| Level validation | Server-side validator + auto-fixer | Guarantees playable levels even with imperfect AI output |
| Chapter pre-fetching | Generate Ch(N+1) while player plays Ch(N) | Zero wait between chapters |
| Content safety | Soften prompt → retry → fallback to mock | Graceful degradation if Gemini refuses content |
| Background music | Gemini-generated ambient audio | Each story gets a unique soundtrack |
| Game SFX | Procedural Web Audio | Zero latency, works offline, theme-selectable |
| Art style variety | Per-level asset overrides | Same engine, different PNGs = different game |
| Mechanics variety | JSON-configured per chapter | AI selects from ~15 mechanics, infinite combinations |
| Loading UX | Live storyboard stream | Generation process IS the experience |
| Video (Veo) | Stretch goal, not core | Game is the interactive experience; video adds risk |
| Cloud Storage | Stretch goal, not core | Serve assets inline for demo; add GCS for production |
| Client streaming | SSE (Server-Sent Events) | Simple, reliable, perfect for interleaved parts |
| Rendering | HTML5 Canvas 2D | Simplest, no framework overhead |
| Collision | Rect-based (AABB) | Simple, reliable |

---

## Why Interleaved Output + ADK Matters

Traditional approach:
- 15+ separate API calls for text, images, audio
- No creative coherence between assets
- Custom orchestration code for every step
- Loading spinner while generating

Our approach:
- **StoryPlanner** — fast text-only story plan (~2-3s)
- **StoryArchitect** — 4 sprites (character, enemy, platform, background) with magenta bg + rembg
- ADK's `SequentialAgent` chains specialized agents with `output_key` state passing
- The agent **reasons about creative coherence** — "this pirate world needs warm tones" — and generates everything in that style
- **Multi-turn chat sessions** maintain visual consistency across all sprites
- **Server-side processing** (checkerboard removal, level validation) ensures quality output
- **Pre-fetching** generates upcoming chapters while the player is still playing
- The user **watches the world being created** — text, images, and music appear together
- The generation process itself is a **multimodal storytelling experience**

### Reference: Proven Patterns

| Source | Pattern Used |
|--------|-------------|
| [Way Back Home Level 0](https://codelabs.developers.google.com/way-back-home-level-0) | Interleaved image generation, multi-turn chat for consistency |
| [Survivor Network (Level 2)](https://codelabs.developers.google.com/codelabs/survivor-network) | SequentialAgent pipeline, tool definitions, output_key |

---

## Stretch Goals (v2+)

- Veo cinematic video intros (chapter 1 + final chapter)
- Cloud Storage for persistent asset hosting
- Boss fights with unique AI-generated boss sprites
- Story branching (player choices affect next chapter)
- AI companion/sidekick with generated personality
- In-world story narration (text floating in the level)
- Mobile touch controls
- Save/share generated stories
- ADK bidi streaming for live NPC voice
- Vertex AI Memory Bank (remember user preferences across stories)

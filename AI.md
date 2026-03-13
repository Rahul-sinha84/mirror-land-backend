# AI Architecture — Playable Storybook

## Overview

Three ADK agents generate a complete playable game from a single user prompt. The frontend game engine is already built — the AI's job is to produce the JSON config and image/audio assets that drive it.

**Design principle:** Keep the pipeline simple and reliable. Story plan first (fast), then sprites, then levels. Total time to first playable chapter: ~30–40 seconds.

---

## Agent Pipeline

```
CreativeDirector (SequentialAgent)
│
├── 1. StoryPlanner (LlmAgent)                    ~2–3s
│       Model: gemini-2.5-flash (JSON mode)
│       Output key: "story_plan"
│       → Story plan JSON (title, premise, art_style, 3 chapters, mechanics)
│
├── 2. StoryArchitect (LlmAgent)                   ~15–25s
│       Model: gemini-2.5-flash-preview-image-generation
│       Input: story_plan
│       Output key: "story_pack"
│       → 4 AI-generated assets: character, enemy_1, platform, background
│       → Server-side: rembg + crop on sprites
│
└── 3. LevelBuilder (LlmAgent)                     ~8–10s per chapter
        Model: gemini-2.5-flash
        Input: story_plan + story_pack
        → Level JSON + background image + ambient music
```

**Non-AI assets (no generation):**
- **Character:** Optional single shared character across all games (one pre-cleaned sprite)
- **Pickups (coin, health, key):** Procedural per-theme drawing in frontend
- **NPC, exit_door, breakable, enemy_2:** Dummy/placeholder assets per theme

---

## Agent 1: StoryPlanner

**Model:** gemini-2.5-flash
**Modalities:** TEXT only (JSON mode)
**Called:** Once per story
**Output key:** `story_plan`

**Input:** User's story prompt

**Output:** Story plan JSON containing:
- `title`, `premise`, `art_style`, `mood`, `sound_pack`
- 3 chapters: `title`, `setting`, `narration`, `mission`, `mechanics`, `difficulty`
- `characters` object: descriptions for hero, enemy_1, platform (used in sprite prompts)

**Why separate:** Decouples planning from image generation. Fast (~2–3s), reliable, enables future parallelism (e.g. sprites + intro video in parallel).

---

## Agent 2: StoryArchitect

**Model:** gemini-2.5-flash-preview-image-generation
**Modalities:** TEXT + IMAGE (interleaved)
**Called:** Once per story
**Input:** `story_plan`
**Output key:** `story_pack`

**Outputs (4 AI-generated assets):**

| Asset | Role | Notes |
|-------|------|-------|
| character | Player hero | Or use single shared character (no generation) |
| enemy_1 | Primary enemy | Theme-specific |
| platform | Platform tile | Tileable horizontally |
| background | Chapter 1 background | Wide, stitchable for parallax |

**Generation strategy:** 4 parallel API calls (or 2 batches of 2). Same art style from `story_plan` applied to all prompts.

**Sprite style constraints (rembg-friendly):**
- 3D mascot / toy aesthetic, simple silhouette (Angry-Birds-like)
- Solid opaque body, no thin strands, no particles, no fog
- Solid flat #ff00ff magenta background edge-to-edge
- 1024x1024 output, character fills ~65% frame
- Strictly facing right, side profile

**Post-processing:** Each sprite (except background) → rembg (background removal) → alpha-threshold crop → save.

---

## Art Style Definitions

The AI must pick ONE art style per story and generate ALL assets in that style. The style is included in every image generation prompt to keep things consistent.

| Style ID | Visual Description | Best For |
|---|---|---|
| `retro_pixel` | 8-bit pixel art, bold primary colors, chunky outlines, nostalgic NES feel | Pirate, dungeon, classic adventure, fantasy RPG |
| `flat_vector` | Clean geometric shapes, smooth gradients, no outlines, atmospheric lighting | Nature, journey, night scenes, sci-fi landscapes |
| `neon_cyberpunk` | Pure black background, glowing neon outlines in pink/cyan/purple, synthwave | Hacker, space, digital, robot, futuristic |
| `watercolor` | Soft bleeding edges, pastel washes, paper texture feel, dreamy | Fairy tale, garden, dream, gentle stories |
| `ink_manga` | Bold black ink strokes on white/cream, halftone dot shading, high contrast | Ninja, samurai, martial arts, action |
| `chalk` | Colorful chalk strokes on dark blackboard background, hand-drawn feel | School, childhood, whimsical, imagination |
| `gothic` | Dark and moody, deep reds/blacks/grays, stone textures, dramatic shadows | Horror, vampire, haunted, dark fantasy |

### Style Selection Rules (for the AI prompt)

The agent's system instruction should include:

```
Choose an art style based on the user's story prompt:
- Pirates, treasure, medieval, fantasy -> retro_pixel
- Mountains, ocean, nature, travel, night -> flat_vector
- Space, robots, hacking, digital, future -> neon_cyberpunk
- Fairy, garden, dream, gentle, magical -> watercolor
- Ninja, samurai, warrior, temple, martial -> ink_manga
- School, kids, imagination, silly, crayon -> chalk
- Horror, vampire, ghost, dark, haunted -> gothic

If the prompt doesn't clearly match, pick the style that best fits the mood.
Apply the chosen style consistently to EVERY generated image.
```

---

## Asset Generation Prompt Templates

Only 4 assets are AI-generated. All use a **rembg-friendly** style: 3D mascot, solid opaque body, simple silhouette, magenta background.

### Universal Sprite Constraints (append to every sprite prompt)

```
SIMPLE SPRITE CONSTRAINTS:
- Angry-birds-like simple silhouette (compact round/oval body)
- Side profile, strictly facing right
- Large readable shapes only, minimal detail
- No thin strands, no loose particles, no smoke/fog
- Solid opaque body (no translucent paint effects)
- Centered character, fills ~65% of frame

BACKGROUND: Solid pure #ff00ff magenta, edge-to-edge, no gradients, no texture, no shadows.

OUTPUT: 1024x1024, game-ready cutout-friendly edges.
```

### Character (if generated; otherwise use shared character)

```
3D mascot sprite, {theme_description}, angry-birds-like simple round silhouette,
side profile strictly facing right, solid opaque body, minimal detail,
no thin strands/particles/fog, centered ~65% frame,
pure #ff00ff background edge-to-edge (no gradient/shadow), 1024x1024, game-ready cutout.
```

### Enemy 1

```
3D mascot enemy sprite, {enemy_1_description}, angry-birds-like simple silhouette,
side profile strictly facing right, solid opaque body, minimal detail,
no thin strands/particles/fog, centered ~65% frame,
pure #ff00ff background edge-to-edge, 1024x1024, game-ready cutout.
```

### Platform Tile

```
3D mascot platform tile, {platform_description}, side view with clear top surface,
simple readable shape, tileable horizontally, solid opaque,
pure #ff00ff background edge-to-edge, 1024x1024, game-ready cutout.
```

### Background (per chapter)

```
Wide 2D side-scrolling game background, 1920x1080.
Art style: {art_style}.
Scene: {chapter_setting_description}.
Seamless horizontal tile, left and right edges must match for parallax.
No characters, no UI, no text.
```

### Non-Generated Assets

| Asset | Source |
|-------|--------|
| coin, health, key | Procedural drawing per theme (`pickupStyles.js`) |
| npc, exit_door, breakable, enemy_2 | Dummy/placeholder assets per theme |
| character (optional) | Single shared pre-cleaned sprite across all games |

### Important Notes for Image Generation

1. **Magenta background** — Enables reliable chroma key or rembg. Pure #ff00ff, no variation.
2. **Solid opaque body** — Watercolor/soft edges cause rembg to over-remove; avoid.
3. **Simple silhouette** — Thin limbs/hair get cropped; use compact mascot shapes.
4. **1024x1024** — Standard size; frontend scales via `renderScale` in mechanics.
5. **Background** — No magenta; full scene. Stitchable for parallax scrolling.

---

## Agent 3: LevelBuilder

**Model:** gemini-2.5-flash (for level JSON) + image/audio APIs for background and music
**Called:** Once per chapter (3 times per story)
**Input:** `story_plan` + `story_pack` (from StoryPlanner and StoryArchitect)

**Output:**

1. Background image (per chapter; Chapter 1 uses StoryArchitect's background, Ch2/Ch3 generate new ones)

2. Ambient music loop (via native audio model, 15-30 seconds, loopable)

3. Level layout JSON containing:
   - `platforms` — ground + floating, optional moving platforms
   - `pickups` — coins, key, health placed along path
   - `enemies` — with behavior (patrol / chase / shoot)
   - `blocks` — breakable, optional items inside
   - `hazards` — spikes / lava / acid
   - `bounce_pads` — vertical launchers
   - `teleporters` — linked portal pairs
   - `npcs` — with story-relevant dialogue lines
   - `exit` — unlock condition matching the mission
   - `player_spawn` — starting position
   - `physics` — gravity, jump_force, move_speed, friction
   - `mechanics` — auto_run, player_action, weather, dark_mode, etc.
   - `mission` — type, description, target_count, success/fail text
   - `ground_color` — matches the art style

**Key technique:** Level JSON uses `response_mime_type: "application/json"` for reliable structured output.

---

## How It Connects to the Frontend

The frontend is a complete game engine that reads JSON config:

| AI Generates | Engine Uses It For |
|---|---|
| Story plan JSON | Chapter intro screens, narration text |
| Character sprite (or shared) | Player avatar |
| Enemy sprites | Enemy visuals |
| Platform sprite | Level tile visuals |
| Background image | Scrolling level background |
| Ambient music | Background loop during gameplay |
| Level layout JSON | Platform positions, enemy placements, pickup locations |
| Mechanics config | Enables/disables player abilities, weather, spotlight |
| Mission config | Sets win condition, HUD display, completion text |
| Physics config | Controls gravity, speed, jump height |

**Non-AI:** Coin/health/key drawn procedurally per theme. NPC, exit_door, breakable, enemy_2 use dummy assets.

---

## SSE Stream Events (Backend -> Frontend)

| Event | Data | When |
|---|---|---|
| `narration` | `{ text }` | Each text part from interleaved response |
| `image` | `{ role, url }` | Each sprite/background generated |
| `audio` | `{ role, url }` | Ambient music generated |
| `story_plan` | `{ title, chapters[] }` | Story plan JSON parsed |
| `level_ready` | `{ level_json, assets }` | Level layout ready to play |
| `complete` | `{}` | All generation done |

---

## Backend Flow (FastAPI)

1. `POST /api/create-story` — receives prompt, returns SSE stream
2. StoryPlanner runs → `story_plan` JSON
3. StoryArchitect runs with `story_plan` → 4 sprites (rembg + crop) → stream as SSE events
4. LevelBuilder runs for Chapter 1 → `level_ready` event
5. Frontend shows "Play Now"
6. `POST /api/next-chapter` — when player finishes, returns pre-fetched or runs LevelBuilder for next chapter

---

## What the AI Must Get Right

1. **Visual consistency** — all 4 sprites (character, enemy, platform, background) must share the same art style from `story_plan`
2. **Rembg-friendly sprites** — solid opaque body, simple silhouette, magenta background; avoid watercolor/soft edges
3. **Playable levels** — platforms reachable, gaps jumpable, enemies fair
4. **Mechanics fit the story** — space → low gravity + laser; fairy → double jump + fog
5. **Mission makes sense** — objective matches the narrative
6. **Level progression** — Ch1 easy, Ch2 medium, Ch3 hard

---

## Available Mechanics (finite set, AI picks per chapter)

| Category | Options |
|---|---|
| Player action | none, laser_shot, sword_slash |
| Movement | normal, auto_run |
| Jump | single, double_jump |
| Vision | normal, dark_mode (spotlight) |
| Gravity | 0.5x (floaty) to 1.5x (heavy) |
| Weather | none, rain, snow, fog, embers |
| Enemy behavior | patrol, chase, shoot |
| Hazard types | spikes, lava, acid |
| Level objects | platforms, blocks, bounce_pads, teleporters |
| Mission types | find_key_exit, collect_all, kill_all, survive, reach_exit |
| Art styles | retro_pixel, flat_vector, neon, watercolor, ink_manga, chalk, gothic |
| Sound packs | retro, sci_fi, fantasy |

The beauty: ~15 mechanics, but the combinations are practically infinite.

---

## ADK Setup Summary

- **Framework:** Google ADK (Agent Development Kit)
- **Root agent:** `SequentialAgent` named `CreativeDirector`
- **Sub-agents (order):** `StoryPlanner` → `StoryArchitect` → `LevelBuilder`
- **State passing:** `output_key` — StoryPlanner outputs `story_plan`, StoryArchitect outputs `story_pack`
- **LevelBuilder input:** `story_plan` + `story_pack`
- **Sessions:** `InMemorySessionService` (stores story_pack between chapter calls)
- **Tools:** `generate_interleaved_assets`, `generate_chapter_level`
- **Streaming:** FastAPI SSE endpoint wraps ADK runner output

---

## Game World Constraints (Critical for Level Generation)

The AI MUST know these constraints or it will generate unplayable levels.

### Coordinate System

- Origin (0,0) is top-left
- X increases to the right
- Y increases downward (y=0 is top of screen, y=1080 is bottom)
- Game viewport: 960x540 (scaled to fit browser window)
- World height: always 1080
- World width: 3840 (short level) to 5760 (long level)

### Player Dimensions and Abilities

- Player size: 48w x 64h pixels
- Player spawn: typically x=60, y=780 (near left edge, above ground)
- Max jump height: ~180px (with gravity=1200, jump_force=-700)
- Max horizontal jump distance: ~280px at full speed (move_speed=300)
- Double jump adds: ~150px additional height
- Player falls at max_fall_speed: 600

### Platform Placement Rules

- Ground platforms: y=850, h=230 (fills bottom of world)
- Floating platforms: y=500-800 range, h=48
- MAXIMUM gap between platforms: 250px (player can't cross wider gaps)
- MAXIMUM height difference between platforms: 160px (player can't jump higher)
- With double_jump enabled: max height difference increases to 300px
- Moving platforms: move_range 50-150px, move_speed 40-80
- Platform minimum width: 192px (one tile)

### Enemy Placement Rules

- Ground enemies: place on ground level, y = ground_y - enemy_height (typically y=806)
- Flying enemies: y=700-780 range (above ground, reachable by jump)
- Patrol range: 100-300px width
- Chase enemies: detect_range 200-400px, chase_speed 150-250
- Shooting enemies: shoot_interval 1.5-3 seconds, shoot_range 300-500
- Don't cluster more than 2 enemies within 200px — unfair difficulty

### Pickup Placement

- Coins: y = platform_y - 32 (float above the surface)
- Key: place in a challenging but reachable location
- Health: place after difficult sections (after hazards or enemy clusters)
- Space pickups 40px apart horizontally when in a row

### Hazard Placement

- Spikes: h=12, placed on ground surface (y = ground_y - 12)
- Lava/acid: h=20-40, placed in ground gaps
- Always leave enough space to jump over (max hazard width: 200px)
- Place a health pickup within 500px after a hazard

### Difficulty Scaling

| Aspect | Chapter 1 (Easy) | Chapter 2 (Medium) | Chapter 3 (Hard) |
|---|---|---|---|
| Enemies | 3-4, patrol only | 5-7, mix patrol + chase | 8-10, patrol + chase + shoot |
| Hazards | 0-1 | 2-3 | 3-5 |
| Gaps | Small (100-150px) | Medium (150-200px) | Large (200-250px) |
| Pickups | Generous health | Moderate health | Sparse health |
| Blocks | 2-3 with items | 3-4 with items | 4-5, some empty |
| Special | Bounce pad intro | Teleporter intro | Dark mode / complex layout |
| Mission | find_key_exit or reach_exit | collect_all or kill_all | survive or kill_all |

---

## Story Plan JSON Schema

StoryArchitect must output this exact structure:

```json
{
  "story_id": "generated-uuid",
  "title": "Tides of the Cursed Isle",
  "premise": "A young sailor recovers cursed gems from haunted islands",
  "art_style": "retro_pixel",
  "mood": "adventure_mystery",
  "sound_pack": "retro",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "The Cursed Shore",
      "setting": "twilight pirate island shore with fog and wooden docks",
      "narration": "You arrive at the cursed island as the fog thickens...",
      "mission": {
        "type": "find_key_exit",
        "description": "Find the Skull Key and escape through the ancient gate",
        "target_count": 1,
        "success_text": "The gate creaks open. Beyond lies the sunken caves...",
        "fail_text": "The curse tightens its grip..."
      },
      "mechanics": {
        "auto_run": false,
        "player_action": "none",
        "gravity_scale": 1.0,
        "double_jump": false,
        "dark_mode": false,
        "weather": "fog",
        "weather_intensity": 0.6
      },
      "difficulty": "easy"
    },
    {
      "chapter_number": 2,
      "title": "The Sunken Caves",
      "setting": "underwater crystal caves with bioluminescence",
      "narration": "Deep beneath the island, the caves glow with cursed light...",
      "mission": {
        "type": "kill_all",
        "description": "Clear the caves of 6 cursed spirits",
        "target_count": 6,
        "success_text": "The spirits dissolve. A hidden passage reveals itself...",
        "fail_text": "The spirits overwhelm you..."
      },
      "mechanics": {
        "auto_run": false,
        "player_action": "laser_shot",
        "gravity_scale": 1.0,
        "double_jump": true,
        "dark_mode": false,
        "weather": "snow",
        "weather_intensity": 0.5
      },
      "difficulty": "medium"
    },
    {
      "chapter_number": 3,
      "title": "The Ember Throne",
      "setting": "volcanic throne room with lava and ancient ruins",
      "narration": "The final gem lies in the heart of the volcano...",
      "mission": {
        "type": "collect_all",
        "description": "Collect all 5 cursed gems before the volcano erupts",
        "target_count": 5,
        "success_text": "The curse is broken. The seas are safe once more.",
        "fail_text": "The volcano claims another soul..."
      },
      "mechanics": {
        "auto_run": false,
        "player_action": "sword_slash",
        "gravity_scale": 1.0,
        "double_jump": true,
        "dark_mode": true,
        "spotlight_radius": 140,
        "weather": "embers",
        "weather_intensity": 0.8
      },
      "difficulty": "hard"
    }
  ],
  "characters": {
    "hero": "A young sailor in a tattered blue coat",
    "enemy_1": "Ghost crabs with glowing blue eyes",
    "enemy_2": "Skeleton pirates with cutlasses",
    "npc": "A wise old parrot perched on a post",
    "coin": "Gold doubloons with skull emblem",
    "health": "Bottle of enchanted rum",
    "key": "Ornate skull key in rusty iron",
    "platform": "Wooden ship planks, weathered and mossy",
    "breakable": "Old barrel with iron bands",
    "exit_door": "Ancient stone gate with ship wheel mechanism"
  }
}
```

The `characters` object provides descriptions used in the asset generation prompts.

---

## Asset Labeling Strategy

When Gemini returns interleaved images, the backend must identify which image is which asset.

**Approach: Sequential prompting with explicit labels.**

StoryArchitect generates 4 assets. Use `[ASSET: role_name]` labels before each image:

```
Generate the following assets in this exact order.
Before each image, write the label on its own line: [ASSET: role_name]

1. [ASSET: character] — hero character
2. [ASSET: enemy_1] — primary enemy
3. [ASSET: platform] — platform tile
4. [ASSET: background] — chapter 1 background
```

**Backend parsing logic:**

1. Iterate through response parts in order
2. When you see text containing `[ASSET: xyz]`, set `current_role = "xyz"`
3. When you see the next inline image, assign it to `current_role`
4. Run rembg + crop on character, enemy_1, platform (not background)

---

## Execution Timeline

```
Player clicks GO
    |
    v
StoryPlanner (~2-3s)
    |   story_plan JSON
    v
StoryArchitect (~15-25s)
    |   4 assets (character, enemy, platform, background)
    |   rembg + crop on sprites
    |   stream to frontend storyboard
    v
LevelBuilder: Chapter 1 (~8-10s)
    |
    +---> "Play Now" — player starts Chapter 1
    |
    +---> LevelBuilder: Chapter 2 (starts in background)
              |
              v
          Chapter 2 READY before player finishes Chapter 1
              |
              +---> LevelBuilder: Chapter 3 (starts when Ch2 done)
```

**Total time to first playable chapter:** ~30–40 seconds.

### Parallel Chapter Pre-fetching

1. After StoryArchitect finishes, LevelBuilder runs for Chapter 1
2. As soon as Chapter 1 `level_ready` is sent, LevelBuilder starts Chapter 2 **in the background**
3. When the player finishes Chapter 1, Chapter 2 is already generated — instant transition
4. Chapter 3 starts when Chapter 2 is done (or pre-fetched)

### Backend Implementation

```
POST /api/create-story:
  1. Run StoryPlanner -> story_plan
  2. Run StoryArchitect(story_plan) -> stream 4 sprites to frontend
  3. Run LevelBuilder(chapter_1) -> send level_ready
  4. Start LevelBuilder(chapter_2) in background task

POST /api/next-chapter:
  1. Check if next chapter is pre-fetched
  2. If yes -> return immediately
  3. If no -> run LevelBuilder, stream results
  4. Pre-fetch the chapter after that
```

---

## Sprite Background Removal (Server-Side)

Sprites are generated with solid magenta (#ff00ff) background. Server-side pipeline: **rembg** (AI segmentation) → **alpha-threshold crop** → save. Frontend has `gl-chromakey` fallback for any remaining solid-color bleed.

### Pipeline

1. **rembg** — Run each sprite through `rembg.remove(img)`. Uses U2Net ONNX model locally; no LLM call. Works best on 3D mascot / solid-opaque sprites.
2. **Crop** — Use alpha-threshold crop to trim transparent padding:
   - `mask = alpha.point(lambda a: 255 if a > 10 else 0)`
   - `bbox = mask.getbbox()` then `img.crop(bbox)`
   - Optional: add 8–16px padding to avoid cutting thin limbs (use lower threshold `a > 2` for mascots)
3. **Save** — PNG with RGBA.

### When rembg Fails (watercolor / soft edges)

For watercolor or soft-edge art, rembg often over-removes (turns body semi-transparent). **Solution:** Use chroma key instead of rembg for those assets:
- Sample border pixels to detect actual background color
- Use `gl-chromakey` (frontend) or Pillow-based chroma key (backend)
- Tune tolerance, smoothness, spill for clean edges

### Fallback (Frontend)

Frontend `spriteCleaner.js`:
- If `hasMeaningfulTransparency` → skip (already clean)
- If `detectUniformBorder` finds solid color → `gl-chromakey`
- Else → checkerboard/gray flood-fill (legacy path)

### When to Apply

- Apply to: character, enemy_1, platform (all magenta-background sprites)
- Do NOT apply to: background (full scene, no removal)
- Run server-side immediately after receiving each image, before SSE/serving

---

## Level Validator + Fixer

After Gemini generates a level JSON, run it through validation before sending to the frontend. This catches and auto-fixes unplayable layouts.

### Checks and Auto-Fixes

**1. Ground exists**
- Check: At least one platform with `role: "ground"` exists
- Fix: Add a full-width ground at y=850, h=230

**2. Player spawn is on solid ground**
- Check: A platform exists beneath `player_spawn.x, player_spawn.y`
- Fix: Move spawn to x=60, y = first_ground.y - 70

**3. Platforms are reachable**
- Check: For each platform, the previous one is within jump reach (gap < 250px horizontal, height diff < 160px, or < 300px with double_jump)
- Fix: Insert a bridge platform halfway between unreachable platforms

**4. Gaps are crossable**
- Check: Ground gaps are < 250px wide (< 350px with double_jump)
- Fix: Shrink the gap by extending the left ground segment

**5. Enemies are on valid surfaces**
- Check: Each ground enemy has a platform beneath it
- Fix: Move enemy y to sit on the nearest platform below

**6. Mission requirements exist**
- Check: If mission is `find_key_exit`, at least one `key` pickup exists. If `collect_all`, enough coins exist to meet `target_count`. If `kill_all`, enemy count matches `target_count`.
- Fix: Add missing key/coins/enemies at reasonable positions

**7. Exit is reachable**
- Check: Exit is on or above a platform, and a platform path exists from spawn to exit
- Fix: Place exit on the last ground segment

**8. World bounds are valid**
- Check: `world.width` >= 2000, `world.height` == 1080, no entity is outside world bounds
- Fix: Clamp all positions to world bounds, set minimums

**9. Physics are sane**
- Check: `gravity` between 800-1600, `jump_force` between -900 and -400, `move_speed` between 150-500
- Fix: Clamp to valid ranges

### Implementation Approach

This runs server-side after `LevelBuilder` returns the JSON, before sending `level_ready` to the frontend. It's a pure data transform — no AI calls needed. Pseudocode:

```
function validateAndFixLevel(level):
    ensureGroundExists(level)
    fixPlayerSpawn(level)
    fixUnreachablePlatforms(level, level.mechanics.double_jump)
    fixGroundGaps(level, level.mechanics.double_jump)
    fixEnemyPlacement(level)
    fixMissionRequirements(level)
    fixExitPlacement(level)
    clampWorldBounds(level)
    clampPhysics(level)
    return level
```

This is ~50-80 lines of Python. It turns "mostly correct" Gemini output into guaranteed-playable levels.

---

## Stretch Goals (not in MVP)

- **IntroGenerator (Veo)** — 4s cinematic video + narration audio, runs in parallel with StoryArchitect after StoryPlanner. Defer until core pipeline is stable.
- Cloud Storage for persistent asset hosting
- AI companion with generated personality and dialogue
- Story branching based on player choices
- Live NPC voice via bidi audio streaming

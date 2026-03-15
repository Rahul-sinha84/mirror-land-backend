# NPC Voice with Gemini TTS — Implementation Verification Prompt

**Use this prompt to ask another LLM to verify the implementation.**

---

## Your Task

Verify that the following implementation correctly implements the **NPC Voice with Gemini TTS and Language Support** feature for a playable storybook backend. Check for:

1. **API correctness** — Gemini TTS usage (model, config, response handling)
2. **Concurrency** — Semaphore, timeout, `asyncio.gather` with `return_exceptions`
3. **Edge cases** — No NPCs, system dialogue, long text, TTS failure, unsupported language
4. **Storage** — Directory creation before WAV write, slug sanitization for filenames
5. **Non-blocking flow** — `generate_chapter_level` streams `level_ready` immediately, spawns background TTS, streams `npc_audio` events
6. **Blocking flow** — `prefetch_chapter_level` awaits `_generate_npc_voices` before write/stream
7. **Completeness** — All 10 todos from the plan are implemented

---

## Todo Order (from plan)

| # | Todo | Status |
|---|------|--------|
| 1 | deps-validate | Verify/add google-genai in requirements.txt |
| 2 | story-planner-language | Add language to StoryPlanner + update validate_story_plan |
| 3 | level-builder-language | Add Language section to LevelBuilder instruction |
| 4 | level-gen-language | Pass language instruction to LevelBuilder |
| 5 | tts-service | Create services/tts_gen.py + tests/test_tts_gen.py |
| 6 | tts-standalone-test | Run standalone TTS test |
| 7 | tools-helper | Add _generate_npc_voices() and _generate_npc_voices_and_stream() |
| 8 | tools-integrate-chapter | Non-blocking TTS in generate_chapter_level |
| 9 | tools-integrate-prefetch | Blocking TTS in prefetch_chapter_level |
| 10 | e2e-verify | Document frontend contract in README |

---

## Expected Architecture

**generate_chapter_level (non-blocking):**
1. Write level_json to disk (no audio_url)
2. Stream `level_ready` immediately
3. Spawn `asyncio.create_task(_generate_npc_voices_and_stream(...))`
4. Background: TTS per line → stream `npc_audio` → update level file when done

**prefetch_chapter_level (blocking):**
1. `level_json = await _generate_npc_voices(...)`
2. Write level_json with audio_url
3. Stream `level_ready`

---

## File 1: `requirements.txt`

```txt
google-adk>=1.27.0
google-genai>=1.0.0
google-auth>=2.0
fastapi>=0.115.0
uvicorn[standard]
sse-starlette
httpx>=0.27.0
rembg[cpu]>=2.0.72
Pillow>=10.0
python-dotenv
pydantic>=2.0
```

**Context:** `google-genai>=1.0.0` added for TTS (todo 1).

---

## File 2: `services/tts_gen.py`

```python
"""
NPC dialogue audio generation via Gemini TTS (gemini-2.5-flash-preview-tts).
"""

import base64
import logging
import os
import wave

from google.genai import types

from services.gemini_client import get_client

logger = logging.getLogger(__name__)

TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Sulafat"

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "ru": "Russian", "es": "Spanish",
    "fr": "French", "de": "German", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese", "pt": "Portuguese", "ar": "Arabic",
}

SUPPORTED_LANGUAGES = set(LANGUAGE_NAMES.keys())


def _write_wav(output_path: str, pcm: bytes) -> None:
    """Write PCM data to WAV file (24kHz, mono, s16le)."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)


async def generate_npc_dialogue_audio(
    text: str,
    speaker_name: str,
    mood: str,
    output_path: str,
    language: str = "en",
) -> str | None:
    if len(text) > 400:
        text = text[:397] + "..."
        logger.warning("Truncated long dialogue to 400 chars for TTS")

    lang = language if language in SUPPORTED_LANGUAGES else "en"
    if language != lang:
        logger.warning("Language %s not supported, falling back to en", language)

    lang_name = LANGUAGE_NAMES.get(lang, "English")
    prompt = (
        f"Speak the following {lang_name} dialogue naturally, warmly and clearly, "
        f"like a {mood} game character:\n{text}"
    )

    try:
        client = get_client()
        response = await client.aio.models.generate_content(
            model=TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=DEFAULT_VOICE,
                        )
                    )
                ),
            ),
        )
    except RuntimeError as e:
        if "GOOGLE_API_KEY" in str(e):
            logger.warning("TTS skipped: %s", e)
            return None
        raise
    except Exception as e:
        logger.warning("TTS generation failed: %s", e)
        return None

    if not response.candidates:
        logger.warning("TTS returned no candidates")
        return None

    parts = response.candidates[0].content.parts
    if not parts:
        logger.warning("TTS returned no parts")
        return None

    data = None
    for part in parts:
        if part.inline_data and part.inline_data.data:
            data = part.inline_data.data
            break

    if not data:
        logger.warning("TTS returned no audio data")
        return None

    if isinstance(data, str):
        pcm = base64.b64decode(data)
    else:
        pcm = data

    try:
        _write_wav(output_path, pcm)
        logger.info("Saved NPC TTS -> %s (%d bytes)", output_path, len(pcm))
        return output_path
    except Exception as e:
        logger.warning("Failed to write TTS WAV: %s", e)
        return None
```

**Context:** TTS service (todo 5). Uses `gemini-2.5-flash-preview-tts`, voice `Sulafat`, `os.makedirs` before write, base64/bytes handling, long text truncation, unsupported language fallback. Slug sanitization is in agent/tools.py.

---

## File 3: `agent/tools.py` (relevant sections)

**Imports and helpers:**
```python
import asyncio
import json
import logging
import os
import re

from services.tts_gen import generate_npc_dialogue_audio
from sse import stream_to_client

def _npc_slug(name: str) -> str:
    """Convert NPC name to filesystem-safe slug."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "npc"

TTS_SEMAPHORE = asyncio.Semaphore(3)
TTS_TIMEOUT = 15
```

**_generate_npc_voices (blocking):**
```python
async def _generate_npc_voices(
    level_json: dict,
    session_id: str,
    output_dir: str,
    story_plan: dict,
    chapter_number: int,
) -> dict:
    npcs = level_json.get("npcs") or []
    if not npcs:
        return level_json

    language = story_plan.get("language", "en")
    mood = story_plan.get("mood", "adventure")

    async def _one_line(npc: dict, idx: int, line: dict) -> tuple[str | None, dict, int]:
        speaker = line.get("speaker", "")
        text = (line.get("text") or "").strip()
        if speaker == "system" or not text or len(text) > 400:
            return None, line, idx
        name = npc.get("name", "npc")
        slug = _npc_slug(name)
        filename = f"npc_{slug}_{chapter_number}_{idx}.wav"
        path = os.path.join(output_dir, filename)
        async with TTS_SEMAPHORE:
            try:
                result = await asyncio.wait_for(
                    generate_npc_dialogue_audio(
                        text=text, speaker_name=name, mood=mood,
                        output_path=path, language=language,
                    ),
                    timeout=TTS_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("TTS timeout for %s line %d", name, idx)
                return None, line, idx
            except Exception as e:
                logger.warning("TTS failed for %s line %d: %s", name, idx, e)
                return None, line, idx
        if result:
            url = _asset_url(session_id, result)
            line["audio_url"] = url
            return url, line, idx
        return None, line, idx

    tasks = []
    for npc in npcs:
        dialogue = npc.get("dialogue") or []
        for idx, line in enumerate(dialogue):
            tasks.append(_one_line(npc, idx, line))

    await asyncio.gather(*tasks, return_exceptions=True)
    return level_json
```

**_generate_npc_voices_and_stream (non-blocking):**
```python
async def _generate_npc_voices_and_stream(
    level_json: dict,
    session_id: str,
    output_dir: str,
    story_plan: dict,
    chapter_number: int,
    level_path: str,
) -> None:
    npcs = level_json.get("npcs") or []
    if not npcs:
        return

    language = story_plan.get("language", "en")
    mood = story_plan.get("mood", "adventure")

    async def _one_line(npc: dict, idx: int, line: dict) -> None:
        speaker = line.get("speaker", "")
        text = (line.get("text") or "").strip()
        if speaker == "system" or not text or len(text) > 400:
            return
        name = npc.get("name", "npc")
        slug = _npc_slug(name)
        filename = f"npc_{slug}_{chapter_number}_{idx}.wav"
        path = os.path.join(output_dir, filename)
        async with TTS_SEMAPHORE:
            try:
                result = await asyncio.wait_for(
                    generate_npc_dialogue_audio(
                        text=text, speaker_name=name, mood=mood,
                        output_path=path, language=language,
                    ),
                    timeout=TTS_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("TTS timeout for %s line %d", name, idx)
                return
            except Exception as e:
                logger.warning("TTS failed for %s line %d: %s", name, idx, e)
                return
        if result:
            url = _asset_url(session_id, result)
            line["audio_url"] = url
            await stream_to_client(session_id, {
                "type": "npc_audio",
                "data": {"npc": name, "line_index": idx, "audio_url": url},
            })

    tasks = [_one_line(npc, idx, line) for npc in npcs for idx, line in enumerate(npc.get("dialogue") or [])]
    await asyncio.gather(*tasks, return_exceptions=True)

    try:
        with open(level_path, "w") as f:
            json.dump(level_json, f, indent=2)
    except Exception as e:
        logger.warning("Failed to update level file with audio_url: %s", e)
```

**generate_chapter_level (non-blocking integration):**
```python
# In the else block when level_json is not Exception:
level_path = os.path.join(output_dir, f"level_ch{chapter_number:02d}.json")
with open(level_path, "w") as f:
    json.dump(level_json, f, indent=2)
result["level_json"] = level_json
result["level_path"] = level_path
asyncio.create_task(
    _generate_npc_voices_and_stream(
        level_json, session_id, output_dir,
        story_plan, chapter_number, level_path,
    )
)
# ... later: stream level_ready with level_json (no audio_url yet)
```

**prefetch_chapter_level (blocking integration):**
```python
# In the else block when level_json is not Exception:
level_json = await _generate_npc_voices(level_json, session_id, output_dir, story_plan, chapter_number)
level_path = os.path.join(output_dir, f"level_ch{chapter_number:02d}.json")
with open(level_path, "w") as f:
    json.dump(level_json, f, indent=2)
```

---

## File 4: `agent/prompts.py` (language-related changes)

**StoryPlanner schema:**
```json
"language": "<BCP-47 code: en, hi, ru, es, fr, de, ja, ko, zh, pt, ar, etc.>",
```

**StoryPlanner Language section:**
```
## Language

- Infer the story language from the user's prompt: "in Hindi", "Hindi story", "हिंदी में" -> "hi"; "in Russian" -> "ru"; etc.
- **Default: "en"** when no language hint is present.
- Use BCP-47 codes: en, hi, ru, es, fr, de, ja, ko, zh, pt, ar, etc.
- **CRITICAL:** All text output MUST be written in that language.
- **Exception:** Character descriptions in `characters` may stay in English for sprite generation.
```

**LevelBuilder Language section:**
```
## Language

- All in-game text (NPC dialogue, locked_dialogue, mission description, success_text, fail_text) MUST match the story plan language.
- Default to English if language is not specified in the story plan.
```

---

## File 5: `services/level_gen.py` (language instruction)

```python
language = story_plan.get("language", "en")

user_message = (
    f"LANGUAGE: All dialogue and in-game text must be in {language}. (en=English, hi=Hindi, ru=Russian, es=Spanish, fr=French, de=German, ja=Japanese, ko=Korean, zh=Chinese, pt=Portuguese, ar=Arabic)\n\n"
    f"Generate a level layout for Chapter {chapter_num}: "
    ...
)
```

---

## File 6: `tests/test_story_planner.py` (validation changes)

```python
VALID_LANGUAGES = {"en", "hi", "ru", "es", "fr", "de", "ja", "ko", "zh", "pt", "ar"}

# In validate_story_plan:
for field in ("story_id", "title", "premise", "art_style", "mood", "sound_pack", "language"):
    if field not in plan:
        errors.append(f"Missing top-level field: {field}")

if plan.get("language") not in VALID_LANGUAGES:
    errors.append(f"Invalid language: {plan.get('language')}. Must be one of {VALID_LANGUAGES}")
```

---

## File 7: `tests/test_tts_gen.py`

```python
# Calls generate_npc_dialogue_audio("Hello, little one! Welcome to our village.", ...)
# Validates WAV (RIFF, sample_rate, channels)
# Graceful fallback when GOOGLE_API_KEY not set
```

---

## File 8: `tests/test_npc_voice.py`

```python
# Test 1: _generate_npc_voices(level_with_empty_npcs) -> returns unchanged
# Test 2: _generate_npc_voices(level_with_one_npc_one_line) with mock TTS -> dialogue has audio_url
# Test 3: speaker == "system" line -> no TTS call, no audio_url
```

---

## Verification Checklist

| Check | Expected |
|-------|----------|
| Model | `gemini-2.5-flash-preview-tts` |
| Voice | `Sulafat` |
| response_modalities | `["AUDIO"]` |
| speech_config | VoiceConfig + PrebuiltVoiceConfig |
| Base64 handling | `if isinstance(data, str): pcm = base64.b64decode(data)` |
| WAV params | 24kHz, mono, sample_width=2 |
| Directory creation | `os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)` (in tts_gen._write_wav) |
| Slug sanitization | `re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")` (in tools._npc_slug) |
| Filename format | `npc_{slug}_{chapter_number}_{idx}.wav` (avoids cross-chapter collision) |
| Semaphore | `asyncio.Semaphore(3)` |
| Timeout | `asyncio.wait_for(..., timeout=15)` |
| No NPCs | Early return `if not npcs` |
| System dialogue | Skip `speaker == "system"` |
| Long text | Truncate `len(text) > 400` |
| generate_chapter_level | Non-blocking: write → stream level_ready → create_task |
| prefetch_chapter_level | Blocking: await _generate_npc_voices before write |
| npc_audio event | `{"type": "npc_audio", "data": {"npc", "line_index", "audio_url"}}` |

---

## Output Format

Please provide:

1. **PASS / FAIL** for each verification category (API, Concurrency, Edge cases, Storage, Flow completeness)
2. **Any issues found** with file name and line number
3. **Overall score** (e.g., 9/10) and brief summary

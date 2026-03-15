"""
NPC dialogue audio generation via Gemini TTS (gemini-2.5-flash-preview-tts).

Generates WAV files for NPC dialogue lines. Requires GOOGLE_API_KEY in .env.
Gracefully returns None if the API is not configured or the call fails,
so the frontend can fall back to text-only display.
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
    "en": "English",
    "hi": "Hindi",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "pt": "Portuguese",
    "ar": "Arabic",
}

SUPPORTED_LANGUAGES = set(LANGUAGE_NAMES.keys())

# Mood -> Gemini TTS voice (from https://ai.google.dev/gemini-api/docs/speech-generation#voices)
MOOD_TO_VOICE = {
    "whimsical_wonder": "Leda",      # Youthful
    "dark_tension": "Gacrux",        # Mature
    "adventure_mystery": "Sulafat",  # Warm
}


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
    """
    Generate NPC dialogue audio via Gemini TTS.

    Returns the path to the saved WAV file, or None if generation
    is unavailable or fails.
    """
    if len(text) > 400:
        text = text[:397] + "..."
        logger.warning("Truncated long dialogue to 400 chars for TTS")

    lang = language if language in SUPPORTED_LANGUAGES else "en"
    if language != lang:
        logger.warning("Language %s not supported, falling back to en", language)

    voice_name = MOOD_TO_VOICE.get(mood, DEFAULT_VOICE)
    mood_desc = (mood or "").replace("_", " ")
    lang_name = LANGUAGE_NAMES.get(lang, "English")
    prompt = (
        f"Speak the following {lang_name} dialogue naturally, warmly and clearly, "
        f"like a {mood_desc} game character:\n{text}"
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
                            voice_name=voice_name,
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

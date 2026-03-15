"""
Phase 6 test: TTS generation via Gemini.

Usage:
    python tests/test_tts_gen.py

If GOOGLE_API_KEY is not set, the test verifies graceful fallback
(returns None, does not crash). If it IS set, generates a WAV file and
validates it.
"""

import asyncio
import os
import struct
import sys

from services.tts_gen import generate_npc_dialogue_audio

OUTPUT_DIR = os.path.join("static", "test_assets")


def validate_wav(path: str) -> list[str]:
    """Basic WAV header validation. Returns list of errors (empty = valid)."""
    errors = []
    try:
        with open(path, "rb") as f:
            riff = f.read(4)
            if riff != b"RIFF":
                errors.append(f"Not a RIFF file (got {riff!r})")
                return errors
            f.read(4)  # file size
            wave_marker = f.read(4)
            if wave_marker != b"WAVE":
                errors.append(f"Not a WAVE file (got {wave_marker!r})")
                return errors

            fmt_found = False
            while True:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break
                chunk_size_raw = f.read(4)
                if len(chunk_size_raw) < 4:
                    break
                chunk_size = struct.unpack("<I", chunk_size_raw)[0]

                if chunk_id == b"fmt ":
                    fmt_found = True
                    fmt_data = f.read(chunk_size)
                    if len(fmt_data) >= 16:
                        channels = struct.unpack("<H", fmt_data[2:4])[0]
                        sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
                        print(f"  WAV format: channels={channels}, sample_rate={sample_rate}")
                        if sample_rate != 24000:
                            errors.append(f"Expected sample rate 24000, got {sample_rate}")
                elif chunk_id == b"data":
                    data_size = chunk_size
                    print(f"  WAV data size: {data_size} bytes")
                    if data_size < 100:
                        errors.append(f"Audio data too small: {data_size} bytes")
                    f.seek(chunk_size, 1)
                else:
                    f.seek(chunk_size, 1)

            if not fmt_found:
                errors.append("No fmt chunk found in WAV")

    except Exception as e:
        errors.append(f"Failed to read WAV: {e}")

    return errors


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "npc_test.wav")

    print("=== TTS Generation (Gemini) ===\n")

    result = await generate_npc_dialogue_audio(
        text="Hello, little one! Welcome to our village.",
        speaker_name="Test NPC",
        mood="adventure",
        output_path=output_path,
        language="en",
    )

    if result is None:
        print("\nResult: None (TTS not generated)")
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("EXPECTED — GOOGLE_API_KEY is not set.")
            print("This is fine: frontend handles missing audio gracefully.")
            print("\nTo enable NPC voice:")
            print("  1. Add GOOGLE_API_KEY to .env from https://aistudio.google.com/apikey")
            print("\nPASSED — graceful fallback works correctly (no crash)")
        else:
            print("WARNING — GOOGLE_API_KEY is set but generation failed.")
            print("Check the logs above for details.")
        return

    print(f"\nResult: {result}")
    if not os.path.exists(result):
        print(f"ERROR: file not found at {result}")
        return

    file_size = os.path.getsize(result)
    print(f"File size: {file_size} bytes ({file_size / 1024:.1f} KB)")

    errors = validate_wav(result)
    if errors:
        print(f"\nWAV ISSUES ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nPASSED — WAV file generated and validated successfully")
        print(f"Play it: open {result}")


if __name__ == "__main__":
    asyncio.run(main())

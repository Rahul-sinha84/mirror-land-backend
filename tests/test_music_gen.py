"""
Phase 5 test: Music generation via Lyria.

Usage:
    python tests/test_music_gen.py

If GOOGLE_CLOUD_PROJECT is not set, the test verifies graceful fallback
(returns None, does not crash). If it IS set, generates a WAV file and
validates it.
"""

import asyncio
import os
import struct
import sys

from services.audio_gen import generate_ambient_music

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
            wave = f.read(4)
            if wave != b"WAVE":
                errors.append(f"Not a WAVE file (got {wave!r})")
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
                        audio_fmt = struct.unpack("<H", fmt_data[0:2])[0]
                        channels = struct.unpack("<H", fmt_data[2:4])[0]
                        sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
                        print(f"  WAV format: {audio_fmt}, channels: {channels}, sample_rate: {sample_rate}")
                        if sample_rate not in (44100, 48000):
                            errors.append(f"Unexpected sample rate: {sample_rate}")
                elif chunk_id == b"data":
                    data_size = chunk_size
                    print(f"  WAV data size: {data_size} bytes")
                    if data_size < 1000:
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
    output_path = os.path.join(OUTPUT_DIR, "ambient_ch1.wav")

    print("=== Phase 5: Music Generation (Lyria) ===\n")

    result = await generate_ambient_music(
        prompt="soft bouncy candy planet landscape with sparkles and gentle wonder",
        mood="whimsical_wonder",
        output_path=output_path,
    )

    if result is None:
        print("\nResult: None (music not generated)")
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project:
            print("EXPECTED — GOOGLE_CLOUD_PROJECT is not set.")
            print("This is fine: frontend handles missing music gracefully.")
            print("\nTo enable Lyria music generation:")
            print("  1. Enable Vertex AI API: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com")
            print("  2. Set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION in .env")
            print("  3. Run: gcloud auth application-default login")
            print("\nPASSED — graceful fallback works correctly (no crash)")
        else:
            print("WARNING — GOOGLE_CLOUD_PROJECT is set but generation failed.")
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

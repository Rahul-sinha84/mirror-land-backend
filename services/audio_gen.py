"""
Ambient music generation via Lyria (lyria-002) on Vertex AI.

Generates a ~32.8s instrumental WAV loop per chapter. Requires:
  - GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION in .env
  - Vertex AI API enabled in GCP console
  - gcloud auth application-default login

Gracefully returns None if Lyria is not configured or the call fails,
so the frontend can handle missing music without crashing.
"""

import base64
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LYRIA_MODEL = "lyria-002"


def _get_vertex_config() -> tuple[str, str] | None:
    """Return (project_id, location) or None if not configured."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        return None
    return project, location


def _get_access_token() -> str | None:
    """Get a Google Cloud access token via application default credentials."""
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default()
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token
    except Exception as e:
        logger.warning("Failed to get access token: %s", e)
        return None


async def generate_ambient_music(
    prompt: str,
    mood: str,
    output_path: str,
) -> str | None:
    """
    Generate ambient music via Lyria on Vertex AI.

    Returns the path to the saved WAV file, or None if generation
    is unavailable or fails.
    """
    config = _get_vertex_config()
    if config is None:
        logger.warning(
            "Lyria not configured: set GOOGLE_CLOUD_PROJECT in .env. "
            "Skipping music generation."
        )
        return None

    project_id, location = config
    token = _get_access_token()
    if token is None:
        logger.warning(
            "Could not obtain access token. Run: gcloud auth application-default login"
        )
        return None

    full_prompt = (
        f"ambient {mood} background music loop for a video game, "
        f"{prompt}, instrumental, loopable, 30 seconds"
    )

    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/"
        f"publishers/google/models/{LYRIA_MODEL}:predict"
    )

    payload = {
        "instances": [
            {
                "prompt": full_prompt,
            }
        ],
    }

    logger.info("Generating ambient music via Lyria (%s)...", LYRIA_MODEL)
    logger.info("Prompt: %s", full_prompt)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code != 200:
            logger.warning(
                "Lyria API returned %d: %s",
                response.status_code,
                response.text[:500],
            )
            return None

        data = response.json()
        predictions = data.get("predictions", [])
        if not predictions:
            logger.warning("Lyria returned no predictions")
            return None

        pred = predictions[0]
        audio_b64 = pred.get("bytesBase64Encoded") or pred.get("audioContent")
        if not audio_b64:
            logger.warning("Lyria prediction missing audio data. Keys in response: %s", list(pred.keys()))
            return None

        audio_bytes = base64.b64decode(audio_b64)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        logger.info("Saved ambient music -> %s (%d bytes)", output_path, len(audio_bytes))
        return output_path

    except Exception as e:
        logger.warning("Lyria music generation failed: %s", e)
        return None

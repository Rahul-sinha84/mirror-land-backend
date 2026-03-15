"""
Unit tests for _generate_npc_voices helper.

Usage:
    python tests/test_npc_voice.py
    pytest tests/test_npc_voice.py -v
"""

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tools import _generate_npc_voices


def _level_with_empty_npcs() -> dict:
    return {
        "level_id": "level_001",
        "npcs": [],
        "platforms": [],
    }


def _level_with_one_npc_one_line() -> dict:
    return {
        "level_id": "level_001",
        "npcs": [
            {
                "role": "npc",
                "name": "Peppermint Elder",
                "x": 200,
                "y": 800,
                "dialogue": [
                    {"speaker": "Peppermint Elder", "text": "Welcome, little one!"},
                ],
            }
        ],
        "platforms": [],
    }


def _level_with_system_line() -> dict:
    return {
        "level_id": "level_001",
        "npcs": [
            {
                "role": "npc",
                "name": "Guide",
                "dialogue": [
                    {"speaker": "Guide", "text": "Hello!"},
                    {"speaker": "system", "text": "Find the key."},
                ],
            }
        ],
        "platforms": [],
    }


class TestGenerateNpcVoices(unittest.IsolatedAsyncioTestCase):
    """Tests for _generate_npc_voices."""

    async def test_empty_npcs_returns_unchanged(self):
        """Empty npcs list should return level unchanged."""
        level = _level_with_empty_npcs()
        with tempfile.TemporaryDirectory() as tmp:
            result = await _generate_npc_voices(
                level,
                session_id="test",
                output_dir=tmp,
                story_plan={"language": "en", "mood": "adventure"},
                chapter_number=1,
            )
        self.assertEqual(result, level)
        self.assertEqual(result.get("npcs"), [])

    @patch("agent.tools.generate_npc_dialogue_audio", new_callable=AsyncMock)
    async def test_one_npc_adds_audio_url(self, mock_tts):
        """One NPC with one line should get audio_url when TTS succeeds."""
        mock_tts.return_value = "/path/to/npc_peppermint_elder_0.wav"
        level = _level_with_one_npc_one_line()
        with tempfile.TemporaryDirectory() as tmp:
            # Mock returns the path we pass; we need to return a path in output_dir
            def side_effect(text, speaker_name, mood, output_path, language="en"):
                with open(output_path, "wb") as f:
                    f.write(b"fake_wav_data")
                return output_path

            mock_tts.side_effect = side_effect
            result = await _generate_npc_voices(
                level,
                session_id="test",
                output_dir=tmp,
                story_plan={"language": "en", "mood": "adventure"},
                chapter_number=1,
            )
        self.assertIsNotNone(result)
        npcs = result.get("npcs", [])
        self.assertEqual(len(npcs), 1)
        dialogue = npcs[0].get("dialogue", [])
        self.assertEqual(len(dialogue), 1)
        self.assertIn("audio_url", dialogue[0])
        self.assertIn("npc_peppermint_elder_1_0.wav", dialogue[0]["audio_url"])

    @patch("agent.tools.generate_npc_dialogue_audio", new_callable=AsyncMock)
    async def test_system_line_no_tts(self, mock_tts):
        """Lines with speaker 'system' should not trigger TTS."""
        level = _level_with_system_line()
        with tempfile.TemporaryDirectory() as tmp:
            result = await _generate_npc_voices(
                level,
                session_id="test",
                output_dir=tmp,
                story_plan={"language": "en", "mood": "adventure"},
                chapter_number=1,
            )
        self.assertEqual(mock_tts.call_count, 1)
        npcs = result.get("npcs", [])
        dialogue = npcs[0].get("dialogue", [])
        self.assertIn("audio_url", dialogue[0])
        self.assertNotIn("audio_url", dialogue[1])


if __name__ == "__main__":
    unittest.main()

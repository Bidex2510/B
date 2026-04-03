"""Generate voiceover audio using OpenAI TTS or ElevenLabs."""

import os
import requests
from openai import OpenAI
from config.settings import settings


def generate_voiceover(narration: str, output_path: str) -> str:
    """Generate voiceover audio from narration text."""
    if settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_VOICE_ID:
        return _generate_elevenlabs(narration, output_path)
    return _generate_openai_tts(narration, output_path)


def _generate_openai_tts(narration: str, output_path: str) -> str:
    """Use OpenAI TTS for voiceover."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.audio.speech.create(
        model="tts-1-hd",
        voice="onyx",  # Deep, engaging voice good for TikTok
        input=narration,
        speed=1.05,  # Slightly faster for TikTok pacing
    )

    response.stream_to_file(output_path)
    print(f"  Voiceover saved: {output_path}")
    return output_path


def _generate_elevenlabs(narration: str, output_path: str) -> str:
    """Use ElevenLabs for higher quality voiceover."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.ELEVENLABS_API_KEY,
    }

    data = {
        "text": narration,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.5,
            "use_speaker_boost": True,
        },
    }

    response = requests.post(url, json=data, headers=headers, timeout=120)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"  Voiceover saved: {output_path}")
    return output_path

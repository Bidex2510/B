"""Configuration settings for the TikTok AI Video Automation."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # TikTok
    TIKTOK_CLIENT_KEY: str = os.getenv("TIKTOK_CLIENT_KEY", "")
    TIKTOK_CLIENT_SECRET: str = os.getenv("TIKTOK_CLIENT_SECRET", "")
    TIKTOK_ACCESS_TOKEN: str = os.getenv("TIKTOK_ACCESS_TOKEN", "")

    # ElevenLabs (optional)
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")

    # Video
    VIDEO_NICHE: str = os.getenv("VIDEO_NICHE", "motivational")
    VIDEO_DURATION: int = int(os.getenv("VIDEO_DURATION", "30"))
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920  # 9:16 vertical for TikTok

    # Scheduling
    POSTING_HOUR: int = int(os.getenv("POSTING_HOUR", "10"))
    POSTING_MINUTE: int = int(os.getenv("POSTING_MINUTE", "0"))
    TIMEZONE: str = os.getenv("TIMEZONE", "UTC")

    # Paths
    OUTPUT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    TEMP_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.TIKTOK_ACCESS_TOKEN:
            missing.append("TIKTOK_ACCESS_TOKEN")
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
        os.makedirs(cls.TEMP_DIR, exist_ok=True)


settings = Settings()

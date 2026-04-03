"""Generate video scripts using OpenAI GPT."""

import json
import random
from datetime import datetime
from openai import OpenAI
from config.settings import settings

NICHES = {
    "motivational": {
        "themes": ["success", "discipline", "mindset", "hustle", "self-improvement"],
        "style": "powerful, emotional, inspiring",
    },
    "facts": {
        "themes": ["science", "history", "nature", "psychology", "space"],
        "style": "fascinating, mind-blowing, educational",
    },
    "tech": {
        "themes": ["AI", "programming", "gadgets", "future tech", "cybersecurity"],
        "style": "informative, exciting, cutting-edge",
    },
    "finance": {
        "themes": ["investing", "saving", "passive income", "crypto", "budgeting"],
        "style": "practical, actionable, wealth-building",
    },
    "scary": {
        "themes": ["urban legends", "true crime", "mysteries", "paranormal", "creepy facts"],
        "style": "suspenseful, eerie, captivating",
    },
}

# Ordered list for daily rotation
NICHE_ROTATION = ["motivational", "facts", "tech", "finance", "scary"]


def get_todays_niche() -> str:
    """Get today's niche based on day-of-year rotation through all 5 niches."""
    day_of_year = datetime.now().timetuple().tm_yday
    return NICHE_ROTATION[day_of_year % len(NICHE_ROTATION)]


def generate_script(niche: str = None) -> dict:
    """Generate a video script with title, narration, and image prompts."""
    niche = niche or get_todays_niche()
    niche_config = NICHES.get(niche, NICHES["motivational"])
    theme = random.choice(niche_config["themes"])

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""Create a short TikTok video script about "{theme}" in the {niche} niche.
Style: {niche_config['style']}

Return a JSON object with:
- "title": catchy TikTok caption with hashtags (max 150 chars)
- "hook": attention-grabbing first line (max 10 words)
- "narration": full voiceover script for a {settings.VIDEO_DURATION}-second video
- "scenes": array of 4-6 scene objects, each with:
  - "text": short text overlay for this scene (max 8 words)
  - "image_prompt": detailed image generation prompt for the background (photorealistic style, vertical 9:16)
  - "duration": seconds this scene should last

The total scene durations should add up to {settings.VIDEO_DURATION} seconds.
Make the narration engaging and viral-worthy. Use short punchy sentences.

Return ONLY valid JSON, no markdown."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=1500,
    )

    script = json.loads(response.choices[0].message.content)
    script["niche"] = niche
    script["theme"] = theme
    return script

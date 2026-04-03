"""Generate images for video scenes using OpenAI DALL-E."""

import os
import requests
from openai import OpenAI
from config.settings import settings


def generate_scene_images(scenes: list[dict], output_dir: str) -> list[str]:
    """Generate an image for each scene and return file paths."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    image_paths = []

    for i, scene in enumerate(scenes):
        prompt = scene["image_prompt"]
        # Ensure vertical orientation for TikTok
        prompt += " Vertical orientation, 9:16 aspect ratio, high quality, cinematic lighting."

        print(f"  Generating image {i + 1}/{len(scenes)}...")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1792",  # Vertical for TikTok
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        image_path = os.path.join(output_dir, f"scene_{i:02d}.png")

        # Download the image
        img_data = requests.get(image_url, timeout=60).content
        with open(image_path, "wb") as f:
            f.write(img_data)

        image_paths.append(image_path)

    return image_paths

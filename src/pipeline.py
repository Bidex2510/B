"""Main pipeline: generate script -> images -> voiceover -> video -> upload."""

import os
import shutil
from datetime import datetime

from config.settings import settings
from src.script_generator import generate_script
from src.image_generator import generate_scene_images
from src.voiceover import generate_voiceover
from src.video_composer import compose_video
from src.tiktok_uploader import TikTokUploader


def run_pipeline(niche: str = None, upload: bool = True) -> str:
    """Run the full video generation and upload pipeline."""
    settings.validate()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = os.path.join(settings.TEMP_DIR, timestamp)
    os.makedirs(work_dir, exist_ok=True)

    try:
        # 1. Generate script
        print("[1/5] Generating script...")
        script = generate_script(niche)
        print(f"  Title: {script['title']}")
        print(f"  Theme: {script['theme']}")

        # 2. Generate scene images
        print("[2/5] Generating images...")
        image_paths = generate_scene_images(script["scenes"], work_dir)

        # 3. Generate voiceover
        print("[3/5] Generating voiceover...")
        audio_path = os.path.join(work_dir, "voiceover.mp3")
        generate_voiceover(script["narration"], audio_path)

        # 4. Compose video
        print("[4/5] Composing video...")
        video_filename = f"tiktok_{timestamp}.mp4"
        output_path = os.path.join(settings.OUTPUT_DIR, video_filename)
        compose_video(script["scenes"], image_paths, audio_path, output_path)

        # 5. Upload to TikTok
        if upload:
            print("[5/5] Uploading to TikTok...")
            uploader = TikTokUploader()
            result = uploader.upload_video(output_path, script["title"])
            print(f"  Upload result: {result}")
        else:
            print("[5/5] Skipping upload (upload=False)")

        print(f"\nDone! Video saved to: {output_path}")
        return output_path

    finally:
        # Clean up temp files
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)

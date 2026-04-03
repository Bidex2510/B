"""Compose final video from images, text overlays, and voiceover."""

import os
from moviepy.editor import (
    ImageClip,
    TextClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
from config.settings import settings


def compose_video(
    scenes: list[dict],
    image_paths: list[str],
    audio_path: str,
    output_path: str,
) -> str:
    """Compose a TikTok video from scenes, images, and voiceover."""
    print("  Composing video...")

    audio = AudioFileClip(audio_path)
    clips = []

    for i, (scene, img_path) in enumerate(zip(scenes, image_paths)):
        duration = scene.get("duration", settings.VIDEO_DURATION / len(scenes))

        # Background image
        img_clip = (
            ImageClip(img_path)
            .set_duration(duration)
            .resize((settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT))
        )

        # Text overlay
        text = scene.get("text", "")
        if text:
            txt_clip = (
                TextClip(
                    text,
                    fontsize=60,
                    color="white",
                    font="Arial-Bold",
                    stroke_color="black",
                    stroke_width=3,
                    size=(settings.VIDEO_WIDTH - 100, None),
                    method="caption",
                )
                .set_duration(duration)
                .set_position(("center", "center"))
            )
            clip = CompositeVideoClip([img_clip, txt_clip])
        else:
            clip = img_clip

        clips.append(clip)

    # Concatenate all scene clips
    final_video = concatenate_videoclips(clips, method="compose")

    # Trim or loop audio to match video length
    video_duration = final_video.duration
    if audio.duration > video_duration:
        audio = audio.subclip(0, video_duration)

    final_video = final_video.set_audio(audio)

    # Export
    final_video.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )

    # Cleanup
    final_video.close()
    audio.close()
    for clip in clips:
        clip.close()

    print(f"  Video saved: {output_path}")
    return output_path

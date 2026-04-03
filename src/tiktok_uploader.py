"""Upload videos to TikTok using the TikTok Content Posting API."""

import os
import time
import requests
from config.settings import settings

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokUploader:
    """Handles video uploads to TikTok via the Content Posting API."""

    def __init__(self):
        self.access_token = settings.TIKTOK_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def upload_video(self, video_path: str, title: str) -> dict:
        """Upload a video to TikTok with the given title/caption."""
        file_size = os.path.getsize(video_path)

        # Step 1: Initialize the upload
        print("  Initializing TikTok upload...")
        init_response = self._init_upload(title, file_size)
        upload_url = init_response["data"]["upload_url"]
        publish_id = init_response["data"]["publish_id"]

        # Step 2: Upload the video file
        print("  Uploading video file...")
        self._upload_file(upload_url, video_path, file_size)

        # Step 3: Check publish status
        print("  Waiting for TikTok to process...")
        result = self._wait_for_publish(publish_id)

        return result

    def _init_upload(self, title: str, file_size: int) -> dict:
        """Initialize a video upload via TikTok API."""
        url = f"{TIKTOK_API_BASE}/post/publish/video/init/"

        payload = {
            "post_info": {
                "title": title,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"TikTok init failed: {data}")

        return data

    def _upload_file(self, upload_url: str, video_path: str, file_size: int):
        """Upload the video binary to TikTok's upload URL."""
        with open(video_path, "rb") as f:
            headers = {
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                "Content-Type": "video/mp4",
            }
            response = requests.put(
                upload_url, data=f, headers=headers, timeout=300
            )
            response.raise_for_status()

    def _wait_for_publish(self, publish_id: str, max_retries: int = 10) -> dict:
        """Poll TikTok for publish status until complete."""
        url = f"{TIKTOK_API_BASE}/post/publish/status/fetch/"

        for attempt in range(max_retries):
            response = requests.post(
                url,
                json={"publish_id": publish_id},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("data", {}).get("status")

            if status == "PUBLISH_COMPLETE":
                print("  Video published successfully!")
                return data
            elif status in ("FAILED", "PUBLISH_FAILED"):
                raise RuntimeError(f"TikTok publish failed: {data}")

            wait_time = min(5 * (attempt + 1), 30)
            print(f"  Status: {status}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

        raise TimeoutError("TikTok publish timed out after max retries")

"""TikTok official Content Posting API - OAuth flow + video publishing.

Uses TikTok for Developers OAuth - never stores raw passwords.
Register your app: https://developers.tiktok.com/
"""

import os
import json
import time
from pathlib import Path
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8000/api/tiktok-publish/callback")

TOKEN_FILE = Path(os.getenv("JARVIS_DATA_DIR", "/tmp/jarvis")) / "tiktok_token.json"
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

OAUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
POST_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
POST_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
USER_URL = "https://open.tiktokapis.com/v2/user/info/"

SCOPES = "user.info.basic,video.publish,video.upload"


class VideoUploadRequest(BaseModel):
    video_url: str  # publicly accessible URL of MP4
    caption: Optional[str] = ""
    privacy: str = "SELF_ONLY"  # SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, PUBLIC_TO_EVERYONE
    disable_duet: bool = False
    disable_comment: bool = False
    disable_stitch: bool = False


def _load_token():
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None


def _save_token(token: dict):
    token["saved_at"] = int(time.time())
    TOKEN_FILE.write_text(json.dumps(token, indent=2))


async def _ensure_fresh_token():
    token = _load_token()
    if not token:
        return None
    expires_at = token.get("saved_at", 0) + token.get("expires_in", 0) - 60
    if time.time() < expires_at:
        return token
    # refresh
    refresh = token.get("refresh_token")
    if not refresh:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_key": CLIENT_KEY,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code == 200:
        new = resp.json()
        new["refresh_token"] = new.get("refresh_token", refresh)
        _save_token(new)
        return new
    return None


@router.get("/setup")
async def setup_guide():
    """Step-by-step instructions to connect your TikTok account safely."""
    return {
        "why_oauth": "TikTok bans accounts that use password-based bots. OAuth is the only safe + official way.",
        "steps": [
            "1. Go to https://developers.tiktok.com/ and log in with your TikTok account",
            "2. Click 'Manage apps' → 'Connect an app'",
            "3. Choose 'Web' platform, give it a name like 'My Jarvis'",
            "4. Add scopes: user.info.basic, video.publish, video.upload",
            "5. Set Redirect URI to: " + REDIRECT_URI,
            "6. Copy 'Client Key' and 'Client Secret' into your .env file as TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET",
            "7. Restart Jarvis, then visit /api/tiktok-publish/oauth-url to get your authorization link",
            "8. Open the link, log in to TikTok, approve - you're done. Jarvis can now post.",
        ],
        "cost": "FREE - TikTok Developer accounts are free",
        "what_you_can_do": [
            "Auto-publish videos to your TikTok account",
            "Schedule videos for optimal posting times",
            "Apply captions and privacy settings programmatically",
            "Track post status (uploaded, processing, published)",
        ],
    }


@router.get("/oauth-url")
async def get_oauth_url():
    """Get the URL the user clicks to authorize Jarvis."""
    if not CLIENT_KEY:
        return {"error": "TIKTOK_CLIENT_KEY not set. See /api/tiktok-publish/setup"}

    params = {
        "client_key": CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": "jarvis-oauth",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return {
        "auth_url": f"{OAUTH_URL}?{query}",
        "instructions": "Open this URL in a browser. After approving, you'll be redirected back to Jarvis which will store the token automatically.",
    }


@router.get("/callback")
async def oauth_callback(code: str = "", state: str = "", error: str = ""):
    """OAuth redirect target - exchanges code for an access token."""
    if error:
        return {"error": error, "message": "TikTok denied the authorization."}
    if not code:
        return {"error": "No authorization code received"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_key": CLIENT_KEY,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        return {"error": "Token exchange failed", "detail": resp.text}

    token = resp.json()
    _save_token(token)
    return {
        "status": "connected",
        "message": "Jarvis is now connected to your TikTok account, sir.",
        "scope": token.get("scope"),
        "expires_in_hours": round(token.get("expires_in", 0) / 3600, 1),
    }


@router.get("/status")
async def connection_status():
    """Check whether TikTok is connected."""
    token = await _ensure_fresh_token()
    if not token:
        return {"connected": False, "message": "Not connected. Visit /api/tiktok-publish/oauth-url to connect."}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            USER_URL + "?fields=open_id,union_id,avatar_url,display_name",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
    if resp.status_code != 200:
        return {"connected": False, "error": resp.text}
    info = resp.json().get("data", {}).get("user", {})
    return {
        "connected": True,
        "display_name": info.get("display_name"),
        "avatar_url": info.get("avatar_url"),
    }


@router.post("/upload")
async def upload_video(req: VideoUploadRequest):
    """Upload and publish a video via TikTok's official API."""
    token = await _ensure_fresh_token()
    if not token:
        raise HTTPException(status_code=401, detail="TikTok not connected. Visit /api/tiktok-publish/oauth-url")

    payload = {
        "post_info": {
            "title": req.caption[:2200],
            "privacy_level": req.privacy,
            "disable_duet": req.disable_duet,
            "disable_comment": req.disable_comment,
            "disable_stitch": req.disable_stitch,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": req.video_url,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            POST_INIT_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {token['access_token']}",
                "Content-Type": "application/json",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json().get("data", {})
    return {
        "status": "submitted",
        "publish_id": data.get("publish_id"),
        "message": "Video submitted to TikTok. Use /status/{publish_id} to check progress.",
    }


@router.get("/post-status/{publish_id}")
async def post_status(publish_id: str):
    """Check status of a submitted video."""
    token = await _ensure_fresh_token()
    if not token:
        raise HTTPException(status_code=401, detail="TikTok not connected")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            POST_STATUS_URL,
            json={"publish_id": publish_id},
            headers={
                "Authorization": f"Bearer {token['access_token']}",
                "Content-Type": "application/json",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

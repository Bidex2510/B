"""Spotify API routes - music control and discovery."""

import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
ACCESS_TOKEN = os.getenv("SPOTIFY_ACCESS_TOKEN", "")
BASE_URL = "https://api.spotify.com/v1"


def _headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


def _check_auth():
    if not ACCESS_TOKEN:
        return {
            "status": "config_needed",
            "message": "Set SPOTIFY_ACCESS_TOKEN in your .env file.",
            "setup_steps": [
                "1. Go to https://developer.spotify.com/dashboard",
                "2. Create an app to get CLIENT_ID and CLIENT_SECRET",
                "3. Use OAuth2 to get an access token with these scopes:",
                "   user-read-playback-state, user-modify-playback-state,",
                "   user-read-currently-playing, playlist-read-private,",
                "   user-library-read, user-top-read",
            ],
        }
    return None


@router.get("/now-playing")
async def now_playing():
    """Get currently playing track."""
    err = _check_auth()
    if err:
        return err

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/me/player/currently-playing", headers=_headers())
    if resp.status_code == 204:
        return {"playing": False, "message": "Nothing is playing right now, sir."}
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to get playback")
    data = resp.json()
    track = data.get("item", {})
    return {
        "playing": data.get("is_playing", False),
        "track": track.get("name"),
        "artist": ", ".join(a["name"] for a in track.get("artists", [])),
        "album": track.get("album", {}).get("name"),
        "image": track.get("album", {}).get("images", [{}])[0].get("url"),
        "progress_ms": data.get("progress_ms"),
        "duration_ms": track.get("duration_ms"),
    }


@router.post("/play")
async def play():
    """Resume playback."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.put(f"{BASE_URL}/me/player/play", headers=_headers())
    return {"status": "playing", "message": "Music resumed, sir."}


@router.post("/pause")
async def pause():
    """Pause playback."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.put(f"{BASE_URL}/me/player/pause", headers=_headers())
    return {"status": "paused", "message": "Music paused, sir."}


@router.post("/next")
async def next_track():
    """Skip to next track."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/me/player/next", headers=_headers())
    return {"status": "skipped", "message": "Skipping to next track, sir."}


@router.post("/previous")
async def previous_track():
    """Go to previous track."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/me/player/previous", headers=_headers())
    return {"status": "previous", "message": "Going back to previous track, sir."}


@router.post("/volume/{level}")
async def set_volume(level: int):
    """Set volume (0-100)."""
    err = _check_auth()
    if err:
        return err
    level = max(0, min(100, level))
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{BASE_URL}/me/player/volume", headers=_headers(), params={"volume_percent": level}
        )
    return {"volume": level, "message": f"Volume set to {level}%, sir."}


@router.get("/search/{query}")
async def search_tracks(query: str, limit: int = 10):
    """Search for tracks on Spotify."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            headers=_headers(),
            params={"q": query, "type": "track", "limit": limit},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Search failed")
    tracks = []
    for t in resp.json().get("tracks", {}).get("items", []):
        tracks.append({
            "name": t["name"],
            "artist": ", ".join(a["name"] for a in t["artists"]),
            "album": t["album"]["name"],
            "uri": t["uri"],
            "image": t["album"]["images"][0]["url"] if t["album"]["images"] else None,
        })
    return {"tracks": tracks}


class PlayTrack(BaseModel):
    uri: str


@router.post("/play-track")
async def play_specific_track(track: PlayTrack):
    """Play a specific track by Spotify URI."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{BASE_URL}/me/player/play",
            headers=_headers(),
            json={"uris": [track.uri]},
        )
    return {"status": "playing", "message": "Now playing your requested track, sir."}


@router.get("/top-tracks")
async def top_tracks(time_range: str = "medium_term", limit: int = 20):
    """Get your top tracks. time_range: short_term, medium_term, long_term"""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/me/top/tracks",
            headers=_headers(),
            params={"time_range": time_range, "limit": limit},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to get top tracks")
    tracks = []
    for t in resp.json().get("items", []):
        tracks.append({
            "name": t["name"],
            "artist": ", ".join(a["name"] for a in t["artists"]),
            "uri": t["uri"],
        })
    return {"tracks": tracks}


@router.get("/playlists")
async def get_playlists(limit: int = 20):
    """Get user's playlists."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/me/playlists", headers=_headers(), params={"limit": limit}
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to get playlists")
    playlists = []
    for p in resp.json().get("items", []):
        playlists.append({
            "name": p["name"],
            "id": p["id"],
            "tracks": p["tracks"]["total"],
            "uri": p["uri"],
            "image": p["images"][0]["url"] if p.get("images") else None,
        })
    return {"playlists": playlists}

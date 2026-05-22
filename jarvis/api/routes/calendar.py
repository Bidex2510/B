"""Google Calendar integration - today's events, upcoming, create events.

Uses Google OAuth (same flow you used for Gmail).
"""

import os
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN", "") or os.getenv("GMAIL_ACCESS_TOKEN", "")
CALENDAR_API = "https://www.googleapis.com/calendar/v3/calendars/primary"


class EventCreate(BaseModel):
    title: str
    start: str  # ISO 8601: 2026-05-23T10:00:00
    end: str
    description: Optional[str] = ""
    location: Optional[str] = ""


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


@router.get("/setup")
async def setup_guide():
    return {
        "steps": [
            "1. Visit https://console.cloud.google.com/apis/credentials",
            "2. Enable 'Google Calendar API' for your project",
            "3. The same OAuth token you used for Gmail works - just add scope: https://www.googleapis.com/auth/calendar",
            "4. Or use the Google OAuth Playground (https://developers.google.com/oauthplayground) to get a fresh access token",
            "5. Add GOOGLE_ACCESS_TOKEN to .env (or reuse GMAIL_ACCESS_TOKEN if scoped properly)",
        ],
        "cost": "FREE - Google Calendar API is completely free for personal use",
    }


def _check():
    if not ACCESS_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_ACCESS_TOKEN not set. See /api/calendar/setup",
        )
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


@router.get("/today")
async def today_events():
    """Get all events scheduled for today."""
    headers = _check()
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{CALENDAR_API}/events",
            headers=headers,
            params={
                "timeMin": _iso(start),
                "timeMax": _iso(end),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    events = resp.json().get("items", [])
    return {
        "date": start.date().isoformat(),
        "count": len(events),
        "events": [
            {
                "title": e.get("summary", "(no title)"),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                "location": e.get("location"),
                "description": e.get("description"),
            }
            for e in events
        ],
    }


@router.get("/upcoming")
async def upcoming_events(days: int = 7):
    """Get upcoming events for the next N days."""
    headers = _check()
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{CALENDAR_API}/events",
            headers=headers,
            params={
                "timeMin": _iso(now),
                "timeMax": _iso(end),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 50,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    events = resp.json().get("items", [])
    return {
        "events": [
            {
                "title": e.get("summary", "(no title)"),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "location": e.get("location"),
            }
            for e in events
        ],
        "total": len(events),
        "range_days": days,
    }


@router.post("/create")
async def create_event(event: EventCreate):
    """Create a new calendar event."""
    headers = _check()

    body = {
        "summary": event.title,
        "description": event.description,
        "location": event.location,
        "start": {"dateTime": event.start},
        "end": {"dateTime": event.end},
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{CALENDAR_API}/events", headers=headers, json=body)
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    return {
        "id": data.get("id"),
        "link": data.get("htmlLink"),
        "message": f"Event '{event.title}' added to your calendar, sir.",
    }

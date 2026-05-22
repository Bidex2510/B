"""Daily life briefing - aggregates everything Jarvis knows.

Combines: weather, calendar, emails, missed calls, tasks, content for today, news.
"""

import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Request

router = APIRouter()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


async def _safe_get(client, url, timeout=8):
    try:
        resp = await client.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


@router.get("/morning")
async def morning_briefing(request: Request, city: str = "London"):
    """One-shot morning briefing - your day at a glance."""
    base = str(request.base_url).rstrip("/")

    async with httpx.AsyncClient() as client:
        weather = await _safe_get(client, f"{base}/api/weather/current/{city}")
        news = await _safe_get(client, f"{base}/api/news/top?count=3")
        calendar = await _safe_get(client, f"{base}/api/calendar/today")
        emails_priority = await _safe_get(client, f"{base}/api/email/priority")
        unread = await _safe_get(client, f"{base}/api/email/unread")
        missed = await _safe_get(client, f"{base}/api/phone/missed")
        tiktok_today = await _safe_get(client, f"{base}/api/tiktok/calendar")

    today_weekday = datetime.now().strftime("%A")

    # Pick today's TikTok slot from calendar
    todays_content = None
    if tiktok_today and "calendar" in tiktok_today:
        for entry in tiktok_today["calendar"]:
            if entry.get("day") == today_weekday:
                todays_content = entry
                break

    briefing = {
        "date": datetime.now().strftime("%A, %B %d, %Y"),
        "greeting": _time_based_greeting(),
        "weather": _format_weather(weather),
        "calendar": _format_calendar(calendar),
        "emails": _format_emails(emails_priority, unread),
        "missed_calls": _format_missed(missed),
        "news_headlines": _format_news(news),
        "tiktok_today": _format_tiktok(todays_content),
    }

    # AI-generated summary on top
    if ANTHROPIC_KEY:
        briefing["ai_summary"] = await _ai_summary(briefing)

    return briefing


@router.get("/evening")
async def evening_briefing(request: Request):
    """End-of-day recap - what got done, what's left."""
    base = str(request.base_url).rstrip("/")
    async with httpx.AsyncClient() as client:
        tasks = await _safe_get(client, f"{base}/api/system/tasks")
        calls = await _safe_get(client, f"{base}/api/phone/calls?limit=10")
        messages = await _safe_get(client, f"{base}/api/phone/messages?limit=10")
        unread = await _safe_get(client, f"{base}/api/email/unread")

    return {
        "date": datetime.now().strftime("%A, %B %d, %Y"),
        "greeting": "Good evening, sir. Here's your day recap.",
        "tasks_summary": tasks.get("report") if tasks else "No task data",
        "calls_today": len(calls.get("calls", [])) if calls else 0,
        "messages_today": len(messages.get("messages", [])) if messages else 0,
        "unread_emails": unread.get("unread", 0) if unread else 0,
        "tomorrow_prep": "Run /api/briefing/morning in the morning for tomorrow's plan.",
    }


def _time_based_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning, sir."
    if hour < 17:
        return "Good afternoon, sir."
    return "Good evening, sir."


def _format_weather(data):
    if not data:
        return "Weather unavailable."
    if data.get("mock_data"):
        w = data["mock_data"]
        return f"{w.get('city')}: {w.get('temperature')}°F, {w.get('description')} (configure OPENWEATHER_API_KEY for live data)"
    return f"{data.get('city', '?')}: {data.get('temperature')}°F, {data.get('description', '')}. Feels like {data.get('feels_like', '?')}°F."


def _format_calendar(data):
    if not data:
        return "Calendar not connected."
    events = data.get("events", [])
    if not events:
        return "No events scheduled today."
    lines = [f"You have {len(events)} event(s) today:"]
    for e in events[:5]:
        lines.append(f"  • {e.get('start', '')[:16]} — {e.get('title', '(no title)')}")
    return "\n".join(lines)


def _format_emails(priority_data, unread_data):
    unread = unread_data.get("unread", 0) if unread_data else 0
    msg = f"{unread} unread email(s)."
    if priority_data and priority_data.get("priority"):
        msg += f" {len(priority_data['priority'])} look urgent:"
        for e in priority_data["priority"][:3]:
            msg += f"\n  • {e.get('from', '?')}: {e.get('subject', '(no subject)')}"
    return msg


def _format_missed(data):
    if not data:
        return "Phone not connected."
    missed = data.get("missed", [])
    if not missed:
        return "No missed calls."
    lines = [f"{len(missed)} missed call(s):"]
    for c in missed[:3]:
        lines.append(f"  • From {c.get('from', '?')} at {c.get('started', '?')}")
    return "\n".join(lines)


def _format_news(data):
    if not data:
        return []
    articles = data.get("articles") or data.get("mock_data") or []
    return [f"{a.get('title', '?')} ({a.get('source', '?')})" for a in articles[:3]]


def _format_tiktok(entry):
    if not entry:
        return "No content scheduled."
    return f"{entry.get('time', '?')} — {entry.get('category', '?')}: {entry.get('idea', '')}"


async def _ai_summary(briefing: dict) -> str:
    """Have Claude write a 3-sentence executive summary."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=(
                "You are Jarvis delivering a morning briefing. "
                "Give a 3-4 sentence executive summary of the day. "
                "Lead with what matters most. Address user as 'sir'. Be crisp, like a butler."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Date: {briefing['date']}\n"
                    f"Weather: {briefing['weather']}\n"
                    f"Calendar: {briefing['calendar']}\n"
                    f"Emails: {briefing['emails']}\n"
                    f"Missed calls: {briefing['missed_calls']}\n"
                    f"News: {', '.join(briefing['news_headlines'])}\n"
                    f"Content for today: {briefing['tiktok_today']}\n\n"
                    f"Write the briefing."
                ),
            }],
        )
        return msg.content[0].text
    except Exception as e:
        return f"(AI summary unavailable: {e})"

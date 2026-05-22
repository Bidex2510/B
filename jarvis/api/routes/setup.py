"""Setup status - one endpoint to see what's connected and what's not."""

import os
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/status")
async def setup_status(request: Request):
    """Show which integrations are connected. Run this first to see what to do next."""
    base = str(request.base_url).rstrip("/")

    checks = [
        {
            "step": 1,
            "name": "Anthropic AI",
            "env": "ANTHROPIC_API_KEY",
            "connected": bool(os.getenv("ANTHROPIC_API_KEY")),
            "required": True,
            "get_key": "https://console.anthropic.com",
            "why": "Powers all AI features: scripts, briefings, email drafts",
        },
        {
            "step": 2,
            "name": "Telegram Bot",
            "env": "TELEGRAM_BOT_TOKEN",
            "connected": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "required": True,
            "get_key": "Talk to @BotFather on Telegram, send /newbot",
            "why": "Phone control - your remote for Jarvis. FREE.",
            "setup_url": f"{base}/api/telegram/setup",
        },
        {
            "step": 3,
            "name": "TikTok Publisher",
            "env": "TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET",
            "connected": bool(os.getenv("TIKTOK_CLIENT_KEY") and os.getenv("TIKTOK_CLIENT_SECRET")),
            "required": False,
            "get_key": "https://developers.tiktok.com/",
            "why": "Auto-post videos to your TikTok account. FREE.",
            "setup_url": f"{base}/api/tiktok-publish/setup",
        },
        {
            "step": 4,
            "name": "Gmail",
            "env": "GMAIL_ACCESS_TOKEN",
            "connected": bool(os.getenv("GMAIL_ACCESS_TOKEN")),
            "required": False,
            "get_key": "https://developers.google.com/oauthplayground",
            "why": "AI email drafting, inbox digest, priority flagging. FREE.",
        },
        {
            "step": 5,
            "name": "Google Calendar",
            "env": "GOOGLE_ACCESS_TOKEN (or reuse Gmail token)",
            "connected": bool(os.getenv("GOOGLE_ACCESS_TOKEN") or os.getenv("GMAIL_ACCESS_TOKEN")),
            "required": False,
            "get_key": "https://developers.google.com/oauthplayground",
            "why": "Today's events in morning briefing. FREE.",
            "setup_url": f"{base}/api/calendar/setup",
        },
    ]

    connected_count = sum(1 for c in checks if c["connected"])
    required_missing = [c for c in checks if c["required"] and not c["connected"]]

    next_step = None
    for c in checks:
        if not c["connected"]:
            next_step = c
            break

    return {
        "summary": f"{connected_count} of {len(checks)} integrations connected",
        "all_required_connected": len(required_missing) == 0,
        "next_step": {
            "step": next_step["step"],
            "name": next_step["name"],
            "what_to_do": f"Get your key at: {next_step['get_key']}",
            "then": f"Add {next_step['env']} to your .env (or Render dashboard) and restart",
        } if next_step else None,
        "checks": checks,
        "deployment_url": base,
        "tip": "Once deployed, set Telegram webhook: POST /api/telegram/set-webhook?base_url=" + base,
    }

"""Telegram bot webhook - control Jarvis from your phone for FREE."""

import os
import httpx
from fastapi import APIRouter, Request

router = APIRouter()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def _telegram_url(method: str) -> str:
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


async def _send(chat_id: int, text: str):
    if not BOT_TOKEN:
        return
    # Trim to Telegram's 4096 char limit
    if len(text) > 4000:
        text = text[:3997] + "..."
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            _telegram_url("sendMessage"),
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram messages and route them to Jarvis."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    message = body.get("message") or body.get("edited_message", {})
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return {"ok": True}

    response = await _route(text, request)
    await _send(chat_id, response)
    return {"ok": True}


async def _route(text: str, request: Request) -> str:
    lower = text.lower()

    if lower in ("/start", "/help"):
        return (
            "🤖 *JARVIS - Your Life Manager*\n\n"
            "*Life Manager:*\n"
            "  /briefing — full morning briefing\n"
            "  /evening — evening recap\n"
            "  /emails — AI inbox digest\n"
            "  /calls — missed call log\n"
            "  /events — today's calendar\n\n"
            "*TikTok Content:*\n"
            "  /ideas — video ideas (all categories)\n"
            "  /sports — sports video ideas\n"
            "  /wholesome — feel-good video ideas\n"
            "  /aiideas — AI/tech video ideas\n"
            "  /calendar — weekly posting schedule\n"
            "  /trending — what's hot right now\n"
            "  /script [topic] — generate a video script\n"
            "  /caption [topic] — get captions + hashtags\n\n"
            "*General:*\n"
            "  /status — Jarvis system status\n"
            "  /chat [message] — chat with Jarvis AI\n\n"
            "Or just type anything to chat with Jarvis!"
        )

    if lower == "/ideas":
        return await _tiktok_ideas("all", request)

    if lower == "/sports":
        return await _tiktok_ideas("sports", request)

    if lower == "/wholesome":
        return await _tiktok_ideas("wholesome", request)

    if lower == "/aiideas":
        return await _tiktok_ideas("ai", request)

    if lower == "/calendar":
        return await _tiktok_calendar(request)

    if lower == "/trending":
        return await _tiktok_trending(request)

    if lower.startswith("/script"):
        topic = text[7:].strip() or "interesting viral content"
        return await _tiktok_script(topic, request)

    if lower.startswith("/caption"):
        topic = text[8:].strip() or "my content"
        return await _tiktok_caption(topic, request)

    if lower == "/status":
        return (
            "✅ *JARVIS Status*\n\n"
            "All systems operational, sir.\n"
            "• TikTok Manager: Online\n"
            "• AI Brain: Online\n"
            "• Telegram Bot: Connected\n"
            "• Content Calendar: Ready"
        )

    if lower in ("/briefing", "/morning"):
        return await _fetch_text(
            request, "/api/briefing/morning?city=London",
            lambda d: (
                f"☀️ *Morning Briefing*\n\n"
                f"{d.get('ai_summary', '')}\n\n"
                f"📅 *Calendar:* {d.get('calendar', '')}\n\n"
                f"📧 *Emails:* {d.get('emails', '')}\n\n"
                f"📞 *Calls:* {d.get('missed_calls', '')}\n\n"
                f"🎬 *TikTok Today:* {d.get('tiktok_today', '')}"
            )
        )

    if lower == "/evening":
        return await _fetch_text(
            request, "/api/briefing/evening",
            lambda d: (
                f"🌙 *Evening Recap*\n\n"
                f"📋 {d.get('tasks_summary', '')}\n\n"
                f"📞 Calls today: {d.get('calls_today', 0)}\n"
                f"💬 Messages: {d.get('messages_today', 0)}\n"
                f"📧 Unread: {d.get('unread_emails', 0)}"
            )
        )

    if lower == "/emails":
        return await _fetch_text(
            request, "/api/email/digest",
            lambda d: f"📧 *Inbox Digest* ({d.get('count', 0)} emails)\n\n{d.get('digest', d.get('mock_digest', ''))}"
        )

    if lower == "/calls":
        return await _fetch_text(
            request, "/api/phone/missed",
            lambda d: _format_calls_for_telegram(d)
        )

    if lower == "/events":
        return await _fetch_text(
            request, "/api/calendar/today",
            lambda d: _format_events_for_telegram(d)
        )

    if lower.startswith("/chat "):
        user_msg = text[6:].strip()
        jarvis = request.app.state.jarvis
        reply = jarvis.chat(user_msg)
        return f"🤖 *Jarvis:*\n{reply}"

    # Default: pass through Jarvis brain
    jarvis = request.app.state.jarvis
    reply = jarvis.chat(text)
    return f"🤖 {reply}"


async def _tiktok_ideas(category: str, request: Request) -> str:
    try:
        base = str(request.base_url).rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/api/tiktok/ideas?category={category}&count=4")
            data = resp.json()

        if category == "all":
            msg = "🎬 *TikTok Video Ideas:*\n\n"
            for cat, ideas in data.get("ideas", {}).items():
                emoji = {"sports": "⚽", "wholesome": "💝", "ai": "🤖"}.get(cat, "•")
                msg += f"{emoji} *{cat.upper()}:*\n"
                for idea in ideas:
                    msg += f"  • {idea}\n"
                msg += "\n"
        else:
            emoji = {"sports": "⚽", "wholesome": "💝", "ai": "🤖"}.get(category, "🎬")
            msg = f"{emoji} *{category.upper()} Video Ideas:*\n\n"
            for idea in data.get("ideas", []):
                msg += f"• {idea}\n"

        msg += "\n_Use /script [topic] to generate a full script!_"
        return msg
    except Exception as e:
        return f"Could not fetch ideas: {e}"


async def _tiktok_calendar(request: Request) -> str:
    try:
        base = str(request.base_url).rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/api/tiktok/calendar")
            data = resp.json()

        msg = "📅 *Weekly TikTok Calendar:*\n\n"
        for entry in data.get("calendar", []):
            emoji = {"AI": "🤖", "Sports": "⚽", "Wholesome": "💝"}.get(entry["category"], "📹")
            msg += f"*{entry['day']}* ({entry['time']})\n{emoji} {entry['category']}: {entry['idea']}\n\n"
        msg += f"💡 {data.get('strategy', '')}"
        return msg
    except Exception as e:
        return f"Could not fetch calendar: {e}"


async def _tiktok_trending(request: Request) -> str:
    try:
        base = str(request.base_url).rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/api/tiktok/trending")
            data = resp.json()

        msg = "🔥 *Trending Topics:*\n\n"
        for cat, emoji in [("sports", "⚽"), ("wholesome", "💝"), ("ai", "🤖")]:
            msg += f"{emoji} *{cat.upper()}:*\n"
            for topic in data.get(cat, [])[:3]:
                msg += f"  • {topic}\n"
            msg += "\n"
        msg += f"💡 _{data.get('hook_tip', '')}_"
        return msg
    except Exception as e:
        return f"Could not fetch trends: {e}"


async def _tiktok_script(topic: str, request: Request) -> str:
    try:
        base = str(request.base_url).rstrip("/")
        # Detect category from topic
        category = "ai"
        tl = topic.lower()
        if any(w in tl for w in ["sport", "game", "athlete", "soccer", "nba", "nfl"]):
            category = "sports"
        elif any(w in tl for w in ["wholesome", "kind", "dog", "family", "heart"]):
            category = "wholesome"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base}/api/tiktok/script",
                json={"category": category, "topic": topic, "duration": 60},
            )
            data = resp.json()

        if data.get("script"):
            return f"🎬 *Script for: {topic}*\n\n{data['script']}"

        sample = data.get("sample_script", {})
        return (
            f"🎬 *Sample Script for: {topic}*\n\n"
            f"*HOOK:* {sample.get('hook', '')}\n\n"
            f"*CONTENT:*\n{sample.get('content', '')}\n\n"
            f"*CTA:* {sample.get('cta', '')}\n\n"
            f"*CAPTION:* {sample.get('caption', '')}\n\n"
            f"_{sample.get('note', '')}_"
        )
    except Exception as e:
        return f"Could not generate script: {e}"


async def _fetch_text(request: Request, path: str, formatter) -> str:
    try:
        base = str(request.base_url).rstrip("/")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{base}{path}")
            data = resp.json()
        if isinstance(data, dict) and data.get("detail"):
            return f"⚠️ {data['detail']}"
        return formatter(data)
    except Exception as e:
        return f"Could not fetch: {e}"


def _format_calls_for_telegram(d: dict) -> str:
    missed = d.get("missed", [])
    if not missed:
        return "📞 No missed calls, sir."
    msg = f"📵 *{len(missed)} Missed Calls:*\n\n"
    for c in missed[:5]:
        msg += f"• From `{c.get('from', '?')}`\n  {c.get('started', '?')}\n\n"
    return msg


def _format_events_for_telegram(d: dict) -> str:
    events = d.get("events", [])
    if not events:
        return f"📅 No events today ({d.get('date', '')})."
    msg = f"📅 *Today — {d.get('date', '')}*\n{len(events)} event(s):\n\n"
    for e in events[:10]:
        start = (e.get("start") or "")[:16]
        msg += f"• {start} — {e.get('title', '')}\n"
        if e.get("location"):
            msg += f"  📍 {e['location']}\n"
    return msg


async def _tiktok_caption(topic: str, request: Request) -> str:
    try:
        base = str(request.base_url).rstrip("/")
        category = "ai"
        tl = topic.lower()
        if any(w in tl for w in ["sport", "game", "athlete"]):
            category = "sports"
        elif any(w in tl for w in ["wholesome", "kind", "dog", "family"]):
            category = "wholesome"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{base}/api/tiktok/caption",
                json={"category": category, "topic": topic},
            )
            data = resp.json()

        captions = data.get("captions", [])[:3]
        msg = f"📝 *Captions for: {topic}*\n\n"
        for i, cap in enumerate(captions, 1):
            msg += f"Option {i}:\n`{cap}`\n\n"
        msg += f"💡 _{data.get('tip', '')}_"
        return msg
    except Exception as e:
        return f"Could not generate caption: {e}"


@router.get("/setup")
async def telegram_setup_info():
    """Step-by-step instructions for setting up the free Telegram bot."""
    return {
        "cost": "100% FREE - Telegram bots are completely free forever",
        "steps": [
            "1. Open Telegram and search for @BotFather",
            "2. Send /newbot and follow the prompts",
            "3. Give your bot a name (e.g. 'My Jarvis') and username (e.g. 'myjarvis_bot')",
            "4. Copy the API token BotFather gives you",
            "5. Add TELEGRAM_BOT_TOKEN=your_token to your .env file",
            "6. Deploy Jarvis to a public URL (free: Render.com or Railway.app)",
            "7. Set the webhook by calling: POST /api/telegram/set-webhook?base_url=https://your-url.com",
            "8. Open your bot in Telegram and send /start",
            "9. You can now control Jarvis from your phone anywhere!",
        ],
        "free_hosting": [
            "Render.com - free tier available, auto-deploys from GitHub",
            "Railway.app - free tier with $5 credit monthly",
            "Fly.io - generous free tier",
        ],
    }


@router.post("/set-webhook")
async def set_webhook(base_url: str):
    """Register this deployed server as the Telegram webhook endpoint."""
    if not BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment"}

    webhook_url = f"{base_url.rstrip('/')}/api/telegram/webhook"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _telegram_url("setWebhook"),
            json={"url": webhook_url, "allowed_updates": ["message"]},
        )
    result = resp.json()
    if result.get("ok"):
        return {"success": True, "webhook": webhook_url, "message": "Webhook set! Message your bot to test it."}
    return {"success": False, "error": result}

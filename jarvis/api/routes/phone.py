"""Phone & SMS via Twilio - make calls, send SMS, view logs.

Twilio free trial gives $15 credit. Calls ~$0.013/min, SMS ~$0.008/msg.
Sign up: https://www.twilio.com/try-twilio
"""

import os
import base64
import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

BASE_URL = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}"


def _auth_header():
    if not ACCOUNT_SID or not AUTH_TOKEN:
        return None
    token = base64.b64encode(f"{ACCOUNT_SID}:{AUTH_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _check_config():
    if not ACCOUNT_SID or not AUTH_TOKEN or not FROM_NUMBER:
        raise HTTPException(
            status_code=400,
            detail="Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in .env",
        )


class CallRequest(BaseModel):
    to: str  # E.164 format: +14155551234
    say: Optional[str] = None  # text to read out loud via TTS
    url: Optional[str] = None  # TwiML URL for advanced call flow


class SmsRequest(BaseModel):
    to: str
    body: str


@router.get("/setup")
async def setup_guide():
    """How to connect Twilio for phone/SMS."""
    return {
        "steps": [
            "1. Sign up at https://www.twilio.com/try-twilio (free $15 trial credit)",
            "2. From the console, copy your Account SID and Auth Token",
            "3. Buy a phone number from the Phone Numbers section (~$1/month, covered by trial credit)",
            "4. Add to .env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER (E.164 format)",
            "5. Restart Jarvis. You can now make calls and send SMS through /api/phone/*",
        ],
        "pricing": {
            "phone_number": "$1.15/month",
            "outbound_calls": "~$0.013 per minute (US)",
            "outbound_sms": "~$0.008 per message (US)",
            "inbound_calls": "~$0.0085 per minute",
        },
        "free_trial": "$15 credit = ~1100 SMS or ~1100 minutes of calls",
    }


@router.post("/call")
async def make_call(req: CallRequest):
    """Initiate an outbound phone call. Optionally have Jarvis speak text."""
    _check_config()

    if req.say:
        from urllib.parse import quote
        twiml = '<Response><Say voice="Polly.Brian">' + req.say + '</Say></Response>'
        url = "http://twimlets.com/echo?Twiml=" + quote(twiml)
    elif req.url:
        url = req.url
    else:
        url = "http://demo.twilio.com/docs/voice.xml"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/Calls.json",
            headers=_auth_header(),
            data={"To": req.to, "From": FROM_NUMBER, "Url": url},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    return {
        "sid": data.get("sid"),
        "status": data.get("status"),
        "to": data.get("to"),
        "from": data.get("from"),
        "message": f"Call initiated to {req.to}, sir.",
    }


@router.post("/sms")
async def send_sms(req: SmsRequest):
    """Send an SMS."""
    _check_config()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/Messages.json",
            headers=_auth_header(),
            data={"To": req.to, "From": FROM_NUMBER, "Body": req.body},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    return {
        "sid": data.get("sid"),
        "status": data.get("status"),
        "to": data.get("to"),
        "message": f"SMS sent to {req.to}, sir.",
    }


@router.get("/calls")
async def call_logs(limit: int = 20):
    """List recent calls."""
    _check_config()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/Calls.json?PageSize={limit}",
            headers=_auth_header(),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    calls = resp.json().get("calls", [])
    return {
        "calls": [
            {
                "from": c.get("from"),
                "to": c.get("to"),
                "status": c.get("status"),
                "duration_sec": c.get("duration"),
                "started": c.get("start_time"),
                "direction": c.get("direction"),
            }
            for c in calls
        ],
        "total": len(calls),
    }


@router.get("/messages")
async def message_logs(limit: int = 20):
    """List recent SMS."""
    _check_config()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/Messages.json?PageSize={limit}",
            headers=_auth_header(),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    msgs = resp.json().get("messages", [])
    return {
        "messages": [
            {
                "from": m.get("from"),
                "to": m.get("to"),
                "body": m.get("body"),
                "status": m.get("status"),
                "direction": m.get("direction"),
                "sent": m.get("date_sent"),
            }
            for m in msgs
        ],
        "total": len(msgs),
    }


@router.get("/missed")
async def missed_calls(limit: int = 10):
    """Show missed/unanswered calls."""
    _check_config()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/Calls.json?PageSize=50",
            headers=_auth_header(),
        )
    calls = resp.json().get("calls", [])
    missed = [
        {
            "from": c.get("from"),
            "to": c.get("to"),
            "status": c.get("status"),
            "started": c.get("start_time"),
        }
        for c in calls
        if c.get("direction", "").startswith("inbound") and c.get("status") in ("no-answer", "busy", "failed")
    ]
    return {"missed": missed[:limit], "total": len(missed)}


@router.post("/voice-webhook")
async def voice_webhook(request: Request):
    """Twilio voice webhook - handles incoming calls. Set this as your number's voice URL.

    By default, sends incoming calls to voicemail with AI transcription.
    """
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Brian">Hello. You've reached Jarvis. Please leave a message after the tone, and your message will be transcribed.</Say>
    <Record maxLength="60" transcribe="true" transcribeCallback="/api/phone/transcription-webhook"/>
    <Say voice="Polly.Brian">No message received. Goodbye.</Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.post("/transcription-webhook")
async def transcription_webhook(request: Request):
    """Receives voicemail transcriptions from Twilio."""
    form = await request.form()
    transcription = form.get("TranscriptionText", "")
    caller = form.get("From", "unknown")
    # Store or relay (could send via Telegram, email, etc.)
    return {"received": True, "from": caller, "transcription": transcription}

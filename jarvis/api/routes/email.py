"""Email/Gmail API routes."""

import os
import base64
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Gmail API via Google OAuth
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
ACCESS_TOKEN = os.getenv("GMAIL_ACCESS_TOKEN", "")


class EmailCompose(BaseModel):
    to: str
    subject: str
    body: str


class EmailSearch(BaseModel):
    query: str
    max_results: int = 10


@router.get("/inbox")
async def get_inbox(max_results: int = 20):
    """Get recent emails from inbox."""
    if not ACCESS_TOKEN:
        return {
            "status": "config_needed",
            "message": "Set GMAIL_ACCESS_TOKEN in your .env file. Follow Google OAuth2 setup for Gmail API.",
            "setup_url": "https://developers.google.com/gmail/api/quickstart/python",
            "mock_data": _mock_inbox(),
        }

    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/messages",
            headers=headers,
            params={"maxResults": max_results, "labelIds": "INBOX"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch inbox")

    messages = resp.json().get("messages", [])
    results = []
    async with httpx.AsyncClient() as client:
        for msg in messages[:max_results]:
            detail = await client.get(
                f"{GMAIL_API}/messages/{msg['id']}",
                headers=headers,
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            )
            if detail.status_code == 200:
                data = detail.json()
                headers_list = data.get("payload", {}).get("headers", [])
                email_info = {"id": msg["id"], "snippet": data.get("snippet", "")}
                for h in headers_list:
                    email_info[h["name"].lower()] = h["value"]
                results.append(email_info)

    return {"emails": results, "total": len(results)}


@router.post("/send")
async def send_email(email: EmailCompose):
    """Send an email via Gmail."""
    if not ACCESS_TOKEN:
        return {
            "status": "config_needed",
            "message": "Set GMAIL_ACCESS_TOKEN to send emails.",
        }

    raw_message = f"To: {email.to}\nSubject: {email.subject}\nContent-Type: text/plain; charset=utf-8\n\n{email.body}"
    encoded = base64.urlsafe_b64encode(raw_message.encode()).decode()

    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/send",
            headers=headers,
            json={"raw": encoded},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to send email")
    return {"status": "sent", "message": f"Email sent to {email.to}, sir."}


@router.post("/search")
async def search_emails(search: EmailSearch):
    """Search emails by query."""
    if not ACCESS_TOKEN:
        return {"status": "config_needed", "message": "Set GMAIL_ACCESS_TOKEN to search emails."}

    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/messages",
            headers=headers,
            params={"q": search.query, "maxResults": search.max_results},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Search failed")
    return resp.json()


@router.get("/unread")
async def unread_count():
    """Get unread email count."""
    if not ACCESS_TOKEN:
        return {"status": "config_needed", "unread": 0, "mock": True}

    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/messages",
            headers=headers,
            params={"q": "is:unread", "maxResults": 1},
        )
    if resp.status_code == 200:
        total = resp.json().get("resultSizeEstimate", 0)
        return {"unread": total}
    return {"unread": 0}


def _mock_inbox():
    return [
        {"from": "professor@university.edu", "subject": "Assignment 3 Due Friday", "snippet": "Reminder: your essay is due..."},
        {"from": "studygroup@gmail.com", "subject": "Study session tonight", "snippet": "Meeting at the library at 7pm..."},
        {"from": "campus@university.edu", "subject": "Career Fair Next Week", "snippet": "Don't miss the spring career fair..."},
    ]


# ============== AI-POWERED EMAIL FEATURES ==============

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


class DraftReplyRequest(BaseModel):
    email_id: str
    tone: str = "professional"  # professional, casual, brief, warm
    instructions: str = ""


@router.get("/digest")
async def inbox_digest(max_emails: int = 10):
    """AI-powered summary of your recent emails - what needs attention."""
    if not ACCESS_TOKEN:
        return {
            "status": "config_needed",
            "message": "Connect Gmail to enable AI digest",
            "mock_digest": "📧 3 emails need attention: 1 from your professor (urgent assignment), 1 study session tonight, 1 career fair invite.",
        }

    inbox = await get_inbox(max_results=max_emails)
    emails = inbox.get("emails", [])
    if not emails:
        return {"digest": "Inbox is clear, sir.", "count": 0}

    if not ANTHROPIC_KEY:
        # Simple non-AI digest
        lines = []
        for e in emails[:10]:
            lines.append(f"• From {e.get('from', '?')}: {e.get('subject', '(no subject)')}")
        return {"digest": "\n".join(lines), "count": len(emails)}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        email_text = "\n\n".join(
            f"From: {e.get('from', '?')}\nSubject: {e.get('subject', '?')}\nPreview: {e.get('snippet', '')}"
            for e in emails[:max_emails]
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system="You are Jarvis. Give a crisp, prioritized briefing of these emails. Group by urgency. Flag what needs a reply today. Keep it under 150 words. Address the user as 'sir'.",
            messages=[{"role": "user", "content": f"Summarize these emails:\n\n{email_text}"}],
        )
        return {"digest": msg.content[0].text, "count": len(emails)}
    except Exception as e:
        return {"digest": f"AI digest failed: {e}", "raw_emails": emails}


@router.post("/draft-reply")
async def draft_reply(req: DraftReplyRequest):
    """Generate an AI-drafted reply to a specific email."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    if not ANTHROPIC_KEY:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY required for AI drafting")

    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{GMAIL_API}/messages/{req.email_id}",
            headers=headers,
            params={"format": "full"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch email")
    data = resp.json()

    # Extract subject and body
    subject = ""
    sender = ""
    for h in data.get("payload", {}).get("headers", []):
        if h["name"] == "Subject":
            subject = h["value"]
        if h["name"] == "From":
            sender = h["value"]

    snippet = data.get("snippet", "")

    try:
        import anthropic
        client_ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        msg = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=(
                f"You are drafting an email reply in a {req.tone} tone. "
                "Be authentic, not robotic. Match the formality of the original. "
                "Don't include subject line or signature placeholders. Just the reply body."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Draft a reply to this email:\n\n"
                    f"From: {sender}\nSubject: {subject}\nMessage: {snippet}\n\n"
                    f"Additional instructions: {req.instructions or 'Reply appropriately.'}"
                ),
            }],
        )
        return {
            "draft": msg.content[0].text,
            "reply_to": sender,
            "original_subject": subject,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority")
async def priority_emails(max_results: int = 20):
    """Flag emails that look important (boss, urgent keywords, replies needed)."""
    inbox = await get_inbox(max_results=max_results)
    emails = inbox.get("emails", [])
    if not emails:
        return {"priority": [], "count": 0}

    urgent_keywords = ["urgent", "asap", "today", "tomorrow", "due", "deadline", "important", "action required", "please respond"]
    priority = []
    for e in emails:
        score = 0
        text = (e.get("subject", "") + " " + e.get("snippet", "")).lower()
        for kw in urgent_keywords:
            if kw in text:
                score += 1
        if e.get("subject", "").lower().startswith("re:"):
            score += 1
        if score > 0:
            priority.append({**e, "priority_score": score})

    priority.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"priority": priority[:10], "count": len(priority)}

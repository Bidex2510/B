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

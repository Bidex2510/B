"""Class note-taking routes - AI-powered lecture notes from live transcription."""

import os
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NOTES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "notes"


class TranscriptRequest(BaseModel):
    transcript: str
    subject: str = "General"
    session_name: str = ""


class SaveNoteRequest(BaseModel):
    subject: str
    session_name: str
    transcript: str
    notes: str
    summary: str
    key_points: list[str]
    action_items: list[str]


@router.post("/generate")
async def generate_notes(req: TranscriptRequest):
    """Send lecture transcript to Claude and get back structured notes."""
    if not req.transcript.strip():
        return {"status": "error", "message": "Transcript is empty."}

    if not API_KEY:
        return {
            "status": "config_needed",
            "message": "Set ANTHROPIC_API_KEY in your .env file to enable AI note generation.",
            "notes": _fallback_notes(req.transcript),
            "summary": "AI summarization unavailable — set ANTHROPIC_API_KEY.",
            "key_points": [],
            "action_items": [],
        }

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=API_KEY)

        system_prompt = (
            "You are an expert academic note-taker. Given a raw lecture transcript, "
            "produce clean, well-structured study notes. Be concise but comprehensive."
        )

        user_prompt = f"""Subject: {req.subject or "General"}
Session: {req.session_name or "Unnamed Session"}

Raw transcript:
\"\"\"
{req.transcript}
\"\"\"

Return a JSON object with exactly these keys:
- "notes": A markdown string with organized, hierarchical notes using headers, bullet points, and emphasis.
- "summary": A 2-3 sentence summary of what was covered.
- "key_points": A JSON array of the 5-8 most important concepts or facts.
- "action_items": A JSON array of homework, readings, or follow-up tasks mentioned.

Return ONLY the JSON object, no other text."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()

        data = json.loads(text)
        return {
            "status": "ok",
            "notes": data.get("notes", ""),
            "summary": data.get("summary", ""),
            "key_points": data.get("key_points", []),
            "action_items": data.get("action_items", []),
        }

    except json.JSONDecodeError:
        return {"status": "error", "message": "Claude returned unexpected format. Try again."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/save")
async def save_notes(req: SaveNoteRequest):
    """Persist a notes session to disk as JSON."""
    try:
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_subject = "".join(c if c.isalnum() or c in "-_ " else "_" for c in req.subject)
        filename = f"{safe_subject}_{timestamp}.json"

        data = {
            "subject": req.subject,
            "session_name": req.session_name,
            "timestamp": datetime.now().isoformat(),
            "transcript": req.transcript,
            "notes": req.notes,
            "summary": req.summary,
            "key_points": req.key_points,
            "action_items": req.action_items,
        }
        (NOTES_DIR / filename).write_text(json.dumps(data, indent=2))
        return {"status": "ok", "filename": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/sessions")
async def list_sessions():
    """List all saved note sessions."""
    try:
        if not NOTES_DIR.exists():
            return {"sessions": []}
        sessions = []
        for f in sorted(NOTES_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                sessions.append({
                    "filename": f.name,
                    "subject": data.get("subject", ""),
                    "session_name": data.get("session_name", ""),
                    "timestamp": data.get("timestamp", ""),
                    "summary": data.get("summary", ""),
                })
            except Exception:
                pass
        return {"sessions": sessions}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/sessions/{filename}")
async def get_session(filename: str):
    """Load a saved notes session by filename."""
    # Sanitize to prevent path traversal
    safe_name = Path(filename).name
    path = NOTES_DIR / safe_name
    if not path.exists() or not safe_name.endswith(".json"):
        return {"status": "error", "message": "Session not found."}
    try:
        return {"status": "ok", "data": json.loads(path.read_text())}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _fallback_notes(transcript: str) -> str:
    lines = [ln.strip() for ln in transcript.split(".") if ln.strip()]
    bullets = "\n".join(f"- {ln}." for ln in lines[:20])
    return f"## Notes\n\n{bullets}\n\n*(Configure ANTHROPIC_API_KEY for AI-organized notes)*"

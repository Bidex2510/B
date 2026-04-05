"""Study tools for college students - Pomodoro, GPA, dictionary, flashcards, schedule."""

import time
import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# === POMODORO TIMER ===

_pomodoro_state = {
    "active": False,
    "type": None,  # "work" or "break"
    "start_time": None,
    "duration_minutes": 25,
    "sessions_completed": 0,
}


class PomodoroConfig(BaseModel):
    work_minutes: int = 25
    break_minutes: int = 5
    long_break_minutes: int = 15


@router.post("/pomodoro/start")
async def start_pomodoro(config: PomodoroConfig = PomodoroConfig()):
    """Start a Pomodoro study session."""
    _pomodoro_state["active"] = True
    _pomodoro_state["type"] = "work"
    _pomodoro_state["start_time"] = time.time()
    _pomodoro_state["duration_minutes"] = config.work_minutes
    return {
        "status": "started",
        "type": "work",
        "duration": config.work_minutes,
        "message": f"Pomodoro started, sir. {config.work_minutes} minutes of focused study. You've got this!",
    }


@router.get("/pomodoro/status")
async def pomodoro_status():
    """Check Pomodoro timer status."""
    if not _pomodoro_state["active"]:
        return {
            "active": False,
            "sessions_completed": _pomodoro_state["sessions_completed"],
            "message": "No active Pomodoro session, sir.",
        }
    elapsed = (time.time() - _pomodoro_state["start_time"]) / 60
    remaining = max(0, _pomodoro_state["duration_minutes"] - elapsed)
    done = remaining == 0
    if done:
        _pomodoro_state["sessions_completed"] += 1
        _pomodoro_state["active"] = False
    return {
        "active": not done,
        "type": _pomodoro_state["type"],
        "elapsed_minutes": round(elapsed, 1),
        "remaining_minutes": round(remaining, 1),
        "sessions_completed": _pomodoro_state["sessions_completed"],
        "message": "Time's up! Take a break, sir." if done else f"{round(remaining)} minutes remaining. Stay focused!",
    }


@router.post("/pomodoro/stop")
async def stop_pomodoro():
    """Stop the current Pomodoro session."""
    _pomodoro_state["active"] = False
    return {"status": "stopped", "message": "Pomodoro stopped, sir."}


# === GPA CALCULATOR ===

GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}


class Course(BaseModel):
    name: str
    grade: str
    credits: int


class GPARequest(BaseModel):
    courses: list[Course]
    cumulative_gpa: float = 0.0
    cumulative_credits: int = 0


@router.post("/gpa/calculate")
async def calculate_gpa(req: GPARequest):
    """Calculate GPA from courses."""
    total_points = 0
    total_credits = 0
    course_results = []

    for c in req.courses:
        grade_upper = c.grade.upper()
        points = GRADE_POINTS.get(grade_upper, 0)
        total_points += points * c.credits
        total_credits += c.credits
        course_results.append({
            "name": c.name,
            "grade": grade_upper,
            "credits": c.credits,
            "grade_points": points,
            "quality_points": points * c.credits,
        })

    semester_gpa = total_points / total_credits if total_credits > 0 else 0

    cumulative_gpa = semester_gpa
    if req.cumulative_credits > 0:
        cumulative_points = req.cumulative_gpa * req.cumulative_credits + total_points
        cumulative_credits = req.cumulative_credits + total_credits
        cumulative_gpa = cumulative_points / cumulative_credits

    return {
        "courses": course_results,
        "semester_gpa": round(semester_gpa, 2),
        "cumulative_gpa": round(cumulative_gpa, 2),
        "total_credits": total_credits,
        "message": f"Your semester GPA is {semester_gpa:.2f}, sir.",
    }


# === DICTIONARY ===

@router.get("/dictionary/{word}")
async def define_word(word: str):
    """Look up a word definition using the free dictionary API."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=10)
    except Exception:
        return {"word": word, "found": False, "message": f"Dictionary service unavailable. Try again later, sir."}

    if resp.status_code != 200:
        return {"word": word, "found": False, "message": f"I couldn't find a definition for '{word}', sir."}

    data = resp.json()[0]
    meanings = []
    for m in data.get("meanings", []):
        defs = []
        for d in m.get("definitions", [])[:3]:
            defs.append({
                "definition": d["definition"],
                "example": d.get("example"),
            })
        meanings.append({
            "part_of_speech": m["partOfSpeech"],
            "definitions": defs,
            "synonyms": m.get("synonyms", [])[:5],
        })

    return {
        "word": data.get("word"),
        "phonetic": data.get("phonetic"),
        "meanings": meanings,
        "found": True,
    }


# === FLASHCARDS ===

FLASHCARD_FILE = os.path.expanduser("~/.jarvis_flashcards.json")


class Flashcard(BaseModel):
    subject: str
    front: str
    back: str


class FlashcardDeck(BaseModel):
    subject: str


def _load_flashcards():
    if os.path.exists(FLASHCARD_FILE):
        with open(FLASHCARD_FILE) as f:
            return json.load(f)
    return {}


def _save_flashcards(data):
    with open(FLASHCARD_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.post("/flashcards/add")
async def add_flashcard(card: Flashcard):
    """Add a flashcard to a subject deck."""
    cards = _load_flashcards()
    if card.subject not in cards:
        cards[card.subject] = []
    cards[card.subject].append({"front": card.front, "back": card.back, "created": datetime.now().isoformat()})
    _save_flashcards(cards)
    return {"status": "added", "subject": card.subject, "total": len(cards[card.subject])}


@router.get("/flashcards/{subject}")
async def get_flashcards(subject: str):
    """Get all flashcards for a subject."""
    cards = _load_flashcards()
    deck = cards.get(subject, [])
    return {"subject": subject, "cards": deck, "total": len(deck)}


@router.get("/flashcards")
async def list_decks():
    """List all flashcard decks."""
    cards = _load_flashcards()
    decks = [{"subject": k, "count": len(v)} for k, v in cards.items()]
    return {"decks": decks}


# === CLASS SCHEDULE ===

SCHEDULE_FILE = os.path.expanduser("~/.jarvis_schedule.json")


class ClassEntry(BaseModel):
    name: str
    day: str  # Monday, Tuesday, etc.
    start_time: str  # "09:00"
    end_time: str  # "10:30"
    location: str = ""
    professor: str = ""


def _load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE) as f:
            return json.load(f)
    return []


def _save_schedule(data):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.post("/schedule/add")
async def add_class(entry: ClassEntry):
    """Add a class to your schedule."""
    schedule = _load_schedule()
    schedule.append(entry.model_dump())
    _save_schedule(schedule)
    return {"status": "added", "class": entry.name, "message": f"{entry.name} added to your schedule, sir."}


@router.get("/schedule")
async def get_schedule():
    """Get full class schedule."""
    schedule = _load_schedule()
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule.sort(key=lambda x: (days_order.index(x.get("day", "Monday")) if x.get("day") in days_order else 7, x.get("start_time", "")))
    return {"schedule": schedule, "total": len(schedule)}


@router.get("/schedule/today")
async def today_schedule():
    """Get today's classes."""
    schedule = _load_schedule()
    today = datetime.now().strftime("%A")
    today_classes = [c for c in schedule if c.get("day") == today]
    today_classes.sort(key=lambda x: x.get("start_time", ""))
    return {
        "day": today,
        "classes": today_classes,
        "total": len(today_classes),
        "message": f"You have {len(today_classes)} class(es) today, sir." if today_classes else "No classes today, sir. Enjoy your free time!",
    }


@router.delete("/schedule/{class_name}")
async def remove_class(class_name: str):
    """Remove a class from schedule."""
    schedule = _load_schedule()
    schedule = [c for c in schedule if c.get("name", "").lower() != class_name.lower()]
    _save_schedule(schedule)
    return {"status": "removed", "message": f"{class_name} removed from schedule, sir."}

"""Utility routes - translate, quotes, URL shortener, random facts, unit converter."""

import random
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# === TRANSLATION ===

class TranslateRequest(BaseModel):
    text: str
    to_lang: str = "es"
    from_lang: str = "auto"


@router.post("/translate")
async def translate(req: TranslateRequest):
    """Translate text using LibreTranslate (free, no API key)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://libretranslate.de/translate",
                json={
                    "q": req.text,
                    "source": req.from_lang,
                    "target": req.to_lang,
                },
                timeout=10,
            )
        if resp.status_code == 200:
            return {
                "original": req.text,
                "translated": resp.json()["translatedText"],
                "from": req.from_lang,
                "to": req.to_lang,
            }
    except Exception:
        pass
    # Fallback with common phrases
    return {
        "original": req.text,
        "status": "api_unavailable",
        "message": "Translation API is currently unavailable. Try Google Translate as backup.",
        "suggestion": f"https://translate.google.com/?sl={req.from_lang}&tl={req.to_lang}&text={req.text}",
    }


# === MOTIVATIONAL QUOTES ===

QUOTES = [
    {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
    {"quote": "Education is the most powerful weapon which you can use to change the world.", "author": "Nelson Mandela"},
    {"quote": "The future belongs to those who believe in the beauty of their dreams.", "author": "Eleanor Roosevelt"},
    {"quote": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucius"},
    {"quote": "Success is not final, failure is not fatal: it is the courage to continue that counts.", "author": "Winston Churchill"},
    {"quote": "Believe you can and you're halfway there.", "author": "Theodore Roosevelt"},
    {"quote": "The best time to plant a tree was 20 years ago. The second best time is now.", "author": "Chinese Proverb"},
    {"quote": "Your time is limited, don't waste it living someone else's life.", "author": "Steve Jobs"},
    {"quote": "In the middle of difficulty lies opportunity.", "author": "Albert Einstein"},
    {"quote": "What we know is a drop, what we don't know is an ocean.", "author": "Isaac Newton"},
    {"quote": "The only impossible journey is the one you never begin.", "author": "Tony Robbins"},
    {"quote": "Don't watch the clock; do what it does. Keep going.", "author": "Sam Levenson"},
    {"quote": "The secret of getting ahead is getting started.", "author": "Mark Twain"},
    {"quote": "I have not failed. I've just found 10,000 ways that won't work.", "author": "Thomas Edison"},
    {"quote": "Strive not to be a success, but rather to be of value.", "author": "Albert Einstein"},
]


@router.get("/quote")
async def get_quote():
    """Get a random motivational quote."""
    q = random.choice(QUOTES)
    return {"quote": q["quote"], "author": q["author"]}


@router.get("/quote/daily")
async def daily_quote():
    """Get a consistent daily quote (same quote all day)."""
    from datetime import datetime
    day_index = datetime.now().timetuple().tm_yday % len(QUOTES)
    q = QUOTES[day_index]
    return {"quote": q["quote"], "author": q["author"], "type": "daily"}


# === UNIT CONVERTER ===

CONVERSIONS = {
    "km_to_miles": 0.621371,
    "miles_to_km": 1.60934,
    "kg_to_lbs": 2.20462,
    "lbs_to_kg": 0.453592,
    "celsius_to_fahrenheit": lambda x: x * 9/5 + 32,
    "fahrenheit_to_celsius": lambda x: (x - 32) * 5/9,
    "cm_to_inches": 0.393701,
    "inches_to_cm": 2.54,
    "liters_to_gallons": 0.264172,
    "gallons_to_liters": 3.78541,
    "meters_to_feet": 3.28084,
    "feet_to_meters": 0.3048,
    "oz_to_grams": 28.3495,
    "grams_to_oz": 0.035274,
}


@router.get("/convert/{value}/{from_unit}/{to_unit}")
async def convert_units(value: float, from_unit: str, to_unit: str):
    """Convert between common units."""
    key = f"{from_unit.lower()}_to_{to_unit.lower()}"
    if key not in CONVERSIONS:
        available = [k.replace("_to_", " -> ") for k in CONVERSIONS]
        return {
            "error": f"Conversion '{from_unit} to {to_unit}' not supported.",
            "available": available,
        }
    conv = CONVERSIONS[key]
    result = conv(value) if callable(conv) else value * conv
    return {
        "from": f"{value} {from_unit}",
        "to": f"{round(result, 4)} {to_unit}",
        "result": round(result, 4),
    }


# === RANDOM FACTS ===

@router.get("/fact")
async def random_fact():
    """Get a random fun fact."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://uselessfacts.jsph.pl/api/v2/facts/random", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {"fact": data["text"], "source": data.get("source")}
    except Exception:
        pass
    facts = [
        "Honey never spoils. Archaeologists have found 3,000-year-old honey in Egyptian tombs that was still edible.",
        "A group of flamingos is called a 'flamboyance'.",
        "The shortest war in history lasted 38-45 minutes between Britain and Zanzibar in 1896.",
        "Octopuses have three hearts and blue blood.",
        "Bananas are berries, but strawberries aren't.",
    ]
    return {"fact": random.choice(facts), "source": "local"}


# === COUNTDOWN / IMPORTANT DATES ===

class CountdownDate(BaseModel):
    name: str
    date: str  # YYYY-MM-DD format


@router.post("/countdown")
async def countdown(event: CountdownDate):
    """Calculate days until an event."""
    from datetime import datetime
    try:
        target = datetime.strptime(event.date, "%Y-%m-%d")
        delta = target - datetime.now()
        days = delta.days
        if days < 0:
            return {"event": event.name, "days": abs(days), "message": f"{event.name} was {abs(days)} days ago, sir."}
        elif days == 0:
            return {"event": event.name, "days": 0, "message": f"{event.name} is today, sir!"}
        return {"event": event.name, "days": days, "message": f"{days} days until {event.name}, sir."}
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

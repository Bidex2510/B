"""Jarvis Web API - FastAPI server exposing all Jarvis capabilities."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from jarvis.core.assistant import Jarvis
from jarvis.api.routes import (
    chat, weather, email, news, spotify, home_assistant,
    ai, study, finance, utilities, system, notes,
)

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Jarvis AI Assistant",
    description="Personal AI Assistant API - Your digital butler",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Shared Jarvis instance
jarvis = Jarvis()
app.state.jarvis = jarvis

# Register route modules
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(weather.router, prefix="/api/weather", tags=["Weather"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(spotify.router, prefix="/api/spotify", tags=["Spotify"])
app.include_router(home_assistant.router, prefix="/api/home", tags=["Home Assistant"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Chat"])
app.include_router(study.router, prefix="/api/study", tags=["Study Tools"])
app.include_router(finance.router, prefix="/api/finance", tags=["Finance"])
app.include_router(utilities.router, prefix="/api/utils", tags=["Utilities"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(notes.router, prefix="/api/notes", tags=["Class Notes"])


@app.get("/notes")
async def notes_page(request: Request):
    """Serve the class note-taking page."""
    return templates.TemplateResponse("notes.html", {"request": request})


@app.get("/")
async def dashboard(request: Request):
    """Serve the main Jarvis dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/health")
async def health():
    return {"status": "online", "message": "All systems operational, sir."}

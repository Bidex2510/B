"""Chat endpoint - main conversational interface."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ChatMessage(BaseModel):
    message: str


@router.post("/chat")
async def chat(msg: ChatMessage, request: Request):
    """Send a message to Jarvis and get a response."""
    jarvis = request.app.state.jarvis
    response = jarvis.chat(msg.message)
    return {"response": response, "status": "ok"}


@router.get("/capabilities")
async def capabilities(request: Request):
    """List all Jarvis capabilities."""
    jarvis = request.app.state.jarvis
    caps = []
    for name, plugin in jarvis.brain.plugins.items():
        caps.append({"name": name, "description": plugin.description})
    return {"capabilities": caps}

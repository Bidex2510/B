"""Claude AI conversation routes - real AI-powered chat."""

import os
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


class AIMessage(BaseModel):
    message: str
    context: str = ""
    max_tokens: int = 1024


class AIStudyHelp(BaseModel):
    subject: str
    question: str
    level: str = "college freshman"


@router.post("/chat")
async def ai_chat(msg: AIMessage):
    """Have a real AI conversation powered by Claude."""
    if not API_KEY:
        return {
            "status": "config_needed",
            "message": "Set ANTHROPIC_API_KEY in your .env file. Get one at https://console.anthropic.com",
            "fallback_response": _fallback_response(msg.message),
        }

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEY)
        system_prompt = (
            "You are Jarvis, a sophisticated personal AI assistant inspired by Iron Man's Jarvis. "
            "You address the user as 'sir' and are helpful, witty, and concise. "
            "You're assisting a college freshman with their daily life."
        )
        if msg.context:
            system_prompt += f"\n\nAdditional context: {msg.context}"

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=msg.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": msg.message}],
        )
        return {
            "response": response.content[0].text,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
    except ImportError:
        return {
            "status": "dependency_needed",
            "message": "Install the anthropic package: pip install anthropic",
            "fallback_response": _fallback_response(msg.message),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/study-help")
async def study_help(req: AIStudyHelp):
    """Get AI-powered study help on any subject."""
    msg = AIMessage(
        message=f"Help me understand this {req.subject} question (I'm a {req.level}): {req.question}",
        context=f"Subject: {req.subject}. Explain clearly with examples. Break down complex concepts.",
    )
    return await ai_chat(msg)


@router.post("/summarize")
async def summarize(msg: AIMessage):
    """Summarize text using AI."""
    msg.context = "Provide a clear, concise summary. Use bullet points for key takeaways."
    msg.message = f"Please summarize the following:\n\n{msg.message}"
    return await ai_chat(msg)


@router.post("/essay-help")
async def essay_help(msg: AIMessage):
    """Get help with essay writing - outlines, feedback, grammar."""
    msg.context = (
        "Help with academic writing. Provide constructive feedback, suggest improvements, "
        "and help with structure. Don't write the essay for them - guide them."
    )
    return await ai_chat(msg)


@router.post("/explain-code")
async def explain_code(msg: AIMessage):
    """Explain code in simple terms."""
    msg.context = "Explain this code simply for a college student learning to program. Use analogies where helpful."
    msg.message = f"Explain this code:\n\n{msg.message}"
    return await ai_chat(msg)


def _fallback_response(message):
    """Basic response when Claude API isn't configured."""
    lower = message.lower()
    if "help" in lower:
        return "I'd love to help with that, sir. Once you configure the ANTHROPIC_API_KEY, I'll be able to have full AI-powered conversations."
    return (
        "I can provide much better answers with the Claude AI integration enabled. "
        "Set your ANTHROPIC_API_KEY in the .env file to unlock my full potential, sir."
    )

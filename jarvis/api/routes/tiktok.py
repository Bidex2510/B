"""TikTok content generation routes - ideas, scripts, captions, calendar."""

import os
import random
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

CATEGORY_DESC = {
    "sports": "sports highlights, athlete stories, game analysis, training tips, sports facts",
    "wholesome": "heartwarming stories, acts of kindness, feel-good moments, inspiring people",
    "ai": "AI tools, ChatGPT tricks, automation, tech news, AI tutorials, future of technology",
}

VIDEO_IDEAS = {
    "sports": [
        "5 mind-blowing sports facts nobody talks about",
        "The greatest comeback in [sport] history explained in 60 seconds",
        "What pro athletes eat before a big game",
        "The training secret that made [athlete] great",
        "Rating viral sports moments: real or fake?",
        "The most underrated sport you should be watching",
        "Why [team] will win the championship this year",
        "Behind the scenes: athlete warm-up routines",
        "Teaching myself [sport] in 30 days - day 1",
        "Sports records that will never be broken",
    ],
    "wholesome": [
        "Dog sees their owner for the first time in months",
        "Grandparents react to modern music challenge",
        "Kids explain what love means - their answers are perfect",
        "Random acts of kindness that restore faith in humanity",
        "The world's kindest bus driver goes viral",
        "Animals meeting each other for the first time",
        "Teachers who changed students' lives forever",
        "Community helps stranger in need - wholesome ending",
        "Baby's first reaction to [fruit/animal/music]",
        "Surprise reunion that will make you tear up",
    ],
    "ai": [
        "I asked AI to build my website - here's what happened",
        "5 AI tools that are completely free in 2025",
        "AI vs Human: who does [task] better?",
        "The ChatGPT prompt that changed how I work",
        "I used AI to plan my entire week - results were wild",
        "The AI tool quietly replacing [job] right now",
        "Build a chatbot in 5 minutes with zero code",
        "Testing the newest AI model so you don't have to",
        "How I built my own JARVIS assistant for free",
        "AI predicted this 5 years ago... it came true",
    ],
}

HASHTAGS = {
    "sports": ["#sports", "#athlete", "#fyp", "#viral", "#sportsedits", "#motivation", "#winning", "#champion", "#sportsnews", "#sportslovers"],
    "wholesome": ["#wholesome", "#heartwarming", "#fyp", "#viral", "#feelgood", "#kindness", "#love", "#inspiring", "#positivevibes", "#happiness"],
    "ai": ["#ai", "#artificialintelligence", "#tech", "#fyp", "#viral", "#future", "#aitools", "#chatgpt", "#automation", "#technology"],
}


class ScriptRequest(BaseModel):
    category: str = "sports"
    topic: Optional[str] = None
    duration: int = 60


class CaptionRequest(BaseModel):
    category: str
    topic: str


@router.get("/ideas")
async def get_ideas(category: str = "all", count: int = 5):
    """Get TikTok video ideas by category."""
    if category == "all":
        result = {}
        for cat, ideas in VIDEO_IDEAS.items():
            result[cat] = random.sample(ideas, min(count, len(ideas)))
        return {"ideas": result, "total": sum(len(v) for v in result.values())}

    cat_ideas = VIDEO_IDEAS.get(category.lower(), VIDEO_IDEAS["ai"])
    selected = random.sample(cat_ideas, min(count, len(cat_ideas)))
    return {"category": category, "ideas": selected, "total": len(selected)}


@router.post("/script")
async def generate_script(req: ScriptRequest):
    """Generate a full TikTok video script using Claude AI (uses cheapest model)."""
    cat_desc = CATEGORY_DESC.get(req.category.lower(), CATEGORY_DESC["ai"])
    topic = req.topic or f"interesting {req.category} content"

    if not API_KEY:
        return {
            "status": "config_needed",
            "message": "Set ANTHROPIC_API_KEY in your .env file for AI-generated scripts.",
            "sample_script": _sample_script(req.category, topic),
        }

    prompt = f"""Write a TikTok video script for a {req.duration}-second video.

Category: {req.category.upper()} ({cat_desc})
Topic: {topic}

Structure:
HOOK (0-3 sec): [One punchy opening line that stops the scroll]
CONTENT ({3}-{req.duration - 5} sec): [Main points, keep each beat 5-10 seconds]
CTA (last 5 sec): [Follow + comment prompt]

Also include:
CAPTION: [With emojis, max 150 chars]
HASHTAGS: [10 hashtags]
THUMBNAIL TEXT: [Bold 3-5 word text for thumbnail]

Keep it conversational, authentic, and high-energy."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=(
                "You are a viral TikTok content creator specializing in sports, wholesome, and AI content. "
                "You write engaging, authentic scripts that perform well with the algorithm. "
                "You understand hooks, pacing, and calls to action."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "script": response.content[0].text,
            "category": req.category,
            "topic": topic,
            "duration": req.duration,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "sample_script": _sample_script(req.category, topic),
        }


@router.post("/caption")
async def generate_caption(req: CaptionRequest):
    """Generate TikTok captions with hashtags for a given topic."""
    tags = HASHTAGS.get(req.category.lower(), HASHTAGS["ai"])
    hashtag_str = " ".join(tags)

    captions = [
        f"This {req.topic} will blow your mind 🤯 | {hashtag_str}",
        f"Nobody talks about this... ✨ {req.topic} | Follow for more! | {hashtag_str}",
        f"POV: you just discovered {req.topic} 👀 | {hashtag_str}",
        f"Wait for it... 🙌 {req.topic} | Comment 'MORE' for part 2! | {hashtag_str}",
        f"The {req.topic} secret they don't want you to know 🔥 | {hashtag_str}",
    ]

    return {
        "captions": captions,
        "hashtags": tags,
        "category": req.category,
        "tip": "Best posting times: 9AM, 12PM, 7PM in your audience's timezone",
        "caption_formula": "Hook + Context + CTA = engagement",
    }


@router.get("/calendar")
async def content_calendar():
    """Get a 7-day TikTok content posting calendar."""
    calendar = [
        {"day": "Monday", "time": "9:00 AM", "category": "AI", "idea": "AI tool of the week spotlight", "why": "Start of week = professional content wins"},
        {"day": "Tuesday", "time": "7:00 PM", "category": "Sports", "idea": "Sports recap or bold prediction", "why": "Evening sports fans checking highlights"},
        {"day": "Wednesday", "time": "12:00 PM", "category": "Wholesome", "idea": "Mid-week motivation / feel-good story", "why": "Hump day - people need positivity"},
        {"day": "Thursday", "time": "6:00 PM", "category": "AI", "idea": "AI tutorial or productivity tips", "why": "Pre-weekend, people learning new skills"},
        {"day": "Friday", "time": "5:00 PM", "category": "Sports", "idea": "Weekend sports preview or analysis", "why": "TGIF - sports fans hyped for weekend games"},
        {"day": "Saturday", "time": "11:00 AM", "category": "Wholesome", "idea": "Weekend feel-good or animal content", "why": "Lazy Saturday browsing - emotional content pops"},
        {"day": "Sunday", "time": "3:00 PM", "category": "AI", "idea": "Week in AI recap video", "why": "Sunday prep - people planning ahead"},
    ]

    return {
        "calendar": calendar,
        "strategy": "Post 1x/day minimum. Mix categories to reach different audiences.",
        "optimal_length": {"ai": "45-60 seconds", "sports": "30-45 seconds", "wholesome": "60-90 seconds"},
        "account_tips": [
            "Use a consistent posting schedule - algorithm rewards it",
            "Reply to every comment in the first hour",
            "Stitch/duet trending videos in your niche",
            "Pin your 3 best videos to your profile",
        ],
    }


@router.get("/trending")
async def get_trending_topics():
    """Get trending topic angles for each content category."""
    return {
        "sports": [
            "NBA/NFL/soccer transfer drama and hot takes",
            "Athlete diet and training secrets revealed",
            "Underdog stories that defy the odds",
            "Sports records that were just broken",
            "Rating celebrity athletes' actual skill level",
        ],
        "wholesome": [
            "Military homecoming reunions",
            "Acts of kindness challenge responses",
            "Pet adoption and rescue stories",
            "Teachers going above and beyond",
            "Surprise makeovers for deserving people",
        ],
        "ai": [
            "Claude vs ChatGPT live comparisons",
            "AI tools that are genuinely free in 2025",
            "Building things with Claude Code (no-code)",
            "AI replacing jobs - real examples",
            "Automating daily life with free AI tools",
        ],
        "hook_tip": "First 1.5 seconds decide everything. Lead with your most shocking statement.",
        "algorithm_tip": "Watch time + comments > likes. Make people comment with controversial or open-ended endings.",
    }


def _sample_script(category: str, topic: str) -> dict:
    return {
        "hook": f"Nobody talks about this {category} secret...",
        "content": (
            f"Beat 1: Here's what most people get wrong about {topic}\n"
            f"Beat 2: The real truth that changed everything\n"
            f"Beat 3: Here's what you should actually do instead"
        ),
        "cta": "Follow for more! Drop a comment with your thoughts below!",
        "caption": f"This changed everything about {topic} 🤯 #fyp #viral #{category}",
        "thumbnail_text": f"{topic.upper()} SECRET",
        "note": "Add ANTHROPIC_API_KEY to .env for fully AI-generated scripts",
    }

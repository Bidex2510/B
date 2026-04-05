"""News API routes - top headlines and search."""

import os
import httpx
from fastapi import APIRouter

router = APIRouter()

API_KEY = os.getenv("NEWS_API_KEY", "")
BASE_URL = "https://newsapi.org/v2"


@router.get("/top")
async def top_headlines(country: str = "us", category: str = "general", count: int = 10):
    """Get top news headlines.

    Categories: general, business, technology, science, sports, entertainment, health
    """
    if not API_KEY:
        return {
            "status": "config_needed",
            "message": "Set NEWS_API_KEY in your .env file. Get a free key at https://newsapi.org",
            "mock_data": _mock_news(),
        }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/top-headlines",
            params={"country": country, "category": category, "pageSize": count, "apiKey": API_KEY},
        )
    data = resp.json()
    articles = []
    for a in data.get("articles", []):
        articles.append({
            "title": a["title"],
            "source": a["source"]["name"],
            "description": a.get("description"),
            "url": a["url"],
            "published": a.get("publishedAt"),
            "image": a.get("urlToImage"),
        })
    return {"articles": articles, "total": len(articles)}


@router.get("/search")
async def search_news(query: str, count: int = 10, sort_by: str = "relevancy"):
    """Search news articles.

    sort_by: relevancy, popularity, publishedAt
    """
    if not API_KEY:
        return {"status": "config_needed", "message": "Set NEWS_API_KEY to search news."}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/everything",
            params={"q": query, "pageSize": count, "sortBy": sort_by, "apiKey": API_KEY},
        )
    data = resp.json()
    articles = []
    for a in data.get("articles", []):
        articles.append({
            "title": a["title"],
            "source": a["source"]["name"],
            "description": a.get("description"),
            "url": a["url"],
            "published": a.get("publishedAt"),
        })
    return {"articles": articles}


@router.get("/tech")
async def tech_news(count: int = 10):
    """Get top technology news."""
    return await top_headlines(category="technology", count=count)


@router.get("/sports")
async def sports_news(count: int = 10):
    """Get top sports news."""
    return await top_headlines(category="sports", count=count)


def _mock_news():
    return [
        {"title": "AI Breakthrough in Natural Language Processing", "source": "TechCrunch", "description": "New models achieve human-level understanding..."},
        {"title": "Campus Innovation Hub Opens", "source": "University News", "description": "Students now have access to 3D printers..."},
        {"title": "NBA Playoffs Update", "source": "ESPN", "description": "Last night's games saw dramatic finishes..."},
    ]

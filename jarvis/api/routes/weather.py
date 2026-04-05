"""Weather API routes - OpenWeatherMap integration."""

import os
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5"


@router.get("/current/{city}")
async def get_current_weather(city: str, units: str = "imperial"):
    """Get current weather for a city.

    Units: 'imperial' (°F), 'metric' (°C), 'standard' (K)
    """
    if not API_KEY:
        return {
            "status": "config_needed",
            "message": "Set OPENWEATHER_API_KEY in your .env file. Get a free key at https://openweathermap.org/api",
            "mock_data": _mock_weather(city),
        }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/weather",
            params={"q": city, "appid": API_KEY, "units": units},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json())
    data = resp.json()
    return {
        "city": data["name"],
        "country": data["sys"]["country"],
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "icon": data["weather"][0]["icon"],
        "wind_speed": data["wind"]["speed"],
    }


@router.get("/forecast/{city}")
async def get_forecast(city: str, units: str = "imperial"):
    """Get 5-day weather forecast for a city."""
    if not API_KEY:
        return {
            "status": "config_needed",
            "message": "Set OPENWEATHER_API_KEY in your .env file.",
        }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/forecast",
            params={"q": city, "appid": API_KEY, "units": units},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json())
    data = resp.json()
    forecasts = []
    for item in data["list"][:10]:
        forecasts.append({
            "datetime": item["dt_txt"],
            "temp": item["main"]["temp"],
            "description": item["weather"][0]["description"],
            "icon": item["weather"][0]["icon"],
        })
    return {"city": data["city"]["name"], "forecasts": forecasts}


def _mock_weather(city):
    return {
        "city": city,
        "temperature": 72,
        "feels_like": 70,
        "humidity": 45,
        "description": "partly cloudy",
        "wind_speed": 8,
        "note": "This is mock data. Add your API key for real weather.",
    }

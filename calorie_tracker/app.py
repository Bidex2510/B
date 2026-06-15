import datetime
import json
import os
import httpx
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, get_db, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CalTrack – Calorie Tracking App")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

USDA_API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")
USDA_BASE = "https://api.nal.usda.gov/fdc/v1"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_profile(db: Session) -> models.UserProfile:
    profile = db.query(models.UserProfile).first()
    if not profile:
        profile = models.UserProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _calculate_tdee(profile: models.UserProfile) -> int:
    """Harris-Benedict BMR → TDEE → goal adjustment."""
    w, h, a = profile.weight_kg, profile.height_cm, profile.age
    if profile.sex == "female":
        bmr = 447.593 + 9.247 * w + 3.098 * h - 4.330 * a
    else:
        bmr = 88.362 + 13.397 * w + 4.799 * h - 5.677 * a

    multipliers = {
        "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
        "active": 1.725, "very_active": 1.9,
    }
    tdee = bmr * multipliers.get(profile.activity_level, 1.55)

    adjustments = {"lose": -500, "maintain": 0, "gain": 300}
    return round(tdee + adjustments.get(profile.goal, 0))


def _macros_from_calories(calories: int, goal: str) -> dict:
    if goal == "lose":
        p_pct, c_pct, f_pct = 0.35, 0.35, 0.30
    elif goal == "gain":
        p_pct, c_pct, f_pct = 0.30, 0.50, 0.20
    else:
        p_pct, c_pct, f_pct = 0.25, 0.45, 0.30
    return {
        "protein": round(calories * p_pct / 4),
        "carbs": round(calories * c_pct / 4),
        "fat": round(calories * f_pct / 9),
    }


def _scale(food: models.FoodItem, qty_g: float) -> dict:
    ratio = qty_g / food.serving_size_g
    return {
        "calories": round(food.calories * ratio, 1),
        "protein_g": round(food.protein_g * ratio, 1),
        "carbs_g": round(food.carbs_g * ratio, 1),
        "fat_g": round(food.fat_g * ratio, 1),
    }


# ─── pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db)
    return templates.TemplateResponse("index.html", {"request": request, "profile": profile})


# ─── profile API ──────────────────────────────────────────────────────────────

class ProfileIn(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    sex: Optional[str] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    water_goal_ml: Optional[int] = None


@app.get("/api/profile")
def get_profile(db: Session = Depends(get_db)):
    p = _get_or_create_profile(db)
    return {
        "id": p.id, "name": p.name, "age": p.age,
        "weight_kg": p.weight_kg, "height_cm": p.height_cm,
        "sex": p.sex, "activity_level": p.activity_level, "goal": p.goal,
        "calorie_goal": p.calorie_goal, "protein_goal": p.protein_goal,
        "carbs_goal": p.carbs_goal, "fat_goal": p.fat_goal,
        "water_goal_ml": p.water_goal_ml,
    }


@app.put("/api/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = _get_or_create_profile(db)
    for k, v in body.dict(exclude_none=True).items():
        setattr(p, k, v)
    # Recalculate goals when body composition changes
    p.calorie_goal = _calculate_tdee(p)
    macros = _macros_from_calories(p.calorie_goal, p.goal)
    p.protein_goal = macros["protein"]
    p.carbs_goal = macros["carbs"]
    p.fat_goal = macros["fat"]
    db.commit()
    db.refresh(p)
    return {"calorie_goal": p.calorie_goal, "protein_goal": p.protein_goal,
            "carbs_goal": p.carbs_goal, "fat_goal": p.fat_goal}


# ─── food search ──────────────────────────────────────────────────────────────

@app.get("/api/food/search")
async def search_food(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    # 1. search local DB first
    local = db.query(models.FoodItem).filter(
        models.FoodItem.name.ilike(f"%{q}%")
    ).limit(10).all()

    results = [
        {"id": f.id, "name": f.name, "brand": f.brand,
         "calories": f.calories, "serving_size_g": f.serving_size_g,
         "serving_unit": f.serving_unit, "source": "local"}
        for f in local
    ]

    # 2. call USDA if local has < 5 results
    if len(results) < 5:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{USDA_BASE}/foods/search", params={
                    "query": q, "api_key": USDA_API_KEY,
                    "dataType": "Foundation,SR Legacy,Branded", "pageSize": 10,
                })
            if resp.status_code == 200:
                for item in resp.json().get("foods", []):
                    nutrients = {n["nutrientId"]: n["value"] for n in item.get("foodNutrients", [])}
                    results.append({
                        "id": None,
                        "usda_fdc_id": str(item["fdcId"]),
                        "name": item.get("description", ""),
                        "brand": item.get("brandOwner", ""),
                        "calories": nutrients.get(1008, 0),
                        "serving_size_g": item.get("servingSize", 100),
                        "serving_unit": item.get("servingSizeUnit", "g"),
                        "source": "usda",
                        "nutrients": nutrients,
                    })
        except Exception:
            pass  # fall back to local results only

    return results


@app.get("/api/food/barcode/{barcode}")
async def lookup_barcode(barcode: str, db: Session = Depends(get_db)):
    # check local
    item = db.query(models.FoodItem).filter(models.FoodItem.barcode == barcode).first()
    if item:
        return {"id": item.id, "name": item.name, "calories": item.calories,
                "serving_size_g": item.serving_size_g, "source": "local"}
    # USDA branded search
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{USDA_BASE}/foods/search", params={
                "query": barcode, "api_key": USDA_API_KEY,
                "dataType": "Branded", "pageSize": 1,
            })
        if resp.status_code == 200:
            foods = resp.json().get("foods", [])
            if foods:
                f = foods[0]
                nutrients = {n["nutrientId"]: n["value"] for n in f.get("foodNutrients", [])}
                return {
                    "id": None,
                    "usda_fdc_id": str(f["fdcId"]),
                    "name": f.get("description", ""),
                    "brand": f.get("brandOwner", ""),
                    "calories": nutrients.get(1008, 0),
                    "serving_size_g": f.get("servingSize", 100),
                    "source": "usda",
                    "nutrients": nutrients,
                }
    except Exception:
        pass
    raise HTTPException(404, "Product not found")


class FoodItemIn(BaseModel):
    name: str
    brand: Optional[str] = None
    barcode: Optional[str] = None
    usda_fdc_id: Optional[str] = None
    serving_size_g: float = 100.0
    serving_unit: str = "g"
    calories: float
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


@app.post("/api/food")
def create_food(body: FoodItemIn, db: Session = Depends(get_db)):
    item = models.FoodItem(**body.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id}


# ─── food log API ─────────────────────────────────────────────────────────────

class LogIn(BaseModel):
    food_item_id: Optional[int] = None
    usda_fdc_id: Optional[str] = None
    food_data: Optional[dict] = None  # if creating food on the fly
    date: Optional[str] = None  # YYYY-MM-DD
    meal_type: str = "lunch"
    quantity_g: float = 100.0


@app.post("/api/log")
def add_log(body: LogIn, db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db)
    date = datetime.date.fromisoformat(body.date) if body.date else datetime.date.today()

    food_id = body.food_item_id
    # create food item on-the-fly from USDA data
    if not food_id and body.food_data:
        fd = body.food_data
        item = models.FoodItem(
            name=fd.get("name", "Unknown"),
            brand=fd.get("brand"),
            usda_fdc_id=fd.get("usda_fdc_id"),
            serving_size_g=fd.get("serving_size_g", 100),
            serving_unit=fd.get("serving_unit", "g"),
            calories=fd.get("calories", 0),
            protein_g=fd.get("protein_g", 0),
            carbs_g=fd.get("carbs_g", 0),
            fat_g=fd.get("fat_g", 0),
            fiber_g=fd.get("fiber_g", 0),
            sugar_g=fd.get("sugar_g", 0),
            sodium_mg=fd.get("sodium_mg", 0),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        food_id = item.id

    food = db.query(models.FoodItem).get(food_id)
    if not food:
        raise HTTPException(404, "Food item not found")

    scaled = _scale(food, body.quantity_g)
    log = models.FoodLog(
        user_id=profile.id,
        food_item_id=food_id,
        date=date,
        meal_type=body.meal_type,
        quantity_g=body.quantity_g,
        **scaled,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"id": log.id, **scaled}


@app.get("/api/log")
def get_logs(date: Optional[str] = None, db: Session = Depends(get_db)):
    d = datetime.date.fromisoformat(date) if date else datetime.date.today()
    logs = db.query(models.FoodLog).filter(models.FoodLog.date == d).all()
    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "food_name": log.food_item.name if log.food_item else "Unknown",
            "brand": log.food_item.brand if log.food_item else None,
            "meal_type": log.meal_type,
            "quantity_g": log.quantity_g,
            "calories": log.calories,
            "protein_g": log.protein_g,
            "carbs_g": log.carbs_g,
            "fat_g": log.fat_g,
        })
    return result


@app.delete("/api/log/{log_id}")
def delete_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.FoodLog).get(log_id)
    if not log:
        raise HTTPException(404, "Log not found")
    db.delete(log)
    db.commit()
    return {"ok": True}


# ─── summary API ──────────────────────────────────────────────────────────────

@app.get("/api/summary")
def get_summary(date: Optional[str] = None, db: Session = Depends(get_db)):
    d = datetime.date.fromisoformat(date) if date else datetime.date.today()
    profile = _get_or_create_profile(db)

    logs = db.query(models.FoodLog).filter(models.FoodLog.date == d).all()
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
    for log in logs:
        totals["calories"] += log.calories
        totals["protein_g"] += log.protein_g
        totals["carbs_g"] += log.carbs_g
        totals["fat_g"] += log.fat_g

    water = db.query(func.sum(models.WaterLog.amount_ml)).filter(
        models.WaterLog.date == d
    ).scalar() or 0

    return {
        "date": d.isoformat(),
        "totals": {k: round(v, 1) for k, v in totals.items()},
        "goals": {
            "calories": profile.calorie_goal,
            "protein_g": profile.protein_goal,
            "carbs_g": profile.carbs_goal,
            "fat_g": profile.fat_goal,
        },
        "water_ml": water,
        "water_goal_ml": profile.water_goal_ml,
    }


@app.get("/api/trends")
def get_trends(days: int = 7, db: Session = Depends(get_db)):
    today = datetime.date.today()
    dates = [today - datetime.timedelta(days=i) for i in range(days - 1, -1, -1)]
    data = []
    for d in dates:
        logs = db.query(models.FoodLog).filter(models.FoodLog.date == d).all()
        cal = sum(l.calories for l in logs)
        protein = sum(l.protein_g for l in logs)
        carbs = sum(l.carbs_g for l in logs)
        fat = sum(l.fat_g for l in logs)
        w_log = db.query(models.WeightLog).filter(models.WeightLog.date == d).order_by(
            models.WeightLog.id.desc()
        ).first()
        data.append({
            "date": d.strftime("%b %d"),
            "calories": round(cal, 1),
            "protein": round(protein, 1),
            "carbs": round(carbs, 1),
            "fat": round(fat, 1),
            "weight": w_log.weight_kg if w_log else None,
        })
    return data


# ─── water API ────────────────────────────────────────────────────────────────

class WaterIn(BaseModel):
    amount_ml: int = 250
    date: Optional[str] = None


@app.post("/api/water")
def log_water(body: WaterIn, db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db)
    d = datetime.date.fromisoformat(body.date) if body.date else datetime.date.today()
    entry = models.WaterLog(user_id=profile.id, date=d, amount_ml=body.amount_ml)
    db.add(entry)
    db.commit()
    return {"ok": True}


# ─── weight API ───────────────────────────────────────────────────────────────

class WeightIn(BaseModel):
    weight_kg: float
    date: Optional[str] = None


@app.post("/api/weight")
def log_weight(body: WeightIn, db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db)
    d = datetime.date.fromisoformat(body.date) if body.date else datetime.date.today()
    # Update profile weight too
    profile.weight_kg = body.weight_kg
    entry = models.WeightLog(user_id=profile.id, date=d, weight_kg=body.weight_kg)
    db.add(entry)
    db.commit()
    return {"ok": True}


# ─── common foods seed ────────────────────────────────────────────────────────

SEED_FOODS = [
    {"name": "Chicken Breast (cooked)", "serving_size_g": 100, "serving_unit": "g",
     "calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6},
    {"name": "White Rice (cooked)", "serving_size_g": 100, "serving_unit": "g",
     "calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3},
    {"name": "Banana", "serving_size_g": 118, "serving_unit": "medium",
     "calories": 105, "protein_g": 1.3, "carbs_g": 27, "fat_g": 0.4},
    {"name": "Whole Egg", "serving_size_g": 50, "serving_unit": "large",
     "calories": 72, "protein_g": 6.3, "carbs_g": 0.4, "fat_g": 5},
    {"name": "Oats (dry)", "serving_size_g": 40, "serving_unit": "cup",
     "calories": 154, "protein_g": 5.4, "carbs_g": 27, "fat_g": 2.6},
    {"name": "Salmon (cooked)", "serving_size_g": 100, "serving_unit": "g",
     "calories": 208, "protein_g": 20, "carbs_g": 0, "fat_g": 13},
    {"name": "Broccoli (raw)", "serving_size_g": 100, "serving_unit": "g",
     "calories": 34, "protein_g": 2.8, "carbs_g": 7, "fat_g": 0.4},
    {"name": "Whole Milk", "serving_size_g": 244, "serving_unit": "cup",
     "calories": 149, "protein_g": 8, "carbs_g": 12, "fat_g": 8},
    {"name": "Greek Yogurt (plain)", "serving_size_g": 170, "serving_unit": "container",
     "calories": 100, "protein_g": 17, "carbs_g": 6, "fat_g": 0.7},
    {"name": "Almonds", "serving_size_g": 28, "serving_unit": "oz",
     "calories": 164, "protein_g": 6, "carbs_g": 6, "fat_g": 14},
    {"name": "Sweet Potato (cooked)", "serving_size_g": 130, "serving_unit": "medium",
     "calories": 112, "protein_g": 2, "carbs_g": 26, "fat_g": 0.1},
    {"name": "Avocado", "serving_size_g": 68, "serving_unit": "half",
     "calories": 114, "protein_g": 1.3, "carbs_g": 6, "fat_g": 10.5},
    {"name": "Bread (whole wheat)", "serving_size_g": 43, "serving_unit": "slice",
     "calories": 110, "protein_g": 5, "carbs_g": 20, "fat_g": 2},
    {"name": "Peanut Butter", "serving_size_g": 32, "serving_unit": "tbsp",
     "calories": 190, "protein_g": 7, "carbs_g": 7, "fat_g": 16},
    {"name": "Apple", "serving_size_g": 182, "serving_unit": "medium",
     "calories": 95, "protein_g": 0.5, "carbs_g": 25, "fat_g": 0.3},
]


@app.post("/api/seed")
def seed_foods(db: Session = Depends(get_db)):
    count = db.query(models.FoodItem).count()
    if count > 0:
        return {"message": "Already seeded", "count": count}
    for food in SEED_FOODS:
        db.add(models.FoodItem(**food))
    db.commit()
    return {"message": "Seeded", "count": len(SEED_FOODS)}

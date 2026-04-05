"""Finance tools - budget tracking, currency conversion, expense tracker."""

import os
import json
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

BUDGET_FILE = os.path.expanduser("~/.jarvis_budget.json")


# === BUDGET / EXPENSE TRACKER ===

class Expense(BaseModel):
    amount: float
    category: str  # food, transport, entertainment, books, rent, other
    description: str = ""


class Budget(BaseModel):
    monthly_budget: float
    categories: dict[str, float] = {}  # category -> budget limit


def _load_budget():
    if os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE) as f:
            return json.load(f)
    return {"budget": 0, "category_limits": {}, "expenses": []}


def _save_budget(data):
    with open(BUDGET_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.post("/budget/set")
async def set_budget(budget: Budget):
    """Set your monthly budget."""
    data = _load_budget()
    data["budget"] = budget.monthly_budget
    data["category_limits"] = budget.categories
    _save_budget(data)
    return {"status": "set", "budget": budget.monthly_budget, "message": f"Monthly budget set to ${budget.monthly_budget:.2f}, sir."}


@router.post("/expense/add")
async def add_expense(expense: Expense):
    """Log an expense."""
    data = _load_budget()
    entry = {
        "amount": expense.amount,
        "category": expense.category,
        "description": expense.description,
        "date": datetime.now().isoformat(),
    }
    data["expenses"].append(entry)
    _save_budget(data)

    # Check budget warning
    month_expenses = sum(
        e["amount"] for e in data["expenses"]
        if e["date"][:7] == datetime.now().strftime("%Y-%m")
    )
    warning = ""
    if data["budget"] > 0 and month_expenses > data["budget"] * 0.8:
        remaining = data["budget"] - month_expenses
        if remaining < 0:
            warning = f" Warning: You're ${abs(remaining):.2f} over budget this month!"
        else:
            warning = f" Heads up: Only ${remaining:.2f} left in this month's budget."

    return {
        "status": "logged",
        "expense": entry,
        "month_total": round(month_expenses, 2),
        "message": f"${expense.amount:.2f} logged for {expense.category}.{warning}",
    }


@router.get("/expense/summary")
async def expense_summary():
    """Get expense summary for the current month."""
    data = _load_budget()
    current_month = datetime.now().strftime("%Y-%m")
    month_expenses = [e for e in data["expenses"] if e["date"][:7] == current_month]

    by_category = {}
    for e in month_expenses:
        cat = e["category"]
        by_category[cat] = by_category.get(cat, 0) + e["amount"]

    total = sum(e["amount"] for e in month_expenses)
    remaining = data["budget"] - total if data["budget"] > 0 else None

    return {
        "month": current_month,
        "total_spent": round(total, 2),
        "budget": data["budget"],
        "remaining": round(remaining, 2) if remaining is not None else None,
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "transaction_count": len(month_expenses),
    }


@router.get("/expense/history")
async def expense_history(limit: int = 20):
    """Get recent expense history."""
    data = _load_budget()
    recent = sorted(data["expenses"], key=lambda x: x["date"], reverse=True)[:limit]
    return {"expenses": recent, "total": len(data["expenses"])}


@router.delete("/expense/clear")
async def clear_expenses():
    """Clear all expenses (fresh start)."""
    data = _load_budget()
    data["expenses"] = []
    _save_budget(data)
    return {"status": "cleared", "message": "All expenses cleared, sir."}


# === CURRENCY CONVERTER ===

@router.get("/currency/{amount}/{from_currency}/{to_currency}")
async def convert_currency(amount: float, from_currency: str, to_currency: str):
    """Convert between currencies using a free API."""
    import httpx
    from_c = from_currency.upper()
    to_c = to_currency.upper()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.exchangerate-api.com/v4/latest/{from_c}"
        )
    if resp.status_code != 200:
        return {"error": "Failed to fetch exchange rates. Check currency codes."}
    rates = resp.json().get("rates", {})
    if to_c not in rates:
        return {"error": f"Currency {to_c} not found."}
    rate = rates[to_c]
    converted = round(amount * rate, 2)
    return {
        "from": from_c,
        "to": to_c,
        "amount": amount,
        "converted": converted,
        "rate": rate,
        "message": f"{amount} {from_c} = {converted} {to_c}",
    }


# === TIP CALCULATOR ===

@router.get("/tip/{bill_amount}")
async def calculate_tip(bill_amount: float, tip_percent: float = 18, split: int = 1):
    """Calculate tip and split the bill."""
    tip = bill_amount * (tip_percent / 100)
    total = bill_amount + tip
    per_person = total / split
    return {
        "bill": round(bill_amount, 2),
        "tip_percent": tip_percent,
        "tip_amount": round(tip, 2),
        "total": round(total, 2),
        "split": split,
        "per_person": round(per_person, 2),
        "message": f"Total: ${total:.2f}" + (f" (${per_person:.2f} per person)" if split > 1 else ""),
    }

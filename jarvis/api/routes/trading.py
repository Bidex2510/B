"""Trading bot API endpoints for the web dashboard."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _bot(request: Request):
    plugin = request.app.state.jarvis.brain.plugins.get("trading_bot")
    if plugin is None:
        raise HTTPException(status_code=503, detail="Trading plugin not loaded")
    return plugin._bot


@router.get("/status")
async def status(request: Request):
    """Full bot status: mode, positions, P&L, stats."""
    bot = _bot(request)

    if not bot.is_running:
        return {
            "running": False,
            "mode": "PAPER" if bot.is_paper_trading else "LIVE",
            "strategies": bot.active_strategies,
            "positions": [],
            "portfolio_value": 0.0,
            "buying_power": 0.0,
            "stats": {},
        }

    try:
        portfolio_value = bot._client.get_portfolio_value()
        buying_power = bot._client.get_buying_power()
        raw_positions = bot._client.get_positions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch state: {exc}")

    positions = []
    for symbol, pos in raw_positions.items():
        price = bot._client.get_current_price(symbol) or pos["average_buy_price"]
        qty = float(pos["quantity"])
        cost = float(pos["average_buy_price"])
        pnl_pct = (price - cost) / cost * 100 if cost else 0.0
        pnl_dollars = (price - cost) * qty
        meta = bot._positions.get(symbol)
        positions.append({
            "symbol": symbol,
            "quantity": qty,
            "avg_cost": round(cost, 2),
            "current_price": round(price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_dollars": round(pnl_dollars, 2),
            "strategy": meta["strategy"] if meta else None,
            "entry_date": meta["entry_date"] if meta else None,
        })

    stats = bot._risk.get_stats()

    return {
        "running": True,
        "frozen": stats["frozen"],
        "mode": "PAPER" if bot.is_paper_trading else "LIVE",
        "strategies": bot.active_strategies,
        "portfolio_value": round(portfolio_value, 2),
        "buying_power": round(buying_power, 2),
        "positions": positions,
        "stats": stats,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


@router.post("/start")
async def start(request: Request):
    bot = _bot(request)
    return {"message": bot.start()}


@router.post("/stop")
async def stop(request: Request):
    bot = _bot(request)
    return {"message": bot.stop()}


@router.post("/freeze")
async def freeze(request: Request):
    bot = _bot(request)
    return {"message": bot.freeze()}


@router.post("/unfreeze")
async def unfreeze(request: Request):
    bot = _bot(request)
    return {"message": bot.unfreeze()}


@router.get("/strategies")
async def strategies(request: Request):
    bot = _bot(request)
    return {"active": bot.active_strategies}

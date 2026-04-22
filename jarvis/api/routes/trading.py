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
        trade_data = bot.get_trade_stats()
        return {
            "running": False,
            "frozen": bot._risk.is_frozen,
            "mode": "PAPER" if bot.is_paper_trading else "LIVE",
            "strategies": bot.active_strategies,
            "positions": [],
            "portfolio_value": 0.0,
            "buying_power": 0.0,
            "stats": bot._risk.get_stats(),
            "trade_stats": trade_data["stats"],
            "by_strategy": trade_data["by_strategy"],
            "best_strategy": trade_data["best_strategy"],
            "equity_history": trade_data["equity_history"],
            "recent_trades": trade_data["recent_trades"],
            "concentration_alerts": [],
        }

    try:
        portfolio_value = bot._client.get_portfolio_value()
        buying_power = bot._client.get_buying_power()
        raw_positions = bot._client.get_positions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch state: {exc}")

    stop_pct = bot._risk.STOP_LOSS_PCT

    positions = []
    pos_for_concentration = {}
    for symbol, pos in raw_positions.items():
        price = bot._client.get_current_price(symbol) or pos["average_buy_price"]
        qty = float(pos["quantity"])
        cost = float(pos["average_buy_price"])
        pnl_pct = (price - cost) / cost * 100 if cost else 0.0
        pnl_dollars = (price - cost) * qty
        stop_price = bot._risk.stop_loss_price(cost)
        distance_to_stop = (price - stop_price) / price * 100 if price else 0.0
        meta = bot._positions.get(symbol)
        entry = meta.get("entry_date", "") if meta else ""
        age_mins = bot._positions.age_minutes(symbol)

        rec = {
            "symbol": symbol,
            "quantity": qty,
            "avg_cost": round(cost, 2),
            "current_price": round(price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_dollars": round(pnl_dollars, 2),
            "stop_price": stop_price,
            "distance_to_stop_pct": round(distance_to_stop, 2),
            "strategy": meta["strategy"] if meta else None,
            "entry_date": entry,
            "age_minutes": round(age_mins, 1),
        }
        positions.append(rec)
        pos_for_concentration[symbol] = {
            "quantity": qty,
            "current_price": price,
            "average_buy_price": cost,
        }

    concentration_alerts = bot._risk.concentration_alert(portfolio_value, pos_for_concentration)
    risk_stats = bot._risk.get_stats()
    trade_data = bot.get_trade_stats()

    return {
        "running": True,
        "frozen": risk_stats["frozen"],
        "mode": "PAPER" if bot.is_paper_trading else "LIVE",
        "strategies": bot.active_strategies,
        "portfolio_value": round(portfolio_value, 2),
        "buying_power": round(buying_power, 2),
        "positions": positions,
        "stats": risk_stats,
        "trade_stats": trade_data["stats"],
        "by_strategy": trade_data["by_strategy"],
        "best_strategy": trade_data["best_strategy"],
        "equity_history": trade_data["equity_history"][-50:],
        "recent_trades": trade_data["recent_trades"],
        "concentration_alerts": concentration_alerts,
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


@router.post("/close-all")
async def close_all(request: Request):
    bot = _bot(request)
    return {"message": bot.close_all()}


@router.get("/strategies")
async def strategies(request: Request):
    bot = _bot(request)
    return {"active": bot.active_strategies}

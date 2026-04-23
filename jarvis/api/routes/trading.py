"""Extended trading API endpoints: per-position controls, VIX, hunting list."""

from datetime import datetime

import yfinance as yf
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


def _bot(request: Request):
    plugin = request.app.state.jarvis.brain.plugins.get("trading_bot")
    if plugin is None:
        raise HTTPException(status_code=503, detail="Trading plugin not loaded")
    return plugin._bot


# ── Status (full snapshot) ────────────────────────────────────────────────────

@router.get("/status")
async def status(request: Request):
    bot = _bot(request)

    if not bot.is_running:
        td = bot.get_trade_stats()
        return {
            "running": False, "frozen": bot._risk.is_frozen,
            "mode": "PAPER" if bot.is_paper_trading else "LIVE",
            "strategies": bot.active_strategies,
            "positions": [], "portfolio_value": 0.0, "buying_power": 0.0,
            "stats": bot._risk.get_stats(),
            "trade_stats": td["stats"], "by_strategy": td["by_strategy"],
            "best_strategy": td["best_strategy"],
            "equity_history": td["equity_history"],
            "recent_trades": td["recent_trades"],
            "concentration_alerts": [], "hunting": [],
            "session_start": bot._session_start_iso,
        }

    try:
        portfolio_value = bot._client.get_portfolio_value()
        buying_power = bot._client.get_buying_power()
        raw_positions = bot._client.get_positions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    positions = []
    pos_for_conc = {}
    for symbol, pos in raw_positions.items():
        price = bot._client.get_current_price(symbol) or pos["average_buy_price"]
        qty = float(pos["quantity"])
        cost = float(pos["average_buy_price"])
        pnl_pct = (price - cost) / cost * 100 if cost else 0.0
        pnl_dollars = (price - cost) * qty
        stop_price = bot._risk.stop_loss_price(cost)
        dist_to_stop = (price - stop_price) / price * 100 if price else 0.0
        meta = bot._positions.get(symbol)
        age = bot._positions.age_minutes(symbol)
        scalp_target = ((price - cost) / cost * 100) / 0.5 * 100 if cost else 0  # % toward 0.5% target

        rec = {
            "symbol": symbol, "quantity": qty,
            "avg_cost": round(cost, 2), "current_price": round(price, 2),
            "pnl_pct": round(pnl_pct, 2), "pnl_dollars": round(pnl_dollars, 2),
            "stop_price": stop_price,
            "distance_to_stop_pct": round(dist_to_stop, 2),
            "scalp_target_pct": max(0.0, min(100.0, round(scalp_target, 1))),
            "strategy": meta["strategy"] if meta else None,
            "entry_date": meta.get("entry_date", "") if meta else "",
            "age_minutes": round(age, 1),
        }
        positions.append(rec)
        pos_for_conc[symbol] = {"quantity": qty, "current_price": price, "average_buy_price": cost}

    concentration_alerts = bot._risk.concentration_alert(portfolio_value, pos_for_conc)
    risk_stats = bot._risk.get_stats()
    td = bot.get_trade_stats()

    return {
        "running": True, "frozen": risk_stats["frozen"],
        "mode": "PAPER" if bot.is_paper_trading else "LIVE",
        "strategies": bot.active_strategies,
        "portfolio_value": round(portfolio_value, 2),
        "buying_power": round(buying_power, 2),
        "positions": positions,
        "stats": risk_stats,
        "trade_stats": td["stats"], "by_strategy": td["by_strategy"],
        "best_strategy": td["best_strategy"],
        "equity_history": td["equity_history"][-100:],
        "recent_trades": td["recent_trades"],
        "concentration_alerts": concentration_alerts,
        "hunting": bot._last_scan_symbols,
        "session_start": bot._session_start_iso,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


# ── Bot controls ──────────────────────────────────────────────────────────────

@router.post("/start")
async def start(request: Request):
    return {"message": _bot(request).start()}

@router.post("/stop")
async def stop(request: Request):
    return {"message": _bot(request).stop()}

@router.post("/freeze")
async def freeze(request: Request):
    return {"message": _bot(request).freeze()}

@router.post("/unfreeze")
async def unfreeze(request: Request):
    return {"message": _bot(request).unfreeze()}

@router.post("/close-all")
async def close_all(request: Request):
    return {"message": _bot(request).close_all()}

@router.get("/strategies")
async def strategies(request: Request):
    return {"active": _bot(request).active_strategies}


# ── Per-position controls ─────────────────────────────────────────────────────

@router.post("/close-position/{symbol}")
async def close_position(symbol: str, request: Request):
    bot = _bot(request)
    positions = bot._client.get_positions()
    if symbol not in positions:
        raise HTTPException(status_code=404, detail=f"{symbol} not in positions")
    pos = positions[symbol]
    price = bot._client.get_current_price(symbol) or pos["average_buy_price"]
    bot._execute_sell(symbol, int(float(pos["quantity"])), price, "manual: single close")
    return {"message": f"Closing {symbol} at ${price:.2f}"}


class ScaleRequest(BaseModel):
    pct: float  # 0.25 / 0.50 / 0.75


@router.post("/scale-out/{symbol}")
async def scale_out(symbol: str, req: ScaleRequest, request: Request):
    bot = _bot(request)
    positions = bot._client.get_positions()
    if symbol not in positions:
        raise HTTPException(status_code=404, detail=f"{symbol} not found")
    pos = positions[symbol]
    qty = float(pos["quantity"])
    sell_shares = max(1, int(qty * req.pct))
    price = bot._client.get_current_price(symbol) or pos["average_buy_price"]
    bot._execute_sell(symbol, sell_shares, price, f"manual: scale out {req.pct:.0%}")
    return {"message": f"Scaling out {sell_shares} shares ({req.pct:.0%}) of {symbol} at ${price:.2f}"}


@router.post("/break-even/{symbol}")
async def break_even(symbol: str, request: Request):
    """Move the stop-loss to the entry price (break-even stop)."""
    bot = _bot(request)
    meta = bot._positions.get(symbol)
    if not meta:
        raise HTTPException(status_code=404, detail=f"No metadata for {symbol}")
    entry = meta["entry_price"]
    # Override the stop in risk manager by forcing peak = entry (trailing stop fires at entry)
    bot._risk._position_peaks[symbol] = entry / (1 + bot._risk.TRAILING_STOP_PCT)
    return {"message": f"Break-even stop set for {symbol} at ${entry:.2f}"}


# ── Goal management ───────────────────────────────────────────────────────────

class GoalRequest(BaseModel):
    goal: float

@router.post("/set-goal")
async def set_goal(req: GoalRequest, request: Request):
    bot = _bot(request)
    bot._daily_goal = req.goal
    return {"message": f"Daily goal set to ${req.goal:,.2f}"}

@router.get("/goal")
async def get_goal(request: Request):
    bot = _bot(request)
    return {"goal": getattr(bot, "_daily_goal", 0.0)}


# ── Market data (free, yfinance) ──────────────────────────────────────────────

@router.get("/vix")
async def vix():
    try:
        df = yf.Ticker("^VIX").history(period="1d", interval="1m")
        val = float(df["Close"].iloc[-1]) if not df.empty else None
        level = "QUIET" if val and val < 15 else "ACTIVE" if val and val < 25 else "EXTREME"
        return {"vix": round(val, 2) if val else None, "level": level}
    except Exception:
        return {"vix": None, "level": "UNKNOWN"}


# ── Backtester ───────────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    strategy: str  # "day", "scalp", etc.
    symbol: str    # "AAPL", "SPY", etc.
    days: int = 30  # lookback period
    initial_capital: float = 10000


@router.post("/backtest")
async def backtest(req: BacktestRequest, request: Request):
    plugin = request.app.state.jarvis.brain.plugins.get("trading_bot")
    if plugin is None:
        raise HTTPException(status_code=503, detail="Trading plugin not loaded")

    from jarvis.plugins.trading.backtester import BacktesterEngine
    backtester = BacktesterEngine(plugin._bot.strategy_manager)
    result = backtester.backtest(req.strategy, req.symbol, req.days, req.initial_capital)
    return result

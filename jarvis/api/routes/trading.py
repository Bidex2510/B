"""Extended trading API endpoints: per-position controls, VIX, hunting list."""

import os
from datetime import datetime

import yfinance as yf
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

# In-memory custom price alerts store
_price_alerts: list[dict] = []


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


# ── Market Indicators ────────────────────────────────────────────────────────

@router.get("/market-indicators")
async def market_indicators():
    symbols = {"SPY": "S&P 500", "QQQ": "Nasdaq", "IWM": "Russell 2000",
               "DIA": "Dow Jones", "GLD": "Gold", "TLT": "Bonds", "UUP": "USD"}
    results = []
    for sym, label in symbols.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev = float(hist["Close"].iloc[-2])
                curr = float(hist["Close"].iloc[-1])
                chg = (curr - prev) / prev * 100
                results.append({"symbol": sym, "label": label,
                                 "price": round(curr, 2), "change_pct": round(chg, 2)})
        except Exception:
            pass
    return {"indicators": results, "timestamp": datetime.now().isoformat(timespec="seconds")}


# ── News Feed ────────────────────────────────────────────────────────────────

@router.get("/news/{symbol}")
async def news_for_symbol(symbol: str):
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return {"articles": [], "error": "NEWS_API_KEY not set"}
    import httpx
    try:
        res = httpx.get(
            "https://newsapi.org/v2/everything",
            params={"q": symbol, "pageSize": 5, "sortBy": "publishedAt", "apiKey": api_key},
            timeout=8,
        )
        data = res.json()
        articles = [{"title": a["title"], "source": a["source"]["name"],
                     "url": a["url"], "published": a["publishedAt"][:10]}
                    for a in data.get("articles", [])[:5]]
        return {"articles": articles}
    except Exception as e:
        return {"articles": [], "error": str(e)}


# ── Earnings Calendar ────────────────────────────────────────────────────────

@router.get("/earnings")
async def earnings(request: Request):
    bot = _bot(request)
    from jarvis.plugins.trading.scanner import get_watchlist
    symbols = get_watchlist()[:30]
    upcoming = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            cal = t.calendar
            if cal is not None and not cal.empty:
                date_val = cal.columns[0] if hasattr(cal, 'columns') else None
                if date_val:
                    upcoming.append({"symbol": sym, "date": str(date_val)[:10]})
        except Exception:
            pass
    upcoming.sort(key=lambda x: x["date"])
    return {"earnings": upcoming[:20]}


# ── Risk Settings ────────────────────────────────────────────────────────────

class RiskSettingsRequest(BaseModel):
    daily_max_loss_pct: float | None = None
    stop_loss_pct: float | None = None
    trailing_stop_pct: float | None = None
    max_position_pct: float | None = None
    max_daily_trades: int | None = None


@router.get("/risk-settings")
async def get_risk_settings(request: Request):
    r = _bot(request)._risk
    return {
        "daily_max_loss_pct": r.DAILY_MAX_LOSS_PCT,
        "stop_loss_pct": r.STOP_LOSS_PCT,
        "trailing_stop_pct": r.TRAILING_STOP_PCT,
        "max_position_pct": r.MAX_POSITION_PCT,
        "max_daily_trades": r.MAX_DAILY_TRADES,
    }


@router.post("/risk-settings")
async def update_risk_settings(req: RiskSettingsRequest, request: Request):
    r = _bot(request)._risk
    changed = []
    if req.daily_max_loss_pct is not None:
        r.DAILY_MAX_LOSS_PCT = req.daily_max_loss_pct
        changed.append(f"daily_max_loss_pct={req.daily_max_loss_pct:.1%}")
    if req.stop_loss_pct is not None:
        r.STOP_LOSS_PCT = req.stop_loss_pct
        changed.append(f"stop_loss_pct={req.stop_loss_pct:.1%}")
    if req.trailing_stop_pct is not None:
        r.TRAILING_STOP_PCT = req.trailing_stop_pct
        changed.append(f"trailing_stop_pct={req.trailing_stop_pct:.1%}")
    if req.max_position_pct is not None:
        r.MAX_POSITION_PCT = req.max_position_pct
        changed.append(f"max_position_pct={req.max_position_pct:.1%}")
    if req.max_daily_trades is not None:
        r.MAX_DAILY_TRADES = req.max_daily_trades
        changed.append(f"max_daily_trades={req.max_daily_trades}")
    return {"message": "Updated: " + ", ".join(changed) if changed else "No changes"}


# ── Watchlist ────────────────────────────────────────────────────────────────

@router.get("/watchlist")
async def get_watchlist_route(request: Request):
    from jarvis.plugins.trading.scanner import get_watchlist
    return {"symbols": get_watchlist()}


class WatchlistRequest(BaseModel):
    symbol: str


@router.post("/watchlist/add")
async def watchlist_add(req: WatchlistRequest, request: Request):
    from jarvis.plugins.trading import scanner
    sym = req.symbol.upper().strip()
    wl = scanner.get_watchlist()
    if sym not in wl:
        os.environ["TRADING_WATCHLIST"] = ",".join(wl + [sym])
        return {"message": f"Added {sym} to watchlist"}
    return {"message": f"{sym} already in watchlist"}


@router.post("/watchlist/remove")
async def watchlist_remove(req: WatchlistRequest, request: Request):
    from jarvis.plugins.trading import scanner
    sym = req.symbol.upper().strip()
    wl = scanner.get_watchlist()
    if sym in wl:
        wl.remove(sym)
        os.environ["TRADING_WATCHLIST"] = ",".join(wl)
        return {"message": f"Removed {sym} from watchlist"}
    return {"message": f"{sym} not in watchlist"}


# ── Strategy Toggles ─────────────────────────────────────────────────────────

@router.post("/strategy/{name}/toggle")
async def toggle_strategy(name: str, request: Request):
    bot = _bot(request)
    sm = bot.strategy_manager
    if name not in sm.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")
    if name in sm.enabled:
        sm.enabled.discard(name)
        return {"message": f"Strategy {name} disabled", "enabled": list(sm.enabled)}
    else:
        sm.enabled.add(name)
        return {"message": f"Strategy {name} enabled", "enabled": list(sm.enabled)}


@router.get("/strategy/status")
async def strategy_status(request: Request):
    bot = _bot(request)
    sm = bot.strategy_manager
    all_strats = list(sm.strategies.keys())
    enabled = list(sm.enabled)
    return {"all": all_strats, "enabled": enabled}


# ── Custom Price Alerts ──────────────────────────────────────────────────────

class AlertRequest(BaseModel):
    symbol: str
    price: float
    direction: str  # "above" or "below"


@router.get("/alerts")
async def get_alerts():
    return {"alerts": _price_alerts}


@router.post("/alerts/add")
async def add_alert(req: AlertRequest):
    _price_alerts.append({
        "symbol": req.symbol.upper(),
        "price": req.price,
        "direction": req.direction,
        "created": datetime.now().isoformat(timespec="seconds"),
        "triggered": False,
    })
    return {"message": f"Alert: {req.symbol.upper()} {req.direction} ${req.price:.2f}"}


@router.delete("/alerts/{idx}")
async def delete_alert(idx: int):
    if 0 <= idx < len(_price_alerts):
        removed = _price_alerts.pop(idx)
        return {"message": f"Alert removed: {removed['symbol']}"}
    raise HTTPException(status_code=404, detail="Alert not found")


# ── Performance by Hour / Day ────────────────────────────────────────────────

@router.get("/performance/hours")
async def performance_by_hour(request: Request):
    bot = _bot(request)
    trades = bot._trade_log.recent_trades(500)
    hour_data = {}
    for t in trades:
        try:
            h = datetime.fromisoformat(t.get("exit_date", "")).hour
            hour_data.setdefault(h, {"wins": 0, "losses": 0, "pnl": 0})
            pnl = t.get("pnl", 0)
            hour_data[h]["pnl"] += pnl
            if pnl > 0:
                hour_data[h]["wins"] += 1
            else:
                hour_data[h]["losses"] += 1
        except Exception:
            pass
    return {"by_hour": {str(h): v for h, v in sorted(hour_data.items())}}


@router.get("/performance/days")
async def performance_by_day(request: Request):
    bot = _bot(request)
    trades = bot._trade_log.recent_trades(500)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_data = {}
    for t in trades:
        try:
            d = datetime.fromisoformat(t.get("exit_date", "")).weekday()
            day_data.setdefault(d, {"wins": 0, "losses": 0, "pnl": 0})
            pnl = t.get("pnl", 0)
            day_data[d]["pnl"] += pnl
            if pnl > 0:
                day_data[d]["wins"] += 1
            else:
                day_data[d]["losses"] += 1
        except Exception:
            pass
    return {"by_day": {day_names[d]: v for d, v in sorted(day_data.items())}}


# ── Telegram Test ────────────────────────────────────────────────────────────

@router.post("/telegram/test")
async def telegram_test(request: Request):
    bot = _bot(request)
    bot._notifier.send("✅ Jarvis Trading Bot connected! Test message from dashboard.")
    return {"message": "Test message sent to Telegram"}


# ── Fear & Greed Index (CNN, free) ───────────────────────────────────────────

@router.get("/fear-greed")
async def fear_greed():
    import httpx
    try:
        res = httpx.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        data = res.json()
        score = data["fear_and_greed"]["score"]
        rating = data["fear_and_greed"]["rating"]
        return {"score": round(score, 1), "rating": rating.replace("_", " ").title()}
    except Exception:
        return {"score": None, "rating": "Unknown"}


# ── Pre-Market Movers ────────────────────────────────────────────────────────

@router.get("/premarket")
async def premarket_movers():
    from jarvis.plugins.trading.scanner import get_watchlist
    symbols = get_watchlist()[:20]
    movers = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            pre = getattr(info, "pre_market_price", None)
            prev = getattr(info, "previous_close", None)
            if pre and prev:
                chg = (pre - prev) / prev * 100
                movers.append({"symbol": sym, "pre_price": round(pre, 2),
                                "change_pct": round(chg, 2), "prev_close": round(prev, 2)})
        except Exception:
            pass
    movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return {"movers": movers[:10]}


# ── Streaks ──────────────────────────────────────────────────────────────────

@router.get("/streaks")
async def streaks(request: Request):
    trades = _bot(request)._trade_log.recent_trades(200)
    if not trades:
        return {"win_streak": 0, "loss_streak": 0, "max_win_streak": 0, "max_loss_streak": 0}
    current_win = current_loss = max_win = max_loss = 0
    for t in reversed(trades):
        if t.get("pnl", 0) > 0:
            current_win += 1
            current_loss = 0
        else:
            current_loss += 1
            current_win = 0
        max_win = max(max_win, current_win)
        max_loss = max(max_loss, current_loss)
    return {"win_streak": current_win, "loss_streak": current_loss,
            "max_win_streak": max_win, "max_loss_streak": max_loss}


# ── Drawdown ─────────────────────────────────────────────────────────────────

@router.get("/drawdown")
async def drawdown_data(request: Request):
    import pandas as pd
    history = _bot(request)._trade_log.equity_history()
    if len(history) < 2:
        return {"max_drawdown": 0, "current_drawdown": 0, "curve": []}
    vals = pd.Series([h["v"] for h in history])
    running_max = vals.expanding().max()
    dd = ((vals - running_max) / running_max * 100).round(2)
    return {
        "max_drawdown": float(dd.min()),
        "current_drawdown": float(dd.iloc[-1]),
        "curve": dd.tolist(),
    }


# ── Kelly Criterion ──────────────────────────────────────────────────────────

@router.get("/kelly")
async def kelly(request: Request):
    s = _bot(request)._trade_log.stats()
    w = s.get("win_rate", 0) / 100
    avg_win = s.get("avg_win", 0)
    avg_loss = s.get("avg_loss", 1)
    if avg_loss == 0 or w == 0:
        return {"kelly_pct": 0, "half_kelly_pct": 0}
    b = avg_win / avg_loss  # win/loss ratio
    k = (b * w - (1 - w)) / b
    k = max(0, min(k, 0.5))  # cap at 50%
    return {"kelly_pct": round(k * 100, 1), "half_kelly_pct": round(k * 50, 1),
            "win_rate": round(w * 100, 1), "win_loss_ratio": round(b, 2)}


# ── Monte Carlo Simulation ────────────────────────────────────────────────────

@router.get("/monte-carlo")
async def monte_carlo(request: Request):
    import random
    trades = _bot(request)._trade_log.recent_trades(200)
    if len(trades) < 10:
        return {"error": "Need at least 10 trades for simulation"}
    pnls = [t.get("pnl", 0) for t in trades]
    capital = _bot(request)._client.get_portfolio_value() if _bot(request).is_running else 10000
    simulations = 200
    horizon = 20
    paths = []
    for _ in range(simulations):
        path = [capital]
        for _ in range(horizon):
            path.append(path[-1] + random.choice(pnls))
        paths.append(path[-1])
    paths.sort()
    return {
        "initial": capital,
        "worst_5pct": round(paths[int(simulations * 0.05)], 2),
        "median": round(paths[simulations // 2], 2),
        "best_5pct": round(paths[int(simulations * 0.95)], 2),
        "prob_profit": round(len([p for p in paths if p > capital]) / simulations * 100, 1),
    }


# ── Calendar P&L (for heatmap) ────────────────────────────────────────────────

@router.get("/calendar-pnl")
async def calendar_pnl(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    cal: dict[str, float] = {}
    for t in trades:
        try:
            day = t.get("exit_date", "")[:10]
            cal[day] = round(cal.get(day, 0) + t.get("pnl", 0), 2)
        except Exception:
            pass
    return {"by_date": cal}


# ── Trade Journal ─────────────────────────────────────────────────────────────

_journal: list[dict] = []


class JournalEntry(BaseModel):
    note: str
    symbol: str = ""
    rating: int = 3  # 1-5


@router.get("/journal")
async def get_journal():
    return {"entries": list(reversed(_journal[-50:]))}


@router.post("/journal/add")
async def add_journal(req: JournalEntry):
    _journal.append({
        "note": req.note,
        "symbol": req.symbol.upper(),
        "rating": req.rating,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    return {"message": "Note saved"}


# ── Earnings Calendar ────────────────────────────────────────────────────────

@router.get("/earnings")
async def earnings(request: Request):
    from jarvis.plugins.trading.scanner import get_watchlist
    symbols = get_watchlist()[:30]
    upcoming = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            cal = t.calendar
            if cal is not None and not cal.empty:
                date_val = cal.columns[0] if hasattr(cal, 'columns') else None
                if date_val:
                    upcoming.append({"symbol": sym, "date": str(date_val)[:10]})
        except Exception:
            pass
    upcoming.sort(key=lambda x: x["date"])
    return {"earnings": upcoming[:20]}

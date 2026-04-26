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


# ── Candlestick Price History ─────────────────────────────────────────────────

@router.get("/price-history/{symbol}")
async def price_history(symbol: str, period: str = "5d", interval: str = "5m"):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df.empty:
            return {"error": "No data"}
        bars = []
        for ts, row in df.iterrows():
            bars.append({
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return {"symbol": symbol, "bars": bars}
    except Exception as e:
        return {"error": str(e)}


# ── Sector Rotation ──────────────────────────────────────────────────────────

@router.get("/sector-rotation")
async def sector_rotation():
    sectors = {
        "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
        "XLV": "Healthcare", "XLY": "Cons Discretionary", "XLP": "Cons Staples",
        "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
        "XLRE": "Real Estate", "XLC": "Communication",
    }
    results = []
    for sym, label in sectors.items():
        try:
            df = yf.Ticker(sym).history(period="5d")
            if len(df) >= 2:
                prev = float(df["Close"].iloc[0])
                curr = float(df["Close"].iloc[-1])
                chg = (curr - prev) / prev * 100
                results.append({"symbol": sym, "name": label, "change_5d": round(chg, 2)})
        except Exception:
            pass
    results.sort(key=lambda x: x["change_5d"], reverse=True)
    return {"sectors": results}


# ── Risk On / Off Indicator ──────────────────────────────────────────────────

@router.get("/risk-on-off")
async def risk_on_off():
    """Compare SPY (risk-on) vs TLT (risk-off / bonds) momentum."""
    try:
        spy = yf.Ticker("SPY").history(period="10d")
        tlt = yf.Ticker("TLT").history(period="10d")
        if len(spy) < 2 or len(tlt) < 2:
            return {"signal": "UNKNOWN"}
        spy_chg = (spy["Close"].iloc[-1] - spy["Close"].iloc[0]) / spy["Close"].iloc[0] * 100
        tlt_chg = (tlt["Close"].iloc[-1] - tlt["Close"].iloc[0]) / tlt["Close"].iloc[0] * 100
        if spy_chg > tlt_chg + 1:
            signal = "RISK ON"
        elif tlt_chg > spy_chg + 1:
            signal = "RISK OFF"
        else:
            signal = "NEUTRAL"
        return {"signal": signal, "spy_10d": round(float(spy_chg), 2),
                "tlt_10d": round(float(tlt_chg), 2)}
    except Exception:
        return {"signal": "UNKNOWN"}


# ── Symbol Info ──────────────────────────────────────────────────────────────

@router.get("/symbol-info/{symbol}")
async def symbol_info(symbol: str):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "symbol": symbol,
            "name": info.get("shortName", symbol),
            "sector": info.get("sector", "—"),
            "industry": info.get("industry", "—"),
            "market_cap": info.get("marketCap", 0),
            "pe": info.get("trailingPE", None),
            "dividend_yield": info.get("dividendYield", None),
            "52w_high": info.get("fiftyTwoWeekHigh", None),
            "52w_low": info.get("fiftyTwoWeekLow", None),
            "avg_volume": info.get("averageVolume", None),
            "beta": info.get("beta", None),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Trade Quality Grader ─────────────────────────────────────────────────────

@router.get("/trade-quality")
async def trade_quality(request: Request):
    trades = _bot(request)._trade_log.recent_trades(50)
    graded = []
    for t in trades:
        pnl_pct = t.get("pnl_pct", 0)
        if pnl_pct > 2.0:
            grade = "A+"
        elif pnl_pct > 1.0:
            grade = "A"
        elif pnl_pct > 0.5:
            grade = "B"
        elif pnl_pct > 0:
            grade = "C"
        elif pnl_pct > -0.5:
            grade = "D"
        else:
            grade = "F"
        graded.append({**t, "grade": grade})
    return {"graded": graded}


# ── R:R Ratio (Risk:Reward per position) ─────────────────────────────────────

@router.get("/risk-reward")
async def risk_reward(request: Request):
    bot = _bot(request)
    if not bot.is_running:
        return {"positions": []}
    raw = bot._client.get_positions()
    out = []
    for sym, pos in raw.items():
        try:
            cost = float(pos["average_buy_price"])
            current = bot._client.get_current_price(sym) or cost
            stop = bot._risk.stop_loss_price(cost)
            risk = abs(current - stop)
            meta = bot._positions.get(sym)
            strat = meta["strategy"] if meta else "day"
            target_pct = 0.005 if strat == "scalp" else 0.02
            target_price = cost * (1 + target_pct)
            reward = abs(target_price - current)
            rr = round(reward / risk, 2) if risk > 0 else 0
            out.append({"symbol": sym, "rr": rr, "risk": round(risk, 2), "reward": round(reward, 2)})
        except Exception:
            pass
    return {"positions": out}


# ── Live Ticker Tape ─────────────────────────────────────────────────────────

@router.get("/ticker-tape")
async def ticker_tape():
    symbols = ["SPY", "QQQ", "IWM", "DIA", "NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "META", "GOOGL", "AMD"]
    tape = []
    for sym in symbols:
        try:
            df = yf.Ticker(sym).history(period="2d")
            if len(df) >= 2:
                prev = float(df["Close"].iloc[-2])
                curr = float(df["Close"].iloc[-1])
                chg = (curr - prev) / prev * 100
                tape.append({"symbol": sym, "price": round(curr, 2), "change": round(chg, 2)})
        except Exception:
            pass
    return {"tape": tape}


# ── Strategy Parameters Viewer ───────────────────────────────────────────────

@router.get("/strategy/{name}/params")
async def strategy_params(name: str, request: Request):
    s = _bot(request).strategy_manager.get(name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")
    return {
        "name": s.name,
        "bar_interval": s.bar_interval,
        "bar_period": s.bar_period,
        "min_score_to_buy": s.min_score_to_buy,
        "target_hold_days": s.target_hold_days,
        "intraday": s.intraday,
    }


class StrategyParamsRequest(BaseModel):
    min_score_to_buy: float | None = None


@router.post("/strategy/{name}/params")
async def update_strategy_params(name: str, req: StrategyParamsRequest, request: Request):
    s = _bot(request).strategy_manager.get(name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")
    if req.min_score_to_buy is not None:
        s.min_score_to_buy = req.min_score_to_buy
    return {"message": f"{name} params updated"}


# ── Symbol Performance Leaderboard ───────────────────────────────────────────

@router.get("/symbol-leaderboard")
async def symbol_leaderboard(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    by_sym: dict = {}
    for t in trades:
        sym = t.get("symbol", "?")
        by_sym.setdefault(sym, {"trades": 0, "pnl": 0.0, "wins": 0})
        by_sym[sym]["trades"] += 1
        by_sym[sym]["pnl"] = round(by_sym[sym]["pnl"] + t.get("pnl", 0), 2)
        if t.get("pnl", 0) > 0:
            by_sym[sym]["wins"] += 1
    out = [{"symbol": s, **v, "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0} for s, v in by_sym.items()]
    out.sort(key=lambda x: x["pnl"], reverse=True)
    return {"top_5": out[:5], "bottom_5": out[-5:][::-1] if len(out) > 5 else [], "all": out}


# ── Hold Time Distribution ───────────────────────────────────────────────────

@router.get("/hold-time-stats")
async def hold_time_stats(request: Request):
    trades = _bot(request)._trade_log.recent_trades(200)
    durations = []
    for t in trades:
        try:
            entry = datetime.fromisoformat(t.get("entry_date", ""))
            exit_ = datetime.fromisoformat(t.get("exit_date", ""))
            durations.append((exit_ - entry).total_seconds() / 60)
        except Exception:
            pass
    if not durations:
        return {"avg": 0, "min": 0, "max": 0, "count": 0}
    return {"avg": round(sum(durations)/len(durations), 1),
            "min": round(min(durations), 1), "max": round(max(durations), 1),
            "count": len(durations)}


# ── Win Rate over Time (rolling 10) ──────────────────────────────────────────

@router.get("/rolling-winrate")
async def rolling_winrate(request: Request):
    trades = list(reversed(_bot(request)._trade_log.recent_trades(200)))
    window = 10
    rolling = []
    for i in range(window, len(trades) + 1):
        slice_ = trades[i-window:i]
        wr = sum(1 for t in slice_ if t.get("pnl", 0) > 0) / window * 100
        rolling.append(round(wr, 1))
    return {"rolling": rolling}


# ── Best / Worst Trades ──────────────────────────────────────────────────────

@router.get("/best-worst-trades")
async def best_worst(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    if not trades:
        return {"best": [], "worst": []}
    sorted_trades = sorted(trades, key=lambda t: t.get("pnl", 0))
    return {"best": sorted_trades[-5:][::-1], "worst": sorted_trades[:5]}


# ── Benchmark vs SPY ─────────────────────────────────────────────────────────

@router.get("/benchmark")
async def benchmark(request: Request):
    bot = _bot(request)
    history = bot._trade_log.equity_history()
    if len(history) < 2:
        return {"bot_return": 0, "spy_return": 0, "alpha": 0}
    start_t = history[0]["t"][:10]
    end_t = history[-1]["t"][:10]
    bot_ret = (history[-1]["v"] - history[0]["v"]) / history[0]["v"] * 100 if history[0]["v"] else 0
    try:
        spy = yf.Ticker("SPY").history(start=start_t, end=end_t)
        if len(spy) >= 2:
            spy_ret = (spy["Close"].iloc[-1] - spy["Close"].iloc[0]) / spy["Close"].iloc[0] * 100
        else:
            spy_ret = 0
    except Exception:
        spy_ret = 0
    return {"bot_return": round(bot_ret, 2), "spy_return": round(float(spy_ret), 2),
            "alpha": round(bot_ret - float(spy_ret), 2)}


# ── Server Health ────────────────────────────────────────────────────────────

import time
_server_start = time.time()


@router.get("/health")
async def health(request: Request):
    bot = _bot(request)
    uptime = time.time() - _server_start
    h = int(uptime // 3600)
    m = int((uptime % 3600) // 60)
    return {
        "uptime_seconds": int(uptime),
        "uptime_human": f"{h}h {m}m",
        "bot_running": bot.is_running,
        "scan_count": getattr(bot, "_scan_count", 0),
        "last_scan_iso": getattr(bot, "_last_scan_iso", ""),
    }


# ── P&L Distribution (Histogram) ─────────────────────────────────────────────

@router.get("/pnl-distribution")
async def pnl_distribution(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    if not trades:
        return {"buckets": [], "counts": []}
    pnls = [t.get("pnl_pct", 0) for t in trades]
    edges = [-5, -3, -2, -1, -0.5, 0, 0.5, 1, 2, 3, 5]
    counts = [0] * (len(edges) - 1)
    for p in pnls:
        for i in range(len(edges) - 1):
            if edges[i] <= p < edges[i+1]:
                counts[i] += 1
                break
        else:
            if p >= edges[-1]:
                counts[-1] += 1
            else:
                counts[0] += 1
    labels = [f"{edges[i]:+g}% to {edges[i+1]:+g}%" for i in range(len(edges) - 1)]
    return {"buckets": labels, "counts": counts}


# ── Tax Report (long/short term split) ───────────────────────────────────────

@router.get("/tax-report")
async def tax_report(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    short_term = []
    long_term = []
    for t in trades:
        try:
            entry = datetime.fromisoformat(t.get("entry_date", ""))
            exit_ = datetime.fromisoformat(t.get("exit_date", ""))
            days_held = (exit_ - entry).days
            row = {
                "symbol": t.get("symbol"),
                "entry": entry.date().isoformat(),
                "exit": exit_.date().isoformat(),
                "days_held": days_held,
                "pnl": t.get("pnl", 0),
            }
            if days_held >= 365:
                long_term.append(row)
            else:
                short_term.append(row)
        except Exception:
            pass
    return {
        "short_term": short_term,
        "long_term": long_term,
        "short_term_total": round(sum(r["pnl"] for r in short_term), 2),
        "long_term_total": round(sum(r["pnl"] for r in long_term), 2),
    }


# ── Bulk Watchlist Import ────────────────────────────────────────────────────

class BulkWatchlistRequest(BaseModel):
    symbols: list[str]


@router.post("/watchlist/import")
async def watchlist_import(req: BulkWatchlistRequest):
    from jarvis.plugins.trading import scanner
    cur = set(scanner.get_watchlist())
    added = []
    for s in req.symbols:
        sym = s.upper().strip()
        if sym and sym not in cur:
            cur.add(sym)
            added.append(sym)
    os.environ["TRADING_WATCHLIST"] = ",".join(sorted(cur))
    return {"message": f"Added {len(added)} symbols", "added": added}


# ── Audit Log ────────────────────────────────────────────────────────────────

_audit_log: list[dict] = []


def _log_audit(action: str, detail: str = ""):
    _audit_log.append({"ts": datetime.now().isoformat(timespec="seconds"),
                        "action": action, "detail": detail})
    if len(_audit_log) > 200:
        _audit_log.pop(0)


@router.get("/audit-log")
async def audit_log():
    return {"log": list(reversed(_audit_log))}


# ── Position Freeze (block bot from closing specific symbol) ─────────────────

_frozen_positions: set[str] = set()


@router.post("/position/freeze/{symbol}")
async def freeze_position(symbol: str):
    sym = symbol.upper()
    if sym in _frozen_positions:
        _frozen_positions.discard(sym)
        _log_audit("position_unfreeze", sym)
        return {"message": f"{sym} unfrozen", "frozen": False}
    _frozen_positions.add(sym)
    _log_audit("position_freeze", sym)
    return {"message": f"{sym} frozen (bot won't auto-close)", "frozen": True}


@router.get("/position/frozen-list")
async def frozen_positions():
    return {"frozen": list(_frozen_positions)}


# ── Holiday / Market-Hours Status ────────────────────────────────────────────

@router.get("/market-status")
async def market_status():
    import pytz
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    weekday = now.weekday()  # 0=Mon .. 6=Sun
    # rough US market holidays (fixed dates only)
    holidays_md = {(1, 1), (1, 15), (2, 19), (5, 27), (6, 19),
                   (7, 4), (9, 2), (11, 28), (12, 25)}
    is_holiday = (now.month, now.day) in holidays_md
    is_weekend = weekday >= 5
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    is_open = (not is_weekend) and (not is_holiday) and (open_t <= now <= close_t)

    if is_holiday:
        status = "HOLIDAY"
    elif is_weekend:
        status = "WEEKEND"
    elif now < open_t:
        status = "PRE-MARKET"
    elif now > close_t:
        status = "AFTER-HOURS"
    else:
        status = "OPEN"

    secs_to_open = max(0, (open_t - now).total_seconds())
    secs_to_close = max(0, (close_t - now).total_seconds())
    return {
        "status": status, "is_open": is_open,
        "now_et": now.strftime("%Y-%m-%d %H:%M:%S"),
        "secs_to_open": int(secs_to_open),
        "secs_to_close": int(secs_to_close),
    }


# ── Symbol Sparkline (last 30 1-min bars) ────────────────────────────────────

@router.get("/sparkline/{symbol}")
async def sparkline(symbol: str):
    try:
        df = yf.Ticker(symbol).history(period="1d", interval="1m").tail(30)
        if df.empty:
            return {"closes": []}
        return {"closes": [round(float(c), 2) for c in df["Close"].tolist()]}
    except Exception:
        return {"closes": []}


# ── ATR (Average True Range) per symbol ──────────────────────────────────────

@router.get("/atr/{symbol}")
async def atr(symbol: str, period: int = 14):
    try:
        df = yf.Ticker(symbol).history(period="1mo", interval="1d")
        if len(df) < period:
            return {"atr": 0}
        tr = (df["High"] - df["Low"]).combine((df["High"] - df["Close"].shift(1)).abs(), max)
        tr = tr.combine((df["Low"] - df["Close"].shift(1)).abs(), max)
        atr_val = float(tr.tail(period).mean())
        return {"atr": round(atr_val, 2)}
    except Exception:
        return {"atr": 0}


# ── Trigger Manual Scan ──────────────────────────────────────────────────────

@router.post("/scan-now")
async def scan_now(request: Request):
    bot = _bot(request)
    if not bot.is_running:
        return {"message": "Bot not running, cannot scan"}
    try:
        # If bot exposes a scan method, call it
        if hasattr(bot, "_scan_once"):
            bot._scan_once()
            return {"message": "Manual scan triggered"}
    except Exception as e:
        return {"message": f"Scan error: {e}"}
    return {"message": "Scan request acknowledged (will run on next cycle)"}


# ── Pinned Symbols (server-side store) ───────────────────────────────────────

_pinned: set[str] = set()


@router.get("/pinned")
async def get_pinned():
    return {"pinned": list(_pinned)}


@router.post("/pinned/{symbol}")
async def toggle_pin(symbol: str):
    sym = symbol.upper()
    if sym in _pinned:
        _pinned.discard(sym)
        return {"pinned": False}
    _pinned.add(sym)
    return {"pinned": True}


# ── Market Breadth (rough via major ETFs) ────────────────────────────────────

@router.get("/breadth")
async def market_breadth():
    sectors = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"]
    advancing = 0
    declining = 0
    for s in sectors:
        try:
            df = yf.Ticker(s).history(period="2d")
            if len(df) >= 2:
                chg = df["Close"].iloc[-1] - df["Close"].iloc[-2]
                if chg > 0:
                    advancing += 1
                elif chg < 0:
                    declining += 1
        except Exception:
            pass
    total = advancing + declining
    breadth_pct = round(advancing / total * 100, 1) if total else 50
    if breadth_pct >= 70:
        signal = "STRONG"
    elif breadth_pct >= 55:
        signal = "BULLISH"
    elif breadth_pct >= 45:
        signal = "MIXED"
    elif breadth_pct >= 30:
        signal = "BEARISH"
    else:
        signal = "WEAK"
    return {"advancing": advancing, "declining": declining,
            "breadth_pct": breadth_pct, "signal": signal}


# ── Strategy Presets ─────────────────────────────────────────────────────────

class PresetRequest(BaseModel):
    preset: str  # "conservative" / "balanced" / "aggressive"


@router.post("/preset")
async def apply_preset(req: PresetRequest, request: Request):
    bot = _bot(request)
    r = bot._risk
    if req.preset == "conservative":
        r.MAX_POSITION_PCT = 0.05
        r.STOP_LOSS_PCT = -0.015
        r.TRAILING_STOP_PCT = -0.02
        r.DAILY_MAX_LOSS_PCT = -0.03
        for s in bot.strategy_manager.strategies.values():
            s.min_score_to_buy = max(0.7, s.min_score_to_buy + 0.05)
        msg = "Applied CONSERVATIVE preset"
    elif req.preset == "balanced":
        r.MAX_POSITION_PCT = 0.10
        r.STOP_LOSS_PCT = -0.02
        r.TRAILING_STOP_PCT = -0.03
        r.DAILY_MAX_LOSS_PCT = -0.05
        for s in bot.strategy_manager.strategies.values():
            s.min_score_to_buy = 0.62
        msg = "Applied BALANCED preset"
    elif req.preset == "aggressive":
        r.MAX_POSITION_PCT = 0.15
        r.STOP_LOSS_PCT = -0.03
        r.TRAILING_STOP_PCT = -0.04
        r.DAILY_MAX_LOSS_PCT = -0.08
        for s in bot.strategy_manager.strategies.values():
            s.min_score_to_buy = 0.55
        msg = "Applied AGGRESSIVE preset"
    else:
        return {"message": "Unknown preset"}
    _log_audit("preset_applied", req.preset)
    return {"message": msg}


# ── Earnings Warning for Held Positions ──────────────────────────────────────

@router.get("/earnings-warning")
async def earnings_warning(request: Request):
    bot = _bot(request)
    if not bot.is_running:
        return {"warnings": []}
    raw = bot._client.get_positions()
    warnings = []
    today = datetime.now().date()
    for sym in raw.keys():
        try:
            t = yf.Ticker(sym)
            cal = t.calendar
            if cal is not None and not cal.empty and hasattr(cal, "columns"):
                date_val = cal.columns[0]
                ed = datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()
                days_until = (ed - today).days
                if 0 <= days_until <= 3:
                    warnings.append({"symbol": sym, "earnings_date": ed.isoformat(),
                                       "days_until": days_until})
        except Exception:
            pass
    return {"warnings": warnings}


# ── Daily Streak (consecutive winning days) ──────────────────────────────────

@router.get("/daily-streak")
async def daily_streak(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    by_day: dict = {}
    for t in trades:
        try:
            d = t.get("exit_date", "")[:10]
            by_day[d] = by_day.get(d, 0) + t.get("pnl", 0)
        except Exception:
            pass
    days = sorted(by_day.keys())
    current_streak = 0
    for d in reversed(days):
        if by_day[d] > 0:
            current_streak += 1
        else:
            break
    max_streak = 0
    s = 0
    for d in days:
        if by_day[d] > 0:
            s += 1
            max_streak = max(max_streak, s)
        else:
            s = 0
    return {"current_streak": current_streak, "max_streak": max_streak,
            "winning_days": sum(1 for v in by_day.values() if v > 0),
            "losing_days": sum(1 for v in by_day.values() if v < 0)}


# ── Scanner Stats ────────────────────────────────────────────────────────────

@router.get("/scanner-stats")
async def scanner_stats(request: Request):
    bot = _bot(request)
    return {
        "watchlist_size": len(getattr(bot, "_last_scan_symbols", [])),
        "scan_count": getattr(bot, "_scan_count", 0),
        "candidates_found": getattr(bot, "_last_candidates", 0),
        "signals_generated": getattr(bot, "_last_signals", 0),
        "last_scan": getattr(bot, "_last_scan_iso", ""),
    }


# ── Sector Exposure (current portfolio) ──────────────────────────────────────

@router.get("/sector-exposure")
async def sector_exposure(request: Request):
    bot = _bot(request)
    if not bot.is_running:
        return {"sectors": {}}
    try:
        raw = bot._client.get_positions()
        portfolio_val = bot._client.get_portfolio_value() or 1
        by_sector: dict = {}
        for sym, pos in raw.items():
            qty = float(pos["quantity"])
            price = bot._client.get_current_price(sym) or float(pos["average_buy_price"])
            value = qty * price
            try:
                sector = yf.Ticker(sym).info.get("sector", "Other")
            except Exception:
                sector = "Other"
            by_sector[sector] = round(by_sector.get(sector, 0) + value, 2)
        return {"sectors": by_sector,
                "portfolio_value": portfolio_val,
                "by_pct": {k: round(v / portfolio_val * 100, 2) for k, v in by_sector.items()}}
    except Exception as e:
        return {"sectors": {}, "error": str(e)}


# ── Daily P&L Line (last 30 days) ────────────────────────────────────────────

@router.get("/daily-pnl")
async def daily_pnl(request: Request):
    trades = _bot(request)._trade_log.recent_trades(500)
    by_day: dict = {}
    for t in trades:
        try:
            d = t.get("exit_date", "")[:10]
            by_day[d] = round(by_day.get(d, 0) + t.get("pnl", 0), 2)
        except Exception:
            pass
    days = sorted(by_day.keys())[-30:]
    cumulative = 0
    out = []
    for d in days:
        cumulative = round(cumulative + by_day[d], 2)
        out.append({"date": d, "daily_pnl": by_day[d], "cumulative": cumulative})
    return {"daily": out}


# ── Restart / Close by Strategy ──────────────────────────────────────────────

@router.post("/close-by-strategy/{name}")
async def close_by_strategy(name: str, request: Request):
    bot = _bot(request)
    if not bot.is_running:
        return {"message": "Bot not running"}
    raw = bot._client.get_positions()
    closed = 0
    for sym in list(raw.keys()):
        meta = bot._positions.get(sym)
        if meta and meta.get("strategy") == name:
            pos = raw[sym]
            price = bot._client.get_current_price(sym) or pos["average_buy_price"]
            bot._execute_sell(sym, int(float(pos["quantity"])), price, f"manual: close all {name}")
            closed += 1
    _log_audit("close_by_strategy", f"{name}: closed {closed} positions")
    return {"message": f"Closed {closed} {name} position(s)"}


# ── Bot Uptime / Stats ───────────────────────────────────────────────────────

@router.get("/bot-stats")
async def bot_stats(request: Request):
    bot = _bot(request)
    uptime = time.time() - _server_start
    return {
        "uptime_seconds": int(uptime),
        "is_running": bot.is_running,
        "is_paper": bot.is_paper_trading,
        "scans_per_hour": round(getattr(bot, "_scan_count", 0) / max(uptime / 3600, 0.1), 1),
        "trades_today": bot._risk.get_stats().get("daily_trades", 0),
    }


# ── Settings Backup ──────────────────────────────────────────────────────────

# ── Personal Records / Achievements ──────────────────────────────────────────

# ── Watchlist Live Quotes ────────────────────────────────────────────────────

@router.get("/watchlist-quotes")
async def watchlist_quotes():
    from jarvis.plugins.trading.scanner import get_watchlist
    syms = get_watchlist()[:30]
    quotes = []
    for s in syms:
        try:
            df = yf.Ticker(s).history(period="2d")
            if len(df) >= 2:
                prev = float(df["Close"].iloc[-2])
                curr = float(df["Close"].iloc[-1])
                vol = int(df["Volume"].iloc[-1])
                chg = (curr - prev) / prev * 100
                quotes.append({"symbol": s, "price": round(curr, 2),
                                "change_pct": round(chg, 2), "volume": vol})
        except Exception:
            pass
    quotes.sort(key=lambda x: x["change_pct"], reverse=True)
    return {"quotes": quotes}


# ── General Market News (NewsAPI) ────────────────────────────────────────────

@router.get("/market-news")
async def market_news():
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return {"articles": []}
    import httpx
    try:
        res = httpx.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": "business", "country": "us", "pageSize": 8, "apiKey": api_key},
            timeout=8,
        )
        d = res.json()
        return {"articles": [{"title": a["title"], "source": a["source"]["name"],
                              "url": a["url"], "published": a["publishedAt"][:10],
                              "image": a.get("urlToImage")}
                            for a in d.get("articles", [])[:8]]}
    except Exception as e:
        return {"articles": [], "error": str(e)}


# ── Risk Score (overall portfolio safety) ────────────────────────────────────

@router.get("/risk-score")
async def risk_score(request: Request):
    bot = _bot(request)
    if not bot.is_running:
        return {"score": 0, "grade": "—", "factors": []}
    try:
        positions = bot._client.get_positions()
        portfolio_val = bot._client.get_portfolio_value() or 1
    except Exception:
        return {"score": 0, "grade": "—"}
    score = 100
    factors = []

    # Concentration risk
    for sym, pos in positions.items():
        val = float(pos.get("quantity", 0)) * float(pos.get("average_buy_price", 0))
        pct = val / portfolio_val * 100
        if pct > 25:
            score -= 20
            factors.append(f"⚠ {sym} is {pct:.0f}% of portfolio (high concentration)")
        elif pct > 15:
            score -= 10

    # Number of positions
    if len(positions) > 10:
        score -= 10
        factors.append("Too many positions (>10) — hard to monitor")
    elif len(positions) == 0:
        score = 100  # cash = safe

    # Frozen state
    if bot._risk.is_frozen:
        score -= 30
        factors.append("Bot is FROZEN (circuit breaker)")

    # PDT risk
    pdt_used = bot._risk.pdt_trades_in_window()
    if bot._risk.ACCOUNT_EQUITY < 25000 and pdt_used >= 2:
        score -= 15
        factors.append(f"PDT close: {pdt_used}/3 day trades used")

    score = max(0, min(100, score))
    grade = "A+" if score >= 95 else "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "F"
    return {"score": score, "grade": grade, "factors": factors}


# ── Day's Grade ──────────────────────────────────────────────────────────────

@router.get("/days-grade")
async def days_grade(request: Request):
    bot = _bot(request)
    today = datetime.now().date().isoformat()
    trades = [t for t in bot._trade_log.recent_trades(100) if (t.get("exit_date") or "").startswith(today)]
    if not trades:
        return {"grade": "—", "pnl": 0, "win_rate": 0}
    pnl = sum(t.get("pnl", 0) for t in trades)
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    win_rate = wins / len(trades) * 100
    if pnl >= 100 and win_rate >= 70: grade = "A+"
    elif pnl >= 50 and win_rate >= 60: grade = "A"
    elif pnl > 0 and win_rate >= 50: grade = "B"
    elif pnl > 0: grade = "C"
    elif pnl > -50: grade = "D"
    else: grade = "F"
    return {"grade": grade, "pnl": round(pnl, 2), "win_rate": round(win_rate, 1), "trades": len(trades)}


# ── Strategy Comparison ──────────────────────────────────────────────────────

@router.get("/strategy-comparison")
async def strategy_comparison(request: Request):
    bot = _bot(request)
    by_strat = bot.get_trade_stats().get("by_strategy", {})
    sm = bot.strategy_manager
    out = []
    for name, strat in sm.strategies.items():
        s = by_strat.get(name, {})
        out.append({
            "name": name,
            "enabled": name in sm.enabled,
            "intraday": strat.intraday,
            "min_score": strat.min_score_to_buy,
            "trades": s.get("num_trades", 0),
            "win_rate": s.get("win_rate", 0) * 100,
            "total_pnl": s.get("total_pnl", 0),
            "avg_pnl": s.get("avg_pnl", 0),
        })
    return {"strategies": out}


@router.get("/personal-records")
async def personal_records(request: Request):
    trades = _bot(request)._trade_log.recent_trades(1000)
    if not trades:
        return {"records": {}}
    by_day: dict = {}
    for t in trades:
        try:
            d = t.get("exit_date", "")[:10]
            by_day.setdefault(d, {"pnl": 0, "trades": 0, "wins": 0})
            by_day[d]["pnl"] += t.get("pnl", 0)
            by_day[d]["trades"] += 1
            if t.get("pnl", 0) > 0:
                by_day[d]["wins"] += 1
        except Exception:
            pass
    if not by_day:
        return {"records": {}}
    best_day = max(by_day.items(), key=lambda x: x[1]["pnl"])
    worst_day = min(by_day.items(), key=lambda x: x[1]["pnl"])
    most_trades = max(by_day.items(), key=lambda x: x[1]["trades"])
    best_single = max(trades, key=lambda t: t.get("pnl", 0))
    worst_single = min(trades, key=lambda t: t.get("pnl", 0))
    return {"records": {
        "best_day": {"date": best_day[0], "pnl": round(best_day[1]["pnl"], 2), "trades": best_day[1]["trades"]},
        "worst_day": {"date": worst_day[0], "pnl": round(worst_day[1]["pnl"], 2), "trades": worst_day[1]["trades"]},
        "most_active": {"date": most_trades[0], "trades": most_trades[1]["trades"]},
        "biggest_win": {"symbol": best_single.get("symbol"), "pnl": best_single.get("pnl"), "date": (best_single.get("exit_date") or "")[:10]},
        "biggest_loss": {"symbol": worst_single.get("symbol"), "pnl": worst_single.get("pnl"), "date": (worst_single.get("exit_date") or "")[:10]},
    }}


# ── Achievements (badges) ────────────────────────────────────────────────────

@router.get("/achievements")
async def achievements(request: Request):
    bot = _bot(request)
    trades = bot._trade_log.recent_trades(1000)
    stats = bot._trade_log.stats()
    badges = []

    if len(trades) >= 1:
        badges.append({"id": "first_trade", "label": "First Trade", "icon": "🎯", "earned": True})
    if len(trades) >= 10:
        badges.append({"id": "ten_trades", "label": "10 Trades", "icon": "🔟", "earned": True})
    if len(trades) >= 50:
        badges.append({"id": "fifty_trades", "label": "50 Trades", "icon": "5️⃣", "earned": True})
    if len(trades) >= 100:
        badges.append({"id": "century", "label": "100 Trades", "icon": "💯", "earned": True})
    if stats.get("win_rate", 0) >= 50 and len(trades) >= 10:
        badges.append({"id": "winning_record", "label": "Winning Record", "icon": "📈", "earned": True})
    if stats.get("win_rate", 0) >= 70 and len(trades) >= 10:
        badges.append({"id": "sharpshooter", "label": "Sharpshooter (70%+)", "icon": "🎯", "earned": True})
    if stats.get("profit_factor", 0) >= 2:
        badges.append({"id": "profit_machine", "label": "Profit Factor 2x+", "icon": "🚀", "earned": True})
    if stats.get("total_pnl", 0) >= 100:
        badges.append({"id": "first_100", "label": "First $100", "icon": "💰", "earned": True})
    if stats.get("total_pnl", 0) >= 1000:
        badges.append({"id": "thousand", "label": "First $1,000", "icon": "💎", "earned": True})

    consec_wins = 0; max_wins = 0
    for t in reversed(trades):
        if t.get("pnl", 0) > 0:
            consec_wins += 1
            max_wins = max(max_wins, consec_wins)
        else:
            consec_wins = 0
    if max_wins >= 5:
        badges.append({"id": "streak_5", "label": "5-Win Streak", "icon": "🔥", "earned": True})
    if max_wins >= 10:
        badges.append({"id": "streak_10", "label": "10-Win Streak", "icon": "🌟", "earned": True})

    return {"earned": badges, "total_count": len(badges)}


# ── Daily Narrative (rule-based, no AI cost) ─────────────────────────────────

@router.get("/daily-narrative")
async def daily_narrative(request: Request):
    bot = _bot(request)
    trades = bot._trade_log.recent_trades(50)
    today = datetime.now().date().isoformat()
    today_trades = [t for t in trades if (t.get("exit_date") or "").startswith(today)]
    if not today_trades:
        return {"narrative": "No trades closed today yet. Bot is hunting for setups."}

    pnl = sum(t.get("pnl", 0) for t in today_trades)
    wins = [t for t in today_trades if t.get("pnl", 0) > 0]
    win_rate = round(len(wins) / len(today_trades) * 100, 1)

    parts = []
    parts.append(f"📅 Today: {len(today_trades)} trade(s), {win_rate}% win rate.")
    if pnl > 0:
        parts.append(f"💰 Net P&L: +${pnl:.2f} — solid green day.")
    elif pnl < 0:
        parts.append(f"💔 Net P&L: ${pnl:.2f} — discipline matters; keep stops tight.")
    else:
        parts.append("⚖️ Net flat day.")

    by_strat: dict = {}
    for t in today_trades:
        s = t.get("strategy", "?")
        by_strat.setdefault(s, 0)
        by_strat[s] += t.get("pnl", 0)
    if by_strat:
        best_strat = max(by_strat.items(), key=lambda x: x[1])
        parts.append(f"🏆 Best strategy today: {best_strat[0]} (${best_strat[1]:+.2f})")

    if today_trades:
        biggest = max(today_trades, key=lambda t: abs(t.get("pnl", 0)))
        parts.append(f"⚡ Biggest move: {biggest.get('symbol')} for ${biggest.get('pnl', 0):+.2f}")

    return {"narrative": " ".join(parts), "today_pnl": round(pnl, 2),
            "today_trades": len(today_trades), "today_win_rate": win_rate}


# ── Monthly Performance ──────────────────────────────────────────────────────

@router.get("/monthly-performance")
async def monthly_performance(request: Request):
    trades = _bot(request)._trade_log.recent_trades(1000)
    by_month: dict = {}
    for t in trades:
        try:
            m = (t.get("exit_date") or "")[:7]  # YYYY-MM
            by_month.setdefault(m, {"trades": 0, "wins": 0, "pnl": 0})
            by_month[m]["trades"] += 1
            if t.get("pnl", 0) > 0:
                by_month[m]["wins"] += 1
            by_month[m]["pnl"] = round(by_month[m]["pnl"] + t.get("pnl", 0), 2)
        except Exception:
            pass
    out = [{"month": m, **v, "win_rate": round(v["wins"]/v["trades"]*100, 1) if v["trades"] else 0}
            for m, v in sorted(by_month.items())]
    return {"by_month": out}


@router.get("/settings-backup")
async def settings_backup(request: Request):
    bot = _bot(request)
    r = bot._risk
    return {
        "exported": datetime.now().isoformat(timespec="seconds"),
        "risk_settings": {
            "daily_max_loss_pct": r.DAILY_MAX_LOSS_PCT,
            "stop_loss_pct": r.STOP_LOSS_PCT,
            "trailing_stop_pct": r.TRAILING_STOP_PCT,
            "max_position_pct": r.MAX_POSITION_PCT,
            "max_daily_trades": r.MAX_DAILY_TRADES,
            "concentration_limit": r.CONCENTRATION_LIMIT,
        },
        "enabled_strategies": list(bot.strategy_manager.enabled),
        "watchlist": getattr(bot, "_last_scan_symbols", []),
        "alerts": _price_alerts,
        "pinned": list(_pinned),
        "frozen_positions": list(_frozen_positions),
    }

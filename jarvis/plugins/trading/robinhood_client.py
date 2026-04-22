"""Robinhood API client - handles auth, portfolio data, and order execution.

Defaults to paper trading (no real money) until PAPER_TRADING=false is set.
Credentials are read exclusively from environment variables - never hardcode them.
"""

import os
import logging

import pyotp
import yfinance as yf

logger = logging.getLogger(__name__)


class RobinhoodClient:
    """Thin wrapper around robin_stocks with paper-trading fallback."""

    def __init__(self, paper_trading: bool = True):
        self.paper_trading = paper_trading
        self._logged_in = False
        # Paper trading state
        self._paper_cash: float = float(os.getenv("PAPER_STARTING_BALANCE", "10000"))
        # {symbol: (quantity, avg_buy_price)}
        self._paper_positions: dict[str, tuple[float, float]] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def login(self) -> None:
        if self.paper_trading:
            self._logged_in = True
            logger.info("Paper trading mode – no real Robinhood login.")
            return

        import robin_stocks.robinhood as rh

        username = os.environ["RH_USERNAME"]
        password = os.environ["RH_PASSWORD"]
        mfa_key = os.getenv("RH_MFA_KEY")

        mfa_code = pyotp.TOTP(mfa_key).now() if mfa_key else None
        rh.login(username, password, mfa_code=mfa_code, store_session=True)
        self._logged_in = True
        logger.info("Logged in to Robinhood (LIVE mode).")

    def logout(self) -> None:
        if not self.paper_trading:
            import robin_stocks.robinhood as rh
            rh.logout()
        self._logged_in = False

    # ------------------------------------------------------------------
    # Account data
    # ------------------------------------------------------------------

    def get_buying_power(self) -> float:
        if self.paper_trading:
            return self._paper_cash

        import robin_stocks.robinhood as rh
        profile = rh.profiles.load_account_profile()
        return float(profile.get("buying_power", 0))

    def get_portfolio_value(self) -> float:
        if self.paper_trading:
            position_value = sum(
                qty * self._get_live_price(sym)
                for sym, (qty, _) in self._paper_positions.items()
                if self._get_live_price(sym)
            )
            return self._paper_cash + position_value

        import robin_stocks.robinhood as rh
        portfolio = rh.profiles.load_portfolio_profile()
        return float(portfolio.get("equity", 0))

    def get_positions(self) -> dict[str, dict]:
        """Returns {symbol: {quantity, average_buy_price}}."""
        if self.paper_trading:
            return {
                sym: {"quantity": qty, "average_buy_price": avg}
                for sym, (qty, avg) in self._paper_positions.items()
            }

        import robin_stocks.robinhood as rh
        raw = rh.account.get_open_stock_positions()
        result: dict[str, dict] = {}
        for pos in raw:
            symbol = rh.stocks.get_symbol_by_url(pos["instrument"])
            if symbol:
                result[symbol] = {
                    "quantity": float(pos["quantity"]),
                    "average_buy_price": float(pos["average_buy_price"]),
                }
        return result

    def get_current_price(self, symbol: str) -> float | None:
        return self._get_live_price(symbol)

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def buy(self, symbol: str, shares: int, limit_price: float) -> dict:
        cost = shares * limit_price

        if self.paper_trading:
            if cost > self._paper_cash:
                return {"error": "Insufficient paper funds"}
            self._paper_cash -= cost
            qty, avg = self._paper_positions.get(symbol, (0.0, 0.0))
            new_qty = qty + shares
            new_avg = ((qty * avg) + cost) / new_qty
            self._paper_positions[symbol] = (new_qty, new_avg)
            logger.info(f"[PAPER] BUY {shares} {symbol} @ ${limit_price:.2f}")
            return {"id": f"paper-buy-{symbol}", "state": "filled"}

        import robin_stocks.robinhood as rh
        return rh.orders.order_buy_limit(symbol, shares, limit_price)

    def sell(self, symbol: str, shares: int, limit_price: float) -> dict:
        if self.paper_trading:
            qty, avg = self._paper_positions.get(symbol, (0.0, 0.0))
            sell_qty = min(int(qty), shares)
            if sell_qty == 0:
                return {"error": "No paper position to sell"}
            proceeds = sell_qty * limit_price
            self._paper_cash += proceeds
            remaining = qty - sell_qty
            if remaining <= 0:
                self._paper_positions.pop(symbol, None)
            else:
                self._paper_positions[symbol] = (remaining, avg)
            logger.info(f"[PAPER] SELL {sell_qty} {symbol} @ ${limit_price:.2f}")
            return {"id": f"paper-sell-{symbol}", "state": "filled"}

        import robin_stocks.robinhood as rh
        return rh.orders.order_sell_limit(symbol, shares, limit_price)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_live_price(self, symbol: str) -> float | None:
        try:
            info = yf.Ticker(symbol).fast_info
            price = getattr(info, "last_price", None)
            return float(price) if price else None
        except Exception:
            return None

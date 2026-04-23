"""Backtester: simulate strategies on historical data."""

from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd


class BacktesterEngine:
    def __init__(self, strategy_manager):
        self.strategy_manager = strategy_manager

    def backtest(self, strategy_name, symbol, days=30, initial_capital=10000):
        """Run backtest on historical data.

        Returns: {
            'symbol': str,
            'strategy': str,
            'days': int,
            'initial_capital': float,
            'final_capital': float,
            'total_pnl': float,
            'total_pnl_pct': float,
            'trades': list,
            'win_rate': float,
            'profit_factor': float,
            'max_drawdown': float,
            'sharpe_ratio': float,
            'equity_curve': list,
            'stats': dict
        }
        """
        try:
            # Get strategy
            strategy = self.strategy_manager.strategies.get(strategy_name)
            if not strategy:
                return {'error': f'Strategy {strategy_name} not found'}

            # Fetch historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            df = yf.download(symbol, start=start_date, end=end_date, interval=strategy.bar_interval, progress=False)
            if df.empty:
                return {'error': f'No data for {symbol}'}

            # Simulate
            capital = initial_capital
            position = None  # {'entry_price', 'entry_idx', 'qty'}
            trades = []
            equity_curve = [initial_capital]

            for idx in range(1, len(df)):
                current_price = df['Close'].iloc[idx]

                # Score for entry
                if position is None:
                    df_slice = df.iloc[:idx+1]
                    score = strategy.score(symbol, df_slice, sentiment=0, fundamental_score=0.5)

                    if score >= strategy.min_score_to_buy:
                        qty = max(1, int(capital * 0.1 / current_price))  # 10% position
                        position = {
                            'entry_price': current_price,
                            'entry_idx': idx,
                            'qty': qty,
                            'entry_time': df.index[idx]
                        }
                        capital -= qty * current_price

                # Check exit
                elif position:
                    age_minutes = (idx - position['entry_idx']) * 5  # Assume 5min bars
                    df_slice = df.iloc[:idx+1]
                    should_exit, reason = strategy.should_exit(symbol, df_slice, position['entry_price'], age_minutes)

                    if should_exit:
                        pnl = (current_price - position['entry_price']) * position['qty']
                        pnl_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
                        capital += position['qty'] * current_price

                        trades.append({
                            'entry_time': position['entry_time'].isoformat(),
                            'exit_time': df.index[idx].isoformat(),
                            'entry_price': round(position['entry_price'], 2),
                            'exit_price': round(current_price, 2),
                            'qty': position['qty'],
                            'pnl': round(pnl, 2),
                            'pnl_pct': round(pnl_pct, 2),
                            'reason': reason
                        })
                        position = None

                equity_curve.append(capital)

            # Force close if still in position
            if position:
                final_price = df['Close'].iloc[-1]
                pnl = (final_price - position['entry_price']) * position['qty']
                pnl_pct = (final_price - position['entry_price']) / position['entry_price'] * 100
                capital += position['qty'] * final_price

                trades.append({
                    'entry_time': position['entry_time'].isoformat(),
                    'exit_time': df.index[-1].isoformat(),
                    'entry_price': round(position['entry_price'], 2),
                    'exit_price': round(final_price, 2),
                    'qty': position['qty'],
                    'pnl': round(pnl, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'reason': 'End of backtest'
                })

            # Calculate stats
            total_pnl = capital - initial_capital
            total_pnl_pct = (total_pnl / initial_capital) * 100
            win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) if trades else 0

            wins = [t['pnl'] for t in trades if t['pnl'] > 0]
            losses = [abs(t['pnl']) for t in trades if t['pnl'] < 0]
            profit_factor = sum(wins) / sum(losses) if losses else 0

            # Max drawdown
            equity_array = pd.Series(equity_curve)
            running_max = equity_array.expanding().max()
            drawdown = (equity_array - running_max) / running_max
            max_drawdown = drawdown.min() * 100

            # Sharpe ratio (daily)
            returns = pd.Series(equity_curve).pct_change().dropna()
            sharpe = (returns.mean() / returns.std() * (252**0.5)) if len(returns) > 1 else 0

            return {
                'symbol': symbol,
                'strategy': strategy_name,
                'days': days,
                'initial_capital': initial_capital,
                'final_capital': round(capital, 2),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_pct': round(total_pnl_pct, 2),
                'num_trades': len(trades),
                'win_rate': round(win_rate * 100, 1),
                'profit_factor': round(profit_factor, 2),
                'max_drawdown': round(max_drawdown, 2),
                'sharpe_ratio': round(sharpe, 2),
                'avg_win': round(sum(wins) / len(wins), 2) if wins else 0,
                'avg_loss': round(sum(losses) / len(losses), 2) if losses else 0,
                'equity_curve': [round(x, 2) for x in equity_curve],
                'trades': trades
            }

        except Exception as e:
            return {'error': str(e)}

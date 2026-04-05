"""
backtest/metrics.py -- Backtest Performance Calculators
========================================================
Calculates key performance metrics from a list of completed trades.

METRICS EXPLAINED:
  - Total Return: How much money you made or lost (as % of starting balance)
  - Win Rate: What percentage of trades were profitable
  - Profit Factor: Total profit / Total loss (> 1 is good)
  - Max Drawdown: Worst peak-to-trough decline (how much you could lose)
  - Sharpe Ratio: Risk-adjusted return (> 1 is decent, > 2 is good)
  - Average Trade: Average profit/loss per trade
  - Risk-Reward Ratio: Average win / Average loss
"""

import numpy as np
from config import get_logger

logger = get_logger(__name__)


def calculate_metrics(trades: list, starting_balance: float) -> dict:
    """
    Calculate all performance metrics from a list of completed trades.

    Args:
        trades:           List of trade dicts, each with at least:
                            - pnl (float): profit/loss of the trade
                            - type (str): "BUY" or "SELL"
        starting_balance: The account balance at the start of backtest

    Returns:
        Dictionary with all performance metrics
    """
    if not trades:
        logger.warning("No trades to calculate metrics for!")
        return _empty_metrics()

    # Extract P&L values
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_trades = len(pnls)
    total_wins = len(wins)
    total_losses = len(losses)
    total_pnl = sum(pnls)

    # --- Win Rate ---
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    # --- Total Return ---
    total_return_pct = (total_pnl / starting_balance * 100) if starting_balance > 0 else 0

    # --- Average Trade ---
    avg_trade = total_pnl / total_trades if total_trades > 0 else 0
    avg_win = sum(wins) / total_wins if total_wins > 0 else 0
    avg_loss = sum(losses) / total_losses if total_losses > 0 else 0

    # --- Profit Factor ---
    # Total gross profit / Total gross loss
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # --- Risk-Reward Ratio ---
    risk_reward = (avg_win / abs(avg_loss)) if avg_loss != 0 else float("inf")

    # --- Max Drawdown ---
    max_dd, max_dd_pct = _calculate_max_drawdown(pnls, starting_balance)

    # --- Sharpe Ratio (simplified, annualized) ---
    sharpe = _calculate_sharpe(pnls)

    # --- Longest win/loss streak ---
    win_streak, loss_streak = _calculate_streaks(pnls)

    metrics = {
        "total_trades":      total_trades,
        "winning_trades":    total_wins,
        "losing_trades":     total_losses,
        "win_rate":          round(win_rate, 2),
        "total_pnl":         round(total_pnl, 2),
        "total_return_pct":  round(total_return_pct, 2),
        "avg_trade":         round(avg_trade, 2),
        "avg_win":           round(avg_win, 2),
        "avg_loss":          round(avg_loss, 2),
        "gross_profit":      round(gross_profit, 2),
        "gross_loss":        round(gross_loss, 2),
        "profit_factor":     round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "risk_reward":       round(risk_reward, 2) if risk_reward != float("inf") else "inf",
        "max_drawdown":      round(max_dd, 2),
        "max_drawdown_pct":  round(max_dd_pct, 2),
        "sharpe_ratio":      round(sharpe, 2),
        "win_streak":        win_streak,
        "loss_streak":       loss_streak,
        "starting_balance":  starting_balance,
        "ending_balance":    round(starting_balance + total_pnl, 2),
    }

    return metrics


def print_metrics(metrics: dict):
    """Print a nicely formatted performance report."""
    print("\n" + "=" * 55)
    print("          BACKTEST PERFORMANCE REPORT")
    print("=" * 55)
    print(f"  Starting Balance : ${metrics['starting_balance']:,.2f}")
    print(f"  Ending Balance   : ${metrics['ending_balance']:,.2f}")
    print(f"  Total P&L        : ${metrics['total_pnl']:,.2f}")
    print(f"  Total Return     : {metrics['total_return_pct']}%")
    print("-" * 55)
    print(f"  Total Trades     : {metrics['total_trades']}")
    print(f"  Winners          : {metrics['winning_trades']}")
    print(f"  Losers           : {metrics['losing_trades']}")
    print(f"  Win Rate         : {metrics['win_rate']}%")
    print("-" * 55)
    print(f"  Avg Trade        : ${metrics['avg_trade']:,.2f}")
    print(f"  Avg Win          : ${metrics['avg_win']:,.2f}")
    print(f"  Avg Loss         : ${metrics['avg_loss']:,.2f}")
    print(f"  Risk/Reward      : {metrics['risk_reward']}")
    print("-" * 55)
    print(f"  Gross Profit     : ${metrics['gross_profit']:,.2f}")
    print(f"  Gross Loss       : ${metrics['gross_loss']:,.2f}")
    print(f"  Profit Factor    : {metrics['profit_factor']}")
    print("-" * 55)
    print(f"  Max Drawdown     : ${metrics['max_drawdown']:,.2f}")
    print(f"  Max Drawdown %   : {metrics['max_drawdown_pct']}%")
    print(f"  Sharpe Ratio     : {metrics['sharpe_ratio']}")
    print("-" * 55)
    print(f"  Win Streak       : {metrics['win_streak']}")
    print(f"  Loss Streak      : {metrics['loss_streak']}")
    print("=" * 55 + "\n")


def _calculate_max_drawdown(pnls: list, starting_balance: float) -> tuple:
    """
    Calculate max drawdown from the equity curve.

    Max drawdown = the largest drop from a peak to a trough.
    It tells you the worst-case scenario: how much you could lose
    from your best point before recovering.

    Returns:
        (max_drawdown_amount, max_drawdown_percentage)
    """
    equity = starting_balance
    peak = starting_balance
    max_dd = 0

    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        if drawdown > max_dd:
            max_dd = drawdown

    max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0
    return max_dd, max_dd_pct


def _calculate_sharpe(pnls: list, risk_free_rate: float = 0.0) -> float:
    """
    Simplified Sharpe ratio.

    Sharpe = (mean return - risk-free rate) / std deviation of returns
    Higher = better risk-adjusted returns.
    > 1 = decent, > 2 = good, > 3 = excellent
    """
    if len(pnls) < 2:
        return 0.0

    returns = np.array(pnls)
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)

    if std_return == 0:
        return 0.0

    return (mean_return - risk_free_rate) / std_return


def _calculate_streaks(pnls: list) -> tuple:
    """Calculate longest consecutive win streak and loss streak."""
    max_win_streak = 0
    max_loss_streak = 0
    current_win = 0
    current_loss = 0

    for pnl in pnls:
        if pnl > 0:
            current_win += 1
            current_loss = 0
        elif pnl < 0:
            current_loss += 1
            current_win = 0
        else:
            current_win = 0
            current_loss = 0

        max_win_streak = max(max_win_streak, current_win)
        max_loss_streak = max(max_loss_streak, current_loss)

    return max_win_streak, max_loss_streak


def _empty_metrics() -> dict:
    """Return empty metrics when there are no trades."""
    return {
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
        "win_rate": 0, "total_pnl": 0, "total_return_pct": 0,
        "avg_trade": 0, "avg_win": 0, "avg_loss": 0,
        "gross_profit": 0, "gross_loss": 0,
        "profit_factor": 0, "risk_reward": 0,
        "max_drawdown": 0, "max_drawdown_pct": 0,
        "sharpe_ratio": 0, "win_streak": 0, "loss_streak": 0,
        "starting_balance": 0, "ending_balance": 0,
    }

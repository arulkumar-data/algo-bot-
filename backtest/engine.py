"""
backtest/engine.py -- Backtest Engine
======================================
Simulates trading the EMA crossover strategy on historical candle data.

HOW THE BACKTEST WORKS (in plain English):
-------------------------------------------
1. Take historical candle data (e.g. 1000 candles of EURUSD M15)
2. Run the EMA crossover strategy to find all BUY/SELL signals
3. Walk through each candle one by one, simulating trades:
   - When a BUY signal appears: open a virtual long position
   - When a SELL signal appears: open a virtual short position
   - Close the trade when:
     a) An OPPOSITE signal appears (BUY closes a SELL, SELL closes a BUY)
     b) Stop Loss is hit (price moves against you too much)
     c) Take Profit is hit (price moves in your favor enough)
4. Track all trades: entry price, exit price, P&L, win/loss
5. At the end, calculate performance metrics

IMPORTANT ASSUMPTIONS:
  - Trades execute at the close price of the signal candle (simplified)
  - Spread cost is deducted from each trade
  - Only one position open at a time (no pyramiding)
  - SL/TP are checked against high/low of subsequent candles

USAGE:
    from backtest.engine import run_backtest
    results = run_backtest(candle_df, starting_balance=10000)
"""

import pandas as pd
from config import SL_PIPS, TP_PIPS, RISK_PER_TRADE, get_logger
from strategy.strategy import add_ema_signals
from backtest.metrics import calculate_metrics, print_metrics

logger = get_logger(__name__)


def run_backtest(
    df: pd.DataFrame,
    starting_balance: float = 10000.0,
    sl_pips: float = SL_PIPS,
    tp_pips: float = TP_PIPS,
    risk_per_trade: float = RISK_PER_TRADE,
    spread_pips: float = 2.0,
    pip_value: float = 0.0001,
) -> dict:
    """
    Run a full backtest on historical candle data.

    Args:
        df:               DataFrame with OHLCV data (from get_candles)
        starting_balance: Starting account balance in USD
        sl_pips:          Stop loss in pips (e.g. 50)
        tp_pips:          Take profit in pips (e.g. 100)
        risk_per_trade:   Fraction of balance to risk per trade (e.g. 0.01 = 1%)
        spread_pips:      Assumed spread cost in pips (deducted from each trade)
        pip_value:        Value of 1 pip in price (0.0001 for most forex pairs)

    Returns:
        Dictionary with:
          - trades:    List of all completed trades
          - metrics:   Performance metrics dict
          - equity_curve: List of equity values after each trade
    """
    logger.info("=" * 50)
    logger.info("  STARTING BACKTEST")
    logger.info("=" * 50)
    logger.info(f"  Candles: {len(df)}")
    logger.info(f"  Balance: ${starting_balance:,.2f}")
    logger.info(f"  SL: {sl_pips} pips | TP: {tp_pips} pips")
    logger.info(f"  Risk/Trade: {risk_per_trade * 100}%")
    logger.info(f"  Spread: {spread_pips} pips")

    # --- Step 1: Add EMA signals to the data ---
    df = add_ema_signals(df)

    # --- Step 2: Walk through candles and simulate trades ---
    trades = []                # completed trades
    equity_curve = [starting_balance]
    balance = starting_balance
    position = None            # current open position (None = no position)

    # Convert pips to price difference
    sl_price = sl_pips * pip_value
    tp_price = tp_pips * pip_value
    spread_cost = spread_pips * pip_value

    for i in range(1, len(df)):
        row = df.iloc[i]
        signal = row["signal"]

        # --- Check if an open position should be closed ---
        if position is not None:
            # Check SL/TP against this candle's high/low
            closed, trade = _check_sl_tp(position, row, sl_price, tp_price)
            if closed:
                trade["pnl"] -= spread_cost * trade["lot_size"] * 100000  # spread cost
                balance += trade["pnl"]
                trades.append(trade)
                equity_curve.append(balance)
                position = None

            # If not closed by SL/TP, check for opposite signal
            elif signal in ("BUY", "SELL") and signal != position["type"]:
                trade = _close_position(position, row["close"], row["time"],
                                        "OPPOSITE_SIGNAL")
                trade["pnl"] -= spread_cost * trade["lot_size"] * 100000
                balance += trade["pnl"]
                trades.append(trade)
                equity_curve.append(balance)
                position = None

        # --- Open a new position on signal ---
        if position is None and signal in ("BUY", "SELL"):
            # Calculate position size based on risk
            lot_size = _calculate_lot_size(balance, risk_per_trade, sl_pips, pip_value)

            position = {
                "type":       signal,
                "entry_price": row["close"],
                "entry_time":  row["time"],
                "lot_size":    lot_size,
                "sl_price":    sl_price,
                "tp_price":    tp_price,
            }
            logger.debug(f"Opened {signal} at {row['close']:.5f} | "
                         f"Lot: {lot_size:.2f} | Time: {row['time']}")

    # --- Close any remaining open position at the last candle ---
    if position is not None:
        last = df.iloc[-1]
        trade = _close_position(position, last["close"], last["time"], "END_OF_DATA")
        trade["pnl"] -= spread_cost * trade["lot_size"] * 100000
        balance += trade["pnl"]
        trades.append(trade)
        equity_curve.append(balance)

    # --- Step 3: Calculate metrics ---
    metrics = calculate_metrics(trades, starting_balance)

    logger.info(f"Backtest complete: {len(trades)} trades executed.")

    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": equity_curve,
    }


def _check_sl_tp(position: dict, candle, sl_price: float, tp_price: float) -> tuple:
    """
    Check if the current candle's high/low hit stop-loss or take-profit.

    For a BUY position:
      - SL is hit if candle LOW goes below entry - SL
      - TP is hit if candle HIGH goes above entry + TP

    For a SELL position:
      - SL is hit if candle HIGH goes above entry + SL
      - TP is hit if candle LOW goes below entry - TP

    Returns:
        (closed: bool, trade: dict or None)
    """
    entry = position["entry_price"]

    if position["type"] == "BUY":
        sl_level = entry - sl_price
        tp_level = entry + tp_price

        # Check SL first (worst case)
        if candle["low"] <= sl_level:
            return True, _close_position(position, sl_level, candle["time"], "STOP_LOSS")
        # Check TP
        if candle["high"] >= tp_level:
            return True, _close_position(position, tp_level, candle["time"], "TAKE_PROFIT")

    elif position["type"] == "SELL":
        sl_level = entry + sl_price
        tp_level = entry - tp_price

        # Check SL first
        if candle["high"] >= sl_level:
            return True, _close_position(position, sl_level, candle["time"], "STOP_LOSS")
        # Check TP
        if candle["low"] <= tp_level:
            return True, _close_position(position, tp_level, candle["time"], "TAKE_PROFIT")

    return False, None


def _close_position(position: dict, exit_price: float,
                     exit_time, reason: str) -> dict:
    """
    Close a position and calculate P&L.

    For BUY: P&L = (exit - entry) * lot_size * 100000
    For SELL: P&L = (entry - exit) * lot_size * 100000

    100000 = 1 standard lot = 100,000 units of base currency
    """
    entry = position["entry_price"]
    lot = position["lot_size"]

    if position["type"] == "BUY":
        pnl = (exit_price - entry) * lot * 100000
    else:  # SELL
        pnl = (entry - exit_price) * lot * 100000

    return {
        "type":        position["type"],
        "entry_price": entry,
        "exit_price":  exit_price,
        "entry_time":  position["entry_time"],
        "exit_time":   exit_time,
        "lot_size":    lot,
        "pnl":         round(pnl, 2),
        "reason":      reason,
    }


def _calculate_lot_size(
    balance: float,
    risk_fraction: float,
    sl_pips: float,
    pip_value: float,
) -> float:
    """
    Calculate position size based on risk management.

    Formula:
      risk_amount = balance * risk_fraction  (e.g. $10000 * 1% = $100)
      lot_size = risk_amount / (sl_pips * pip_value * 100000)

    This ensures you never risk more than X% of your balance on one trade.
    """
    risk_amount = balance * risk_fraction  # how much $ we're willing to lose
    pip_value_per_lot = sl_pips * pip_value * 100000  # $ per lot for SL distance

    if pip_value_per_lot <= 0:
        return 0.01  # minimum lot

    lot_size = risk_amount / pip_value_per_lot
    lot_size = max(0.01, round(lot_size, 2))  # minimum 0.01, round to 2 decimals

    return lot_size


def print_trades(trades: list, max_show: int = 20):
    """Print a formatted table of trades."""
    if not trades:
        print("No trades to display.")
        return

    show = trades[:max_show]
    print(f"\n{'#':<4} {'Type':<5} {'Entry':>10} {'Exit':>10} {'Lot':>6} "
          f"{'P&L':>10} {'Reason':<16} {'Entry Time'}")
    print("-" * 90)

    for idx, t in enumerate(show, 1):
        pnl_str = f"${t['pnl']:+,.2f}"
        print(f"{idx:<4} {t['type']:<5} {t['entry_price']:>10.5f} "
              f"{t['exit_price']:>10.5f} {t['lot_size']:>6.2f} "
              f"{pnl_str:>10} {t['reason']:<16} {t['entry_time']}")

    if len(trades) > max_show:
        print(f"  ... and {len(trades) - max_show} more trades")
    print()


# ============================================================
# Quick test: run backtest on synthetic data
# ============================================================
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("  BACKTEST ENGINE -- Test with Synthetic Data")
    print("=" * 60)

    # Create synthetic price data with trends (up -> down -> up)
    np.random.seed(42)
    n = 500

    # Simulate price movement with clear trends
    segments = []
    price = 1.1000
    for _ in range(5):
        # Uptrend
        for _ in range(50):
            price += np.random.uniform(0.00005, 0.0004)
            segments.append(price)
        # Downtrend
        for _ in range(50):
            price -= np.random.uniform(0.00005, 0.0004)
            segments.append(price)

    prices = np.array(segments)

    # Build candle DataFrame
    fake_df = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open": prices - 0.0002,
        "high": prices + np.random.uniform(0.0002, 0.0008, n),
        "low":  prices - np.random.uniform(0.0002, 0.0008, n),
        "close": prices,
        "tick_volume": np.random.randint(100, 1000, n),
    })

    print(f"\nGenerated {n} synthetic candles with trending price")
    print(f"Price range: {prices.min():.5f} to {prices.max():.5f}\n")

    # --- Run the backtest ---
    results = run_backtest(
        df=fake_df,
        starting_balance=10000.0,
        sl_pips=50,
        tp_pips=100,
        spread_pips=2.0,
    )

    # --- Show results ---
    print("\n--- TRADE LOG ---")
    print_trades(results["trades"])

    print_metrics(results["metrics"])

    print(f"Equity curve points: {len(results['equity_curve'])}")
    print(f"  Start: ${results['equity_curve'][0]:,.2f}")
    print(f"  End:   ${results['equity_curve'][-1]:,.2f}")

    print("\n[OK] Backtest engine test complete!\n")

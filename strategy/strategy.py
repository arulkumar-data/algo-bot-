"""
strategy/strategy.py -- EMA Crossover Strategy (Version 1)
============================================================

STRATEGY EXPLAINED IN PLAIN ENGLISH:
-------------------------------------
EMA = Exponential Moving Average. It's a smoothed average of recent prices
that gives more weight to newer prices.

We use TWO EMAs:
  - Fast EMA (20 periods): reacts quickly to price changes
  - Slow EMA (50 periods): reacts slowly, shows the bigger trend

SIGNALS:
  - BUY  signal: Fast EMA crosses ABOVE Slow EMA
    This means recent prices are rising faster than the trend = upward momentum.

  - SELL signal: Fast EMA crosses BELOW Slow EMA
    This means recent prices are falling faster than the trend = downward momentum.

  - HOLD (no signal): No crossover happened on the latest candle.

CROSSOVER DETECTION:
  A crossover happens when:
    - Previous candle: Fast EMA was BELOW Slow EMA
    - Current candle:  Fast EMA is ABOVE Slow EMA
    (This is a "bullish crossover" = BUY)

    Or the opposite for a SELL signal.

VISUAL EXAMPLE:
    Price chart with EMAs:

    Price  ^
           |       Fast EMA ....
           |      /              \\.....
           |   ../                     \\...
           |  /  Slow EMA ............... \\...
           | /  /                              \\
           |/  /    <-- BUY here         SELL --> \\
           +-----------------------------------------> Time

USAGE:
    from strategy.strategy import add_ema_signals, get_latest_signal
    
    df = get_candles("EURUSD", "M15", 200)  # from Phase 2
    df = add_ema_signals(df)                 # adds EMA columns + signal column
    signal = get_latest_signal(df)           # returns "BUY", "SELL", or "HOLD"
"""

import pandas as pd
from config import EMA_FAST, EMA_SLOW, get_logger

logger = get_logger(__name__)


def calculate_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """
    Calculate the Exponential Moving Average (EMA) for a given period.

    WHAT IS EMA?
      EMA is like a regular average of prices, but it gives MORE weight
      to recent prices. This makes it react faster to new price movements.

    Args:
        df:      DataFrame with OHLCV data (must have a 'close' column)
        period:  Number of candles to average over (e.g. 20, 50)
        column:  Which price column to use (default: 'close')

    Returns:
        pandas Series with the EMA values
    """
    return df[column].ewm(span=period, adjust=False).mean()


def add_ema_signals(
    df: pd.DataFrame,
    fast_period: int = EMA_FAST,
    slow_period: int = EMA_SLOW,
) -> pd.DataFrame:
    """
    Add EMA columns and a trading signal column to the candle DataFrame.

    This is the MAIN function that processes raw candle data into signals.

    Steps:
      1. Calculate Fast EMA (20)
      2. Calculate Slow EMA (50)
      3. Detect crossovers
      4. Add a 'signal' column: "BUY", "SELL", or "HOLD"

    Args:
        df:          DataFrame from get_candles() with 'close' column
        fast_period: Fast EMA period (default: 20)
        slow_period: Slow EMA period (default: 50)

    Returns:
        Same DataFrame with new columns added:
          - ema_fast:       Fast EMA values
          - ema_slow:       Slow EMA values
          - signal:         "BUY", "SELL", or "HOLD" for each candle
    """
    # Make a copy so we don't modify the original
    df = df.copy()

    # --- Step 1: Calculate both EMAs ---
    df["ema_fast"] = calculate_ema(df, fast_period)
    df["ema_slow"] = calculate_ema(df, slow_period)

    logger.info(f"Calculated EMA Fast({fast_period}) and EMA Slow({slow_period})")

    # --- Step 2: Detect crossovers ---
    # We compare current row vs previous row to find the exact crossover candle.
    #
    # prev_fast_above = was Fast EMA above Slow EMA on the PREVIOUS candle?
    # curr_fast_above = is Fast EMA above Slow EMA on the CURRENT candle?
    #
    # BUY crossover:  prev_fast_above = False AND curr_fast_above = True
    # SELL crossover: prev_fast_above = True  AND curr_fast_above = False

    df["signal"] = "HOLD"  # default: no signal

    for i in range(1, len(df)):
        prev_fast = df["ema_fast"].iloc[i - 1]
        prev_slow = df["ema_slow"].iloc[i - 1]
        curr_fast = df["ema_fast"].iloc[i]
        curr_slow = df["ema_slow"].iloc[i]

        # Bullish crossover: Fast was below Slow, now Fast is above Slow
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            df.iloc[i, df.columns.get_loc("signal")] = "BUY"

        # Bearish crossover: Fast was above Slow, now Fast is below Slow
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            df.iloc[i, df.columns.get_loc("signal")] = "SELL"

    # Count signals found
    buy_count = (df["signal"] == "BUY").sum()
    sell_count = (df["signal"] == "SELL").sum()
    logger.info(f"Signals found: {buy_count} BUY, {sell_count} SELL, "
                f"{len(df) - buy_count - sell_count} HOLD")

    return df


def get_latest_signal(df: pd.DataFrame) -> dict:
    """
    Get the trading signal from the MOST RECENT (last) candle.

    This is what you call in the main loop to decide whether to trade.

    Args:
        df: DataFrame that has already been processed by add_ema_signals()

    Returns:
        Dictionary with:
          - signal:    "BUY", "SELL", or "HOLD"
          - time:      Time of the candle
          - close:     Close price
          - ema_fast:  Fast EMA value
          - ema_slow:  Slow EMA value
          - ema_diff:  Difference between Fast and Slow EMA
    """
    if df is None or len(df) == 0:
        logger.error("No data to get signal from!")
        return {"signal": "HOLD", "time": None, "close": None,
                "ema_fast": None, "ema_slow": None, "ema_diff": None}

    # Get the last (most recent) row
    last = df.iloc[-1]

    result = {
        "signal":   last["signal"],
        "time":     last["time"],
        "close":    last["close"],
        "ema_fast": round(last["ema_fast"], 6),
        "ema_slow": round(last["ema_slow"], 6),
        "ema_diff": round(last["ema_fast"] - last["ema_slow"], 6),
    }

    logger.info(
        f"Latest signal: {result['signal']} | "
        f"Time: {result['time']} | "
        f"Close: {result['close']} | "
        f"EMA Fast: {result['ema_fast']} | "
        f"EMA Slow: {result['ema_slow']} | "
        f"Diff: {result['ema_diff']}"
    )

    return result


def get_signal_history(df: pd.DataFrame, last_n: int = 10) -> pd.DataFrame:
    """
    Get the last N rows showing signals, useful for debugging.

    Args:
        df:     DataFrame processed by add_ema_signals()
        last_n: Number of recent rows to return

    Returns:
        DataFrame with columns: time, close, ema_fast, ema_slow, signal
    """
    cols = ["time", "close", "ema_fast", "ema_slow", "signal"]
    available_cols = [c for c in cols if c in df.columns]
    return df[available_cols].tail(last_n)


# ============================================================
# Quick test: run this file with sample data to see signals
# ============================================================
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("  EMA CROSSOVER STRATEGY -- Test with Synthetic Data")
    print("=" * 60)

    # Create fake candle data to demonstrate the strategy
    # We simulate a price that trends up then down to trigger both signals
    np.random.seed(42)
    n = 100

    # Simulate a price that goes up for 50 candles, then down for 50
    base_price = 1.1000
    trend_up = base_price + np.cumsum(np.random.uniform(0.0001, 0.0005, 50))
    trend_down = trend_up[-1] - np.cumsum(np.random.uniform(0.0001, 0.0005, 50))
    prices = np.concatenate([trend_up, trend_down])

    # Build a minimal DataFrame
    fake_df = pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open": prices - 0.0002,
        "high": prices + 0.0005,
        "low":  prices - 0.0005,
        "close": prices,
        "tick_volume": np.random.randint(100, 1000, n),
    })

    print(f"\nGenerated {n} fake candles (price up then down)")
    print(f"Price range: {prices.min():.5f} to {prices.max():.5f}\n")

    # --- Run the strategy ---
    result_df = add_ema_signals(fake_df)

    # Show recent signals
    print("\n--- Last 20 candles with signals ---")
    history = get_signal_history(result_df, 20)
    print(history.to_string(index=False))

    # Show only BUY/SELL signals
    signals_only = result_df[result_df["signal"] != "HOLD"]
    print(f"\n--- All BUY/SELL signals ({len(signals_only)} total) ---")
    if len(signals_only) > 0:
        print(get_signal_history(signals_only, len(signals_only)).to_string(index=False))
    else:
        print("  No crossover signals found in this data.")

    # Get the latest signal
    print("\n--- Latest Signal ---")
    latest = get_latest_signal(result_df)
    for key, val in latest.items():
        print(f"  {key}: {val}")

    print("\n[OK] Strategy test complete!\n")

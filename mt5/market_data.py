"""
mt5/market_data.py -- Market Data Fetcher
==========================================
Fetches historical candle (OHLCV) data and live tick prices from MetaTrader 5.

KEY CONCEPTS:
  - Candle / Bar: One row of data = Open, High, Low, Close, Volume for a time period.
  - Timeframe: The duration of each candle (M1=1min, M5=5min, M15=15min, H1=1hr, D1=1day).
  - OHLCV: Open, High, Low, Close, Volume -- the 5 standard candle values.
  - Tick: The most recent bid/ask price (real-time).

PREREQUISITE: You must call connect_mt5() first!
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from config import SYMBOL, TIMEFRAME_STR, NUM_CANDLES, get_logger

logger = get_logger(__name__)


# ============================================================
# Timeframe Mapping
# ============================================================
# Maps human-readable timeframe strings to MT5 constants.
# MT5 uses integer constants like mt5.TIMEFRAME_M15 internally.
TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,    # 1 minute
    "M5":  mt5.TIMEFRAME_M5,    # 5 minutes
    "M15": mt5.TIMEFRAME_M15,   # 15 minutes
    "M30": mt5.TIMEFRAME_M30,   # 30 minutes
    "H1":  mt5.TIMEFRAME_H1,    # 1 hour
    "H4":  mt5.TIMEFRAME_H4,    # 4 hours
    "D1":  mt5.TIMEFRAME_D1,    # 1 day
    "W1":  mt5.TIMEFRAME_W1,    # 1 week
    "MN1": mt5.TIMEFRAME_MN1,   # 1 month
}


def get_timeframe(timeframe_str: str) -> int:
    """
    Convert a human-readable timeframe string (e.g. 'M15') to an MT5 constant.

    Args:
        timeframe_str: One of 'M1','M5','M15','M30','H1','H4','D1','W1','MN1'

    Returns:
        MT5 timeframe constant (integer)

    Raises:
        ValueError: If the timeframe string is not recognized
    """
    tf = TIMEFRAME_MAP.get(timeframe_str.upper())
    if tf is None:
        valid = ", ".join(TIMEFRAME_MAP.keys())
        raise ValueError(
            f"Unknown timeframe '{timeframe_str}'. Valid options: {valid}"
        )
    return tf


def get_candles(
    symbol: str = SYMBOL,
    timeframe_str: str = TIMEFRAME_STR,
    num_candles: int = NUM_CANDLES,
) -> pd.DataFrame | None:
    """
    Fetch historical candle (OHLCV) data from MT5.

    This is the MAIN function you will use to get price data for analysis.

    Args:
        symbol:        Trading symbol, e.g. 'EURUSD', 'XAUUSD'
        timeframe_str: Timeframe string, e.g. 'M15', 'H1'
        num_candles:   How many candles to fetch (e.g. 200)

    Returns:
        pandas DataFrame with columns:
          time, open, high, low, close, tick_volume, spread, real_volume
        Returns None if the fetch fails.

    Example:
        df = get_candles("EURUSD", "M15", 200)
        print(df.head())
        #                       time     open     high      low    close  tick_volume  spread  real_volume
        # 0  2024-01-02 00:00:00  1.10425  1.10450  1.10400  1.10430          150       2            0
        # 1  2024-01-02 00:15:00  1.10430  1.10460  1.10410  1.10440          120       3            0
    """
    logger.info(f"Fetching {num_candles} candles for {symbol} {timeframe_str}...")

    # Step 1: Check if the symbol exists and is available
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"Symbol '{symbol}' not found! Check the spelling.")
        logger.error("Common symbols: EURUSD, GBPUSD, USDJPY, XAUUSD")
        return None

    # Step 2: Make sure the symbol is visible in Market Watch
    if not symbol_info.visible:
        logger.info(f"Symbol '{symbol}' is not visible. Enabling it...")
        if not mt5.symbol_select(symbol, True):
            logger.error(f"Failed to enable symbol '{symbol}' in Market Watch.")
            return None

    # Step 3: Convert the timeframe string to MT5 constant
    timeframe = get_timeframe(timeframe_str)

    # Step 4: Fetch the candles using copy_rates_from_pos
    # copy_rates_from_pos(symbol, timeframe, start_position, count)
    #   start_position = 0 means the most recent candle
    #   count = how many candles to go back
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)

    if rates is None or len(rates) == 0:
        error = mt5.last_error()
        logger.error(f"Failed to fetch candle data! Error: {error}")
        return None

    # Step 5: Convert to pandas DataFrame
    df = pd.DataFrame(rates)

    # Step 6: Convert the 'time' column from Unix timestamp to readable datetime
    df["time"] = pd.to_datetime(df["time"], unit="s")

    logger.info(f"Fetched {len(df)} candles. Range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")

    return df


def get_current_tick(symbol: str = SYMBOL) -> dict | None:
    """
    Get the latest bid/ask tick price for a symbol.

    This gives you the real-time price right now.

    Args:
        symbol: Trading symbol, e.g. 'EURUSD'

    Returns:
        Dictionary with: bid, ask, last, time
        Returns None if it fails.

    Example:
        tick = get_current_tick("EURUSD")
        print(f"Bid: {tick['bid']}, Ask: {tick['ask']}")
    """
    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        error = mt5.last_error()
        logger.error(f"Failed to get tick for {symbol}! Error: {error}")
        return None

    tick_data = {
        "symbol": symbol,
        "bid":    tick.bid,
        "ask":    tick.ask,
        "last":   tick.last,
        "spread": round(tick.ask - tick.bid, 6),
        "time":   datetime.fromtimestamp(tick.time),
    }

    logger.info(
        f"Tick {symbol}: Bid={tick_data['bid']:.5f}  Ask={tick_data['ask']:.5f}  "
        f"Spread={tick_data['spread']:.5f}"
    )

    return tick_data


def get_symbol_info(symbol: str = SYMBOL) -> dict | None:
    """
    Get detailed information about a trading symbol.

    Useful for:
      - Finding the pip value (point size)
      - Checking min/max lot sizes
      - Checking trading hours
      - Getting the number of decimal digits

    Args:
        symbol: Trading symbol, e.g. 'EURUSD'

    Returns:
        Dictionary with key symbol properties, or None if it fails.
    """
    info = mt5.symbol_info(symbol)

    if info is None:
        logger.error(f"Symbol info not found for '{symbol}'")
        return None

    sym_data = {
        "symbol":       info.name,
        "description":  info.description,
        "point":        info.point,          # smallest price change (e.g. 0.00001)
        "digits":       info.digits,         # decimal places (e.g. 5 for EURUSD)
        "spread":       info.spread,         # current spread in points
        "volume_min":   info.volume_min,     # minimum lot size
        "volume_max":   info.volume_max,     # maximum lot size
        "volume_step":  info.volume_step,    # lot size increment
        "trade_mode":   info.trade_mode,     # 0=disabled, 4=full
        "bid":          info.bid,
        "ask":          info.ask,
    }

    logger.info(f"Symbol info for {symbol}:")
    logger.info(f"  Point={sym_data['point']}, Digits={sym_data['digits']}, "
                f"Spread={sym_data['spread']} pts")
    logger.info(f"  Lot: min={sym_data['volume_min']}, max={sym_data['volume_max']}, "
                f"step={sym_data['volume_step']}")

    return sym_data


# ============================================================
# Quick test: run this file directly to fetch sample data
# ============================================================
if __name__ == "__main__":
    from mt5.connection import connect_mt5, disconnect_mt5

    print("=" * 60)
    print("  MT5 Market Data Test")
    print("=" * 60)

    if connect_mt5():
        # Test 1: Get symbol info
        print("\n--- Symbol Info ---")
        sym = get_symbol_info(SYMBOL)
        if sym:
            for key, val in sym.items():
                print(f"  {key}: {val}")

        # Test 2: Get current tick
        print("\n--- Current Tick ---")
        tick = get_current_tick(SYMBOL)
        if tick:
            print(f"  Bid: {tick['bid']}")
            print(f"  Ask: {tick['ask']}")
            print(f"  Spread: {tick['spread']}")
            print(f"  Time: {tick['time']}")

        # Test 3: Fetch candles
        print(f"\n--- Last 10 Candles ({SYMBOL} {TIMEFRAME_STR}) ---")
        df = get_candles(SYMBOL, TIMEFRAME_STR, 10)
        if df is not None:
            print(df.to_string(index=False))

        disconnect_mt5()
        print("\n[OK] Market data test completed!\n")
    else:
        print("[FAIL] Could not connect to MT5.\n")

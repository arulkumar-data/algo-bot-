"""
tests/test_connection.py -- Full MT5 Connection + Data Test
============================================================
Run this script to test ALL Phase 2 functionality at once:
  1. Connect to MT5 terminal
  2. Read account information
  3. Fetch symbol info
  4. Get current tick price
  5. Fetch 10 historical candles
  6. Disconnect cleanly

HOW TO RUN:
  cd mt5_algo_bot
  python -m tests.test_connection

EXPECTED OUTPUT:
  You should see account details, symbol info, tick prices,
  and a table of recent candles. If anything fails, the error
  messages will tell you exactly what to fix.
"""

import sys
import os

# Add the project root to Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SYMBOL, TIMEFRAME_STR, get_logger
from mt5.connection import connect_mt5, disconnect_mt5
from mt5.account import get_account_info, print_account_summary
from mt5.market_data import get_candles, get_current_tick, get_symbol_info

logger = get_logger("test_connection")


def run_all_tests():
    """Run all Phase 2 tests in sequence."""

    print("=" * 60)
    print("  MT5 PHASE 2 -- FULL CONNECTION & DATA TEST")
    print("=" * 60)

    # ----------------------------------------------------------
    # TEST 1: Connect to MT5
    # ----------------------------------------------------------
    print("\n[TEST 1] Connecting to MetaTrader 5...")
    if not connect_mt5():
        print("[FAIL] Connection failed. Fix the errors above and retry.")
        return False

    print("[PASS] Connected to MT5!\n")

    # ----------------------------------------------------------
    # TEST 2: Account Information
    # ----------------------------------------------------------
    print("[TEST 2] Reading account information...")
    account = get_account_info()
    if account:
        print_account_summary(account)
        print("[PASS] Account info retrieved!\n")
    else:
        print("[FAIL] Could not read account info.\n")

    # ----------------------------------------------------------
    # TEST 3: Symbol Information
    # ----------------------------------------------------------
    print(f"[TEST 3] Getting symbol info for {SYMBOL}...")
    sym = get_symbol_info(SYMBOL)
    if sym:
        print(f"  Point (pip unit) : {sym['point']}")
        print(f"  Digits           : {sym['digits']}")
        print(f"  Spread           : {sym['spread']} points")
        print(f"  Min lot          : {sym['volume_min']}")
        print(f"  Bid              : {sym['bid']}")
        print(f"  Ask              : {sym['ask']}")
        print("[PASS] Symbol info retrieved!\n")
    else:
        print(f"[FAIL] Symbol '{SYMBOL}' not found.\n")

    # ----------------------------------------------------------
    # TEST 4: Current Tick Price
    # ----------------------------------------------------------
    print(f"[TEST 4] Getting live tick for {SYMBOL}...")
    tick = get_current_tick(SYMBOL)
    if tick:
        print(f"  Bid    : {tick['bid']}")
        print(f"  Ask    : {tick['ask']}")
        print(f"  Spread : {tick['spread']}")
        print(f"  Time   : {tick['time']}")
        print("[PASS] Tick data retrieved!\n")
    else:
        print("[FAIL] Could not get tick data.\n")

    # ----------------------------------------------------------
    # TEST 5: Historical Candles
    # ----------------------------------------------------------
    print(f"[TEST 5] Fetching 10 candles for {SYMBOL} {TIMEFRAME_STR}...")
    df = get_candles(SYMBOL, TIMEFRAME_STR, 10)
    if df is not None and len(df) > 0:
        print(df.to_string(index=False))
        print(f"\n  Total candles: {len(df)}")
        print(f"  Columns: {list(df.columns)}")
        print("[PASS] Candle data retrieved!\n")
    else:
        print("[FAIL] Could not fetch candle data.\n")

    # ----------------------------------------------------------
    # CLEANUP: Disconnect
    # ----------------------------------------------------------
    disconnect_mt5()

    print("=" * 60)
    print("  ALL PHASE 2 TESTS COMPLETE!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

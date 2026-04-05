"""
execution/live_trader.py -- Live Trading Execution
===================================================
Runs the trading bot on a LIVE MT5 account with REAL MONEY.

WARNING:
  - This mode uses REAL FUNDS.
  - Losses are permanent. Proceed entirely at your own risk.
  - It is highly recommended to run the paper_trader for at least
    1-2 weeks before even considering live trading.

HOW IT DIFFERS FROM PAPER TRADER:
  1. Enforces TRADING_MODE = "live"
  2. Subscribes to stricter slippage / execution rules (if needed)
  3. Uses a different MT5 Magic Number (to separate live from demo)

NOTE:
  Currently, this is a skeleton. For version 1.0, we reuse the robust logic
  from paper_trader, but wrap it in an explicit "live" confirmation check.
"""

import sys
import time
from datetime import datetime
from config import TRADING_MODE, SYMBOL, TIMEFRAME_STR, get_logger
from execution.paper_trader import run_single_check
from mt5.connection import connect_mt5, disconnect_mt5
from mt5.account import get_account_info, print_account_summary

logger = get_logger(__name__)


def run_live_bot(check_interval_seconds: int = 60, max_iterations: int = 1000):
    """
    Run the Live Trading Bot.
    """
    # --- CRITICAL SAFETY CHECK ---
    if TRADING_MODE != "live":
        logger.error("Live trader ONLY works in live mode!")
        logger.error("Set TRADING_MODE=live in .env file to enable.")
        return

    logger.critical("=" * 60)
    logger.critical("  WARNING: LIVE TRADING MODE INITIATED")
    logger.critical("  YOU ARE TRADING WITH REAL MONEY.")
    logger.critical("  PRESS CTRL+C IMMEDIATELY TO CANCEL.")
    logger.critical("=" * 60)

    # 10 second countdown to allow canceling
    for i in range(10, 0, -1):
        sys.stdout.write(f"\rStarting in {i} seconds... (Ctrl+C to abort)  ")
        sys.stdout.flush()
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)
    print("\nStarting live execution loop...")

    # --- Connect ---
    if not connect_mt5():
        logger.error("Cannot connect to MT5. Exiting live mode.")
        return

    try:
        account = get_account_info()
        if account:
            print_account_summary(account)
            # The paper_trader module handles the daily stats resetting
        else:
            logger.error("Could not get account info. Live trading aborted.")
            return

        # --- Main loop ---
        for iteration in range(1, max_iterations + 1):
            logger.info(f"--- Live Iteration {iteration}/{max_iterations} "
                        f"| {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

            # In Version 1, we share the execution logic with the paper trader,
            # because the paper trader already sends real MT5 orders and applies
            # all safety checks via risk/rules.py.
            result = run_single_check()

            if result['action'] != "NO_SIGNAL":
                logger.info(f"Live action taken: {result['action']} - {result['details']}")

            if iteration < max_iterations:
                time.sleep(check_interval_seconds)

    except KeyboardInterrupt:
        logger.info("\nLive bot stopped by user (Ctrl+C).")

    finally:
        logger.info("Shutting down live trader...")
        disconnect_mt5()

    logger.info("Live trading bot stopped cleanly.")


if __name__ == "__main__":
    run_live_bot()

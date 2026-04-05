"""
main.py -- Entry Point for the MT5 Algo Trading Bot
=====================================================
This is the file you run:  python main.py

Current state (Phase 5):
  1. Loads configuration from .env
  2. Connects to MetaTrader 5 terminal
  3. Uses execution/paper_trader.py to:
     - Run risk and safety checks
     - Fetch data & generate signals
     - Place demo trades via mt5/orders.py
  4. Disconnects cleanly
"""

import sys
from config import (
    TRADING_MODE,
    SYMBOL,
    TIMEFRAME_STR,
    EMA_FAST,
    EMA_SLOW,
    SL_PIPS,
    TP_PIPS,
    RISK_PER_TRADE,
    MAX_TRADES_DAY,
    MAX_DAILY_LOSS,
    NUM_CANDLES,
    get_logger,
)
from mt5.connection import connect_mt5, disconnect_mt5
from mt5.account import get_account_info, print_account_summary
from mt5.market_data import get_candles, get_current_tick
from strategy.strategy import add_ema_signals, get_latest_signal, get_signal_history

# Create a logger for this module
logger = get_logger(__name__)


def print_banner():
    """Print a startup banner with current settings."""
    banner = f"""
+----------------------------------------------------------+
|           MT5 ALGO TRADING BOT -- Version 1.0            |
|                  EMA Crossover Strategy                   |
+----------------------------------------------------------+
|  Mode        : {TRADING_MODE.upper():<41s} |
|  Symbol      : {SYMBOL:<41s} |
|  Timeframe   : {TIMEFRAME_STR:<41s} |
|  EMA Fast    : {str(EMA_FAST):<41s} |
|  EMA Slow    : {str(EMA_SLOW):<41s} |
|  SL (pips)   : {str(SL_PIPS):<41s} |
|  TP (pips)   : {str(TP_PIPS):<41s} |
|  Risk/Trade  : {str(RISK_PER_TRADE * 100) + '%':<41s} |
|  Max Trades  : {str(MAX_TRADES_DAY) + '/day':<41s} |
|  Max DailyLoss: {str(MAX_DAILY_LOSS * 100) + '%':<40s} |
+----------------------------------------------------------+
    """
    print(banner)


def main():
    """Main entry point for the trading bot."""

    # --- Step 1: Startup ---
    print_banner()
    logger.info("Bot starting up...")
    logger.info(f"Trading mode: {TRADING_MODE.upper()}")
    logger.info(f"Strategy: EMA Crossover ({EMA_FAST}/{EMA_SLOW}) on {SYMBOL} {TIMEFRAME_STR}")

    # --- Safety check: warn if live mode ---
    if TRADING_MODE == "live":
        logger.warning("WARNING: LIVE TRADING MODE is active! Real money is at risk!")
        logger.warning("Make sure you know what you are doing.")
    else:
        logger.info("[OK] Running in DEMO mode -- no real money at risk.")

    # --- Step 2: Connect to MT5 (Phase 2) ---
    if not connect_mt5():
        logger.error("Cannot continue without MT5 connection. Exiting.")
        return

    try:
        # --- Run Paper Trader (Phase 5) ---
        from execution.paper_trader import run_single_check
        result = run_single_check()
        logger.info(f"Execution result: {result}")

    finally:
        # --- Step 7: Always disconnect cleanly ---
        disconnect_mt5()

    logger.info("Bot run complete.")
    print("\n[OK] Phase 5 complete! Paper trading execution integrated.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

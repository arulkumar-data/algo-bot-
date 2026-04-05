"""
execution/paper_trader.py -- Paper/Demo Trading Execution
==========================================================
Runs the trading bot on a demo MT5 account.

HOW IT WORKS:
  1. Connect to MT5 (demo account)
  2. Fetch candle data
  3. Run EMA crossover strategy
  4. If signal is BUY or SELL:
     a. Run all pre-trade safety checks (risk/rules.py)
     b. Calculate lot size based on risk
     c. Calculate SL/TP price levels
     d. Send the order via mt5/orders.py
  5. Log everything
  6. Wait for next candle and repeat

MODES:
  - Single run: check once and exit (good for cron jobs / scheduler)
  - Loop mode: keep checking every N seconds (continuous bot)

SAFETY:
  - Only works on DEMO accounts by default
  - All risk checks must pass before placing orders
  - Ctrl+C stops the bot cleanly
  - Max trades per day enforced
  - Max daily loss enforced
"""

import time
from datetime import datetime
from config import (
    SYMBOL,
    TIMEFRAME_STR,
    NUM_CANDLES,
    SL_PIPS,
    TP_PIPS,
    TRADING_MODE,
    get_logger,
)
from mt5.connection import connect_mt5, disconnect_mt5
from mt5.account import get_account_info, print_account_summary
from mt5.market_data import get_candles, get_current_tick
from mt5.orders import send_market_order, get_open_positions, close_all_bot_positions
from strategy.strategy import add_ema_signals, get_latest_signal
from risk.rules import (
    pre_trade_checks,
    calculate_lot_size,
    calculate_sl_tp_prices,
    reset_daily_stats,
    record_trade,
    get_daily_stats,
)

logger = get_logger(__name__)


def run_single_check() -> dict:
    """
    Run one cycle: fetch data, check signal, place trade if needed.

    This is the core logic that runs each time we check the market.

    Returns:
        Dictionary with what happened:
          - signal: BUY/SELL/HOLD
          - action: what was done (TRADE_PLACED, CHECK_FAILED, NO_SIGNAL, ERROR)
          - details: extra info
    """
    result = {"signal": "HOLD", "action": "NO_SIGNAL", "details": ""}

    # --- Step 1: Get account info ---
    account = get_account_info()
    if account is None:
        result["action"] = "ERROR"
        result["details"] = "Could not get account info"
        logger.error(result["details"])
        return result

    balance = account["balance"]

    # --- Step 2: Fetch candle data ---
    candles = get_candles(SYMBOL, TIMEFRAME_STR, NUM_CANDLES)
    if candles is None:
        result["action"] = "ERROR"
        result["details"] = "Could not fetch candle data"
        logger.error(result["details"])
        return result

    # --- Step 3: Run strategy ---
    candles = add_ema_signals(candles)
    signal_data = get_latest_signal(candles)
    signal = signal_data["signal"]
    result["signal"] = signal

    if signal == "HOLD":
        logger.info("Signal: HOLD -- no trade needed.")
        return result

    logger.info(f"Signal detected: {signal}")

    # --- Step 4: Run pre-trade safety checks ---
    can_trade, reason = pre_trade_checks(
        symbol=SYMBOL,
        signal=signal,
        account_balance=balance,
    )

    if not can_trade:
        result["action"] = "CHECK_FAILED"
        result["details"] = reason
        logger.warning(f"Trade blocked by risk check: {reason}")
        return result

    # --- Step 5: Calculate lot size and SL/TP ---
    lot_size = calculate_lot_size(
        balance=balance,
        sl_pips=SL_PIPS,
        symbol=SYMBOL,
    )

    sl_price, tp_price = calculate_sl_tp_prices(
        symbol=SYMBOL,
        order_type=signal,
        sl_pips=SL_PIPS,
        tp_pips=TP_PIPS,
    )

    if sl_price == 0 or tp_price == 0:
        result["action"] = "ERROR"
        result["details"] = "Could not calculate SL/TP prices"
        logger.error(result["details"])
        return result

    # --- Step 6: Place the order ---
    logger.info(f"Placing {signal} order: {SYMBOL} | Lot: {lot_size} | "
                f"SL: {sl_price} | TP: {tp_price}")

    order_result = send_market_order(
        symbol=SYMBOL,
        order_type=signal,
        lot_size=lot_size,
        sl_price=sl_price,
        tp_price=tp_price,
        comment=f"EMA_{signal}_{TIMEFRAME_STR}",
    )

    if order_result and order_result["success"]:
        result["action"] = "TRADE_PLACED"
        result["details"] = (f"Ticket: {order_result['ticket']} | "
                             f"Price: {order_result['price']} | "
                             f"Lot: {order_result['volume']}")
        logger.info(f"Trade PLACED successfully! {result['details']}")
        # Note: P&L is recorded when the trade closes, not when it opens
    else:
        result["action"] = "ORDER_FAILED"
        result["details"] = "MT5 order_send failed"
        logger.error("Order placement FAILED!")

    return result


def run_paper_bot(
    check_interval_seconds: int = 60,
    max_iterations: int = 100,
):
    """
    Run the paper trading bot in a continuous loop.

    Args:
        check_interval_seconds: Seconds to wait between checks
        max_iterations:         Maximum loops before auto-stop (safety limit)

    The bot will:
      1. Connect to MT5
      2. Check for signals every N seconds
      3. Place demo trades when signal appears
      4. Stop after max_iterations OR on Ctrl+C
    """
    # Safety: Only run on demo accounts
    if TRADING_MODE != "demo":
        logger.error("Paper trader ONLY works in demo mode!")
        logger.error("Set TRADING_MODE=demo in .env file.")
        return

    logger.info("=" * 55)
    logger.info("  PAPER TRADING BOT -- Starting")
    logger.info("=" * 55)
    logger.info(f"  Symbol: {SYMBOL} | Timeframe: {TIMEFRAME_STR}")
    logger.info(f"  Check interval: {check_interval_seconds}s")
    logger.info(f"  Max iterations: {max_iterations}")
    logger.info(f"  Press Ctrl+C to stop")
    logger.info("=" * 55)

    # --- Connect ---
    if not connect_mt5():
        logger.error("Cannot connect to MT5. Exiting.")
        return

    try:
        # Initialize daily stats
        account = get_account_info()
        if account:
            print_account_summary(account)
            reset_daily_stats(account["balance"])
        else:
            logger.warning("Could not get account info. Using default balance.")
            reset_daily_stats(10000)

        # --- Main loop ---
        for iteration in range(1, max_iterations + 1):
            logger.info(f"\n--- Iteration {iteration}/{max_iterations} "
                        f"| {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

            # Run one check cycle
            result = run_single_check()

            logger.info(f"Result: signal={result['signal']}, "
                        f"action={result['action']}, "
                        f"details={result['details']}")

            # Show current open positions
            positions = get_open_positions(SYMBOL)
            if positions:
                logger.info(f"Open positions: {len(positions)}")
                for p in positions:
                    logger.info(f"  Ticket: {p['ticket']} | {p['type']} | "
                                f"Vol: {p['volume']} | P&L: ${p['profit']:+,.2f}")

            # Show daily stats
            stats = get_daily_stats()
            logger.info(f"Daily stats: trades={stats['trade_count']}, "
                        f"P&L=${stats['daily_pnl']:+,.2f}")

            # Wait before next check
            if iteration < max_iterations:
                logger.info(f"Waiting {check_interval_seconds}s before next check...")
                time.sleep(check_interval_seconds)

    except KeyboardInterrupt:
        logger.info("\nBot stopped by user (Ctrl+C).")

    finally:
        # --- Cleanup ---
        logger.info("Shutting down paper trader...")

        # Optionally close all bot positions on exit
        # Uncomment the next line if you want auto-close on stop:
        # close_all_bot_positions(SYMBOL)

        disconnect_mt5()

    logger.info("Paper trading bot stopped.")


# ============================================================
# Quick start: run this file directly
# ============================================================
if __name__ == "__main__":
    import sys

    print("=" * 55)
    print("  MT5 PAPER TRADING BOT")
    print("=" * 55)
    print(f"  Symbol    : {SYMBOL}")
    print(f"  Timeframe : {TIMEFRAME_STR}")
    print(f"  Mode      : {TRADING_MODE.upper()}")
    print()

    if TRADING_MODE != "demo":
        print("[ERROR] This script only runs in DEMO mode.")
        print("  Set TRADING_MODE=demo in your .env file.")
        sys.exit(1)

    print("Starting paper trading bot...")
    print("Press Ctrl+C to stop.\n")

    # Run with 60-second intervals, max 100 iterations
    # Adjust these for your needs:
    #   - check_interval_seconds: how often to check (60 = every minute)
    #   - max_iterations: safety limit (100 = stop after ~100 minutes)
    run_paper_bot(
        check_interval_seconds=60,
        max_iterations=100,
    )

"""
mt5/connection.py -- MT5 Terminal Connection Manager
=====================================================
Handles connecting to and disconnecting from MetaTrader 5.

HOW IT WORKS:
1. Calls MetaTrader5.initialize() to start a connection with the MT5 terminal.
2. Optionally logs in with account credentials from config.py (.env file).
3. Provides a clean shutdown function.

PREREQUISITES:
- MetaTrader 5 desktop terminal must be installed on this PC.
- The terminal must be open and running.
- You must be logged into a demo/live broker account in the terminal.
- "Algo Trading" must be enabled in MT5 settings.
"""

import sys
import MetaTrader5 as mt5
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH, get_logger

logger = get_logger(__name__)


def connect_mt5() -> bool:
    """
    Initialize connection to the MetaTrader 5 terminal.

    Steps:
      1. Call mt5.initialize() -- this starts the connection.
      2. If MT5_PATH is set in .env, it tells Python where the terminal exe is.
      3. After init, log in with your account credentials.
      4. Return True if everything worked, False otherwise.

    Returns:
        True if connected successfully, False if connection failed.
    """
    logger.info("Connecting to MetaTrader 5 terminal...")

    # --- Step 1: Initialize the MT5 terminal ---
    # If MT5_PATH is provided, use it; otherwise let MT5 auto-detect
    if MT5_PATH:
        initialized = mt5.initialize(path=MT5_PATH)
    else:
        initialized = mt5.initialize()

    if not initialized:
        error = mt5.last_error()
        logger.error(f"MT5 initialize() failed! Error: {error}")
        logger.error("CHECKLIST:")
        logger.error("  1. Is MetaTrader 5 desktop terminal installed?")
        logger.error("  2. Is the terminal currently running (open)?")
        logger.error("  3. Is MT5_PATH in .env correct?")
        return False

    logger.info("MT5 terminal initialized successfully.")

    # --- Step 2: Log in to the trading account ---
    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        logged_in = mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        if not logged_in:
            error = mt5.last_error()
            logger.error(f"MT5 login failed! Error: {error}")
            logger.error("CHECKLIST:")
            logger.error("  1. Are MT5_LOGIN, MT5_PASSWORD, MT5_SERVER correct in .env?")
            logger.error("  2. Is the broker server reachable (internet connected)?")
            logger.error("  3. Is it a valid demo/live account?")
            disconnect_mt5()
            return False

        logger.info(f"Logged in to account #{MT5_LOGIN} on {MT5_SERVER}")
    else:
        logger.warning("No login credentials in .env -- using currently logged-in account.")
        logger.warning("Make sure you are already logged in inside the MT5 terminal.")

    # --- Step 3: Print terminal info for confirmation ---
    terminal_info = mt5.terminal_info()
    if terminal_info is not None:
        logger.info(f"Terminal: {terminal_info.name}")
        logger.info(f"Company: {terminal_info.company}")
        logger.info(f"Connected: {terminal_info.connected}")
        logger.info(f"Trade allowed: {terminal_info.trade_allowed}")

        if not terminal_info.trade_allowed:
            logger.warning("Trade is NOT allowed! Enable 'Algo Trading' in MT5 settings.")
    else:
        logger.warning("Could not retrieve terminal info.")

    return True


def disconnect_mt5():
    """
    Cleanly shut down the MT5 connection.
    Always call this when you're done (like closing a file after reading it).
    """
    mt5.shutdown()
    logger.info("MetaTrader 5 connection closed.")


# ============================================================
# Quick test: run this file directly to test your connection
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  MT5 Connection Test")
    print("=" * 50)

    success = connect_mt5()

    if success:
        print("\n[OK] Connected to MT5 successfully!")
        print(f"  MT5 version: {mt5.version()}")
        disconnect_mt5()
        print("[OK] Disconnected cleanly.\n")
    else:
        print("\n[FAIL] Could not connect to MT5.")
        print("  Check the error messages above and fix your setup.\n")
        sys.exit(1)

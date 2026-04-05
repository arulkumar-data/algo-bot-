"""
mt5/account.py -- Account Information Reader
==============================================
Reads your trading account details from MetaTrader 5:
  - Account number, name, broker
  - Balance, equity, margin, free margin
  - Profit/loss
  - Account type and leverage

WHY THIS IS USEFUL:
  - Risk management needs to know your current balance
  - Position sizing is calculated from balance/equity
  - Daily loss tracking compares current equity to start-of-day balance

PREREQUISITE: You must call connect_mt5() first!
"""

import MetaTrader5 as mt5
from config import get_logger

logger = get_logger(__name__)


def get_account_info() -> dict | None:
    """
    Fetch current account information from MT5.

    Returns a dictionary with all account details, or None if it fails.

    Example return value:
    {
        "login": 12345678,
        "name": "John Doe",
        "server": "BrokerName-Demo",
        "balance": 10000.00,
        "equity": 10050.00,
        "margin": 200.00,
        "free_margin": 9850.00,
        "profit": 50.00,
        "leverage": 100,
        "currency": "USD",
        "trade_mode": "DEMO",
    }
    """
    # Fetch account info from MT5
    info = mt5.account_info()

    if info is None:
        error = mt5.last_error()
        logger.error(f"Failed to get account info! Error: {error}")
        logger.error("Make sure you are connected to MT5 first (call connect_mt5).")
        return None

    # Convert to a dictionary for easy use
    # mt5.account_info() returns a named tuple -- we pick the fields we need
    account = {
        "login":       info.login,
        "name":        info.name,
        "server":      info.server,
        "balance":     info.balance,
        "equity":      info.equity,
        "margin":      info.margin,
        "free_margin": info.margin_free,
        "profit":      info.profit,
        "leverage":    info.leverage,
        "currency":    info.currency,
        "trade_mode":  _trade_mode_name(info.trade_mode),
    }

    return account


def print_account_summary(account: dict):
    """
    Print a nicely formatted account summary to the console and log file.

    Args:
        account: Dictionary returned by get_account_info()
    """
    if account is None:
        logger.error("No account data to display.")
        return

    logger.info("=" * 50)
    logger.info("  ACCOUNT SUMMARY")
    logger.info("=" * 50)
    logger.info(f"  Login      : {account['login']}")
    logger.info(f"  Name       : {account['name']}")
    logger.info(f"  Server     : {account['server']}")
    logger.info(f"  Mode       : {account['trade_mode']}")
    logger.info(f"  Currency   : {account['currency']}")
    logger.info(f"  Leverage   : 1:{account['leverage']}")
    logger.info("-" * 50)
    logger.info(f"  Balance    : {account['balance']:.2f} {account['currency']}")
    logger.info(f"  Equity     : {account['equity']:.2f} {account['currency']}")
    logger.info(f"  Margin     : {account['margin']:.2f} {account['currency']}")
    logger.info(f"  Free Margin: {account['free_margin']:.2f} {account['currency']}")
    logger.info(f"  Profit     : {account['profit']:.2f} {account['currency']}")
    logger.info("=" * 50)


def _trade_mode_name(mode_code: int) -> str:
    """
    Convert MT5 trade mode integer to a human-readable string.

    MT5 trade mode codes:
      0 = ACCOUNT_TRADE_MODE_DEMO
      1 = ACCOUNT_TRADE_MODE_CONTEST
      2 = ACCOUNT_TRADE_MODE_REAL
    """
    modes = {
        0: "DEMO",
        1: "CONTEST",
        2: "REAL / LIVE",
    }
    return modes.get(mode_code, f"UNKNOWN ({mode_code})")


# ============================================================
# Quick test: run this file directly to see your account info
# ============================================================
if __name__ == "__main__":
    from mt5.connection import connect_mt5, disconnect_mt5

    print("=" * 50)
    print("  MT5 Account Info Test")
    print("=" * 50)

    if connect_mt5():
        account = get_account_info()
        if account:
            print_account_summary(account)
            print("\n[OK] Account info retrieved successfully!\n")
        else:
            print("\n[FAIL] Could not retrieve account info.\n")
        disconnect_mt5()
    else:
        print("[FAIL] Could not connect to MT5.\n")

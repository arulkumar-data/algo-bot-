"""
config.py — Central Configuration Loader
=========================================
Reads sensitive values from .env file.
Defines all strategy, risk, and trading constants in one place.
Every other module imports from here instead of hardcoding values.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# 1. Load .env file
# ============================================================
# The .env file should be in the same folder as this config.py
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ============================================================
# 2. MetaTrader 5 Credentials (from .env — never hardcode!)
# ============================================================
MT5_LOGIN    = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER   = os.getenv("MT5_SERVER", "")
MT5_PATH     = os.getenv("MT5_PATH", "")          # leave blank to auto-detect

# ============================================================
# 3. Trading Mode
# ============================================================
# "demo" = paper/demo trading only (safe)
# "live" = real-money trading (use with extreme caution!)
TRADING_MODE = os.getenv("TRADING_MODE", "demo").lower()

# Safety check: refuse to start in live mode unless explicitly confirmed
if TRADING_MODE not in ("demo", "live"):
    raise ValueError(f"Invalid TRADING_MODE='{TRADING_MODE}'. Must be 'demo' or 'live'.")

# ============================================================
# 4. Strategy Parameters (EMA Crossover v1)
# ============================================================
SYMBOL        = "EURUSD"       # Trading symbol
TIMEFRAME_STR = "M15"          # Human-readable timeframe label
EMA_FAST      = 20             # Fast EMA period
EMA_SLOW      = 50             # Slow EMA period
NUM_CANDLES   = 200            # How many candles to fetch for analysis

# Stop-loss and take-profit in pips
SL_PIPS = 50
TP_PIPS = 100

# Deviation / max allowed slippage in points
MAX_DEVIATION = 20

# ============================================================
# 5. Risk Management
# ============================================================
RISK_PER_TRADE   = 0.01        # 1% of account balance per trade
MAX_TRADES_DAY   = 5           # Maximum trades allowed per day
MAX_DAILY_LOSS   = 0.03        # 3% max daily drawdown — stop trading

# ============================================================
# 6. Logging Configuration
# ============================================================
LOG_DIR  = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "bot.log"

# Create logs directory if it doesn't exist
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL  = logging.INFO
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
LOG_DATE   = "%Y-%m-%d %H:%M:%S"

# ============================================================
# 7. Helper: get a configured logger for any module
# ============================================================
def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger that writes to both the console and the log file.
    Usage in any module:
        from config import get_logger
        logger = get_logger(__name__)
        logger.info("Hello from my module!")
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if not logger.handlers:
        logger.setLevel(LOG_LEVEL)

        # Console handler — prints to terminal
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVEL)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE))

        # File handler — writes to logs/bot.log
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(LOG_LEVEL)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE))

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger


# ============================================================
# 8. Quick sanity print (runs only when you execute config.py directly)
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  MT5 Algo Bot -- Configuration Check")
    print("=" * 60)
    print(f"  MT5 Login    : {MT5_LOGIN}")
    print(f"  MT5 Server   : {MT5_SERVER}")
    print(f"  MT5 Path     : {MT5_PATH or '(auto-detect)'}")
    print(f"  Trading Mode : {TRADING_MODE.upper()}")
    print(f"  Symbol       : {SYMBOL}")
    print(f"  Timeframe    : {TIMEFRAME_STR}")
    print(f"  EMA Fast     : {EMA_FAST}")
    print(f"  EMA Slow     : {EMA_SLOW}")
    print(f"  SL (pips)    : {SL_PIPS}")
    print(f"  TP (pips)    : {TP_PIPS}")
    print(f"  Risk/Trade   : {RISK_PER_TRADE * 100}%")
    print(f"  Max Trades   : {MAX_TRADES_DAY}/day")
    print(f"  Max Daily Loss: {MAX_DAILY_LOSS * 100}%")
    print(f"  Log File     : {LOG_FILE}")
    print("=" * 60)
    print("  ✅ Config loaded successfully!")
    print("=" * 60)

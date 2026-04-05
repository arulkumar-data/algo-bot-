"""
risk/rules.py -- Risk Management Rules
========================================
Pre-trade safety checks that MUST pass before any order is placed.

RULES:
  1. Max trades per day: Don't open more than N trades in one day
  2. Max daily loss: Stop trading if total daily loss exceeds X%
  3. Position sizing: Calculate correct lot size based on risk %
  4. Spread check: Don't trade if spread is too wide
  5. No duplicate position: Don't open if same-direction position exists

WHY RISK MANAGEMENT MATTERS:
  Without these rules, a bot could:
  - Open hundreds of trades in a loop
  - Lose your entire account in minutes
  - Trade during high-spread news events
  These rules are your SAFETY NET.
"""

import MetaTrader5 as mt5
from datetime import datetime, date
from config import (
    RISK_PER_TRADE,
    MAX_TRADES_DAY,
    MAX_DAILY_LOSS,
    SL_PIPS,
    get_logger,
)
from mt5.orders import BOT_MAGIC

logger = get_logger(__name__)

# Track daily stats (reset each new day)
_daily_stats = {
    "date": None,
    "trade_count": 0,
    "daily_pnl": 0.0,
    "starting_balance": 0.0,
}


def reset_daily_stats(balance: float):
    """
    Reset daily stats at the start of each trading day.
    Call this when the bot starts or when a new day begins.
    """
    _daily_stats["date"] = date.today()
    _daily_stats["trade_count"] = 0
    _daily_stats["daily_pnl"] = 0.0
    _daily_stats["starting_balance"] = balance
    logger.info(f"Daily stats reset. Starting balance: ${balance:,.2f}")


def record_trade(pnl: float):
    """Record a completed trade for daily stats tracking."""
    _check_new_day()
    _daily_stats["trade_count"] += 1
    _daily_stats["daily_pnl"] += pnl
    logger.info(f"Trade recorded: P&L=${pnl:+,.2f} | "
                f"Daily count: {_daily_stats['trade_count']} | "
                f"Daily P&L: ${_daily_stats['daily_pnl']:+,.2f}")


def pre_trade_checks(
    symbol: str,
    signal: str,
    account_balance: float,
    max_spread_pips: float = 5.0,
) -> tuple[bool, str]:
    """
    Run ALL safety checks before placing a trade.

    Args:
        symbol:          Trading symbol
        signal:          'BUY' or 'SELL'
        account_balance: Current account balance
        max_spread_pips: Maximum acceptable spread in pips

    Returns:
        (can_trade: bool, reason: str)
        - (True, "OK") if all checks pass
        - (False, "reason...") if any check fails
    """
    _check_new_day()

    # Check 1: Valid signal
    if signal not in ("BUY", "SELL"):
        return False, f"Invalid signal: '{signal}'"

    # Check 2: Max trades per day
    if _daily_stats["trade_count"] >= MAX_TRADES_DAY:
        msg = (f"Max daily trades reached ({MAX_TRADES_DAY}). "
               f"No more trades today.")
        logger.warning(msg)
        return False, msg

    # Check 3: Max daily loss
    if _daily_stats["starting_balance"] > 0:
        daily_loss_pct = abs(min(0, _daily_stats["daily_pnl"])) / _daily_stats["starting_balance"]
        if daily_loss_pct >= MAX_DAILY_LOSS:
            msg = (f"Max daily loss reached ({daily_loss_pct * 100:.1f}% >= "
                   f"{MAX_DAILY_LOSS * 100}%). Trading halted for today.")
            logger.warning(msg)
            return False, msg

    # Check 4: Spread check
    spread_ok, spread_msg = check_spread(symbol, max_spread_pips)
    if not spread_ok:
        return False, spread_msg

    # Check 5: No duplicate same-direction position
    dup_ok, dup_msg = check_no_duplicate(symbol, signal)
    if not dup_ok:
        return False, dup_msg

    # Check 6: Account balance sanity
    if account_balance <= 0:
        return False, "Account balance is zero or negative!"

    logger.info(f"Pre-trade checks PASSED for {signal} {symbol}")
    return True, "OK"


def check_spread(symbol: str, max_spread_pips: float = 5.0) -> tuple[bool, str]:
    """
    Check if the current spread is acceptable.

    High spreads occur during:
    - News events
    - Market open/close
    - Low liquidity periods

    Trading during high spread = worse entry = more cost.
    """
    sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        return False, f"Cannot get symbol info for {symbol}"

    spread_points = sym_info.spread
    # Convert spread from points to pips
    # For 5-digit brokers: 1 pip = 10 points
    spread_pips = spread_points / 10.0 if sym_info.digits == 5 else spread_points

    if spread_pips > max_spread_pips:
        msg = (f"Spread too high! Current: {spread_pips:.1f} pips > "
               f"Max: {max_spread_pips} pips. Skipping trade.")
        logger.warning(msg)
        return False, msg

    logger.info(f"Spread check OK: {spread_pips:.1f} pips (max: {max_spread_pips})")
    return True, "OK"


def check_no_duplicate(symbol: str, signal: str) -> tuple[bool, str]:
    """
    Check that we don't already have an open position in the same direction.

    Prevents accidentally doubling up on the same trade.
    """
    positions = mt5.positions_get(symbol=symbol)
    if positions is None or len(positions) == 0:
        return True, "OK"

    for pos in positions:
        if pos.magic != BOT_MAGIC:
            continue  # ignore manual trades

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        if pos_type == signal:
            msg = f"Already have an open {signal} position (ticket: {pos.ticket}). Skipping."
            logger.warning(msg)
            return False, msg

    return True, "OK"


def calculate_lot_size(
    balance: float,
    sl_pips: float = SL_PIPS,
    risk_fraction: float = RISK_PER_TRADE,
    pip_value: float = 0.0001,
    symbol: str = None,
) -> float:
    """
    Calculate position size based on risk management.

    Formula:
      risk_amount = balance * risk_fraction
      lot_size = risk_amount / (sl_pips * pip_value * 100000)

    Args:
        balance:       Current account balance
        sl_pips:       Stop loss distance in pips
        risk_fraction: Fraction to risk (0.01 = 1%)
        pip_value:     Price value of 1 pip
        symbol:        If provided, checks min/max lot constraints

    Returns:
        Lot size (rounded to 2 decimals, min 0.01)
    """
    risk_amount = balance * risk_fraction
    pip_value_per_lot = sl_pips * pip_value * 100000

    if pip_value_per_lot <= 0:
        return 0.01

    lot_size = risk_amount / pip_value_per_lot
    lot_size = max(0.01, round(lot_size, 2))

    # Respect broker min/max lot limits
    if symbol:
        sym_info = mt5.symbol_info(symbol)
        if sym_info:
            lot_size = max(sym_info.volume_min, lot_size)
            lot_size = min(sym_info.volume_max, lot_size)
            # Round to volume step
            step = sym_info.volume_step
            if step > 0:
                lot_size = round(lot_size / step) * step
                lot_size = round(lot_size, 2)

    logger.info(f"Lot size calculated: {lot_size} "
                f"(balance=${balance:,.0f}, risk={risk_fraction * 100}%, SL={sl_pips} pips)")

    return lot_size


def calculate_sl_tp_prices(
    symbol: str,
    order_type: str,
    sl_pips: float = SL_PIPS,
    tp_pips: float = None,
) -> tuple[float, float]:
    """
    Calculate SL and TP price levels from the current price.

    BUY order:
      SL = current price - sl_pips * point_value
      TP = current price + tp_pips * point_value

    SELL order:
      SL = current price + sl_pips * point_value
      TP = current price - tp_pips * point_value
    """
    from config import TP_PIPS
    if tp_pips is None:
        tp_pips = TP_PIPS

    tick = mt5.symbol_info_tick(symbol)
    sym_info = mt5.symbol_info(symbol)

    if tick is None or sym_info is None:
        logger.error(f"Cannot calculate SL/TP: tick or symbol info unavailable for {symbol}")
        return 0.0, 0.0

    point = sym_info.point
    # Convert pips to price: 1 pip = 10 points for 5-digit brokers
    pip_to_price = point * 10 if sym_info.digits == 5 else point

    if order_type.upper() == "BUY":
        price = tick.ask
        sl = round(price - sl_pips * pip_to_price, sym_info.digits)
        tp = round(price + tp_pips * pip_to_price, sym_info.digits)
    else:  # SELL
        price = tick.bid
        sl = round(price + sl_pips * pip_to_price, sym_info.digits)
        tp = round(price - tp_pips * pip_to_price, sym_info.digits)

    logger.info(f"SL/TP for {order_type} {symbol}: Price={price:.{sym_info.digits}f} "
                f"SL={sl:.{sym_info.digits}f} TP={tp:.{sym_info.digits}f}")

    return sl, tp


def get_daily_stats() -> dict:
    """Return current daily trading stats."""
    _check_new_day()
    return dict(_daily_stats)


def _check_new_day():
    """Auto-reset stats if a new day has started."""
    today = date.today()
    if _daily_stats["date"] != today:
        bal = _daily_stats.get("starting_balance", 0)
        reset_daily_stats(bal if bal > 0 else 10000)

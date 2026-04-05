"""
mt5/orders.py -- MT5 Order Management
=======================================
Sends, modifies, and closes trades on MetaTrader 5.

ORDER TYPES EXPLAINED:
  - Market Order: Buy/Sell immediately at current price
  - We use mt5.ORDER_TYPE_BUY and mt5.ORDER_TYPE_SELL
  - SL (Stop Loss): auto-close if price moves against you
  - TP (Take Profit): auto-close if price moves in your favor

SAFETY NOTES:
  - Always call connect_mt5() before using these functions
  - Always set SL and TP -- never trade without a stop loss!
  - The 'magic' number tags orders from this bot so you can identify them

PREREQUISITE: MT5 terminal must be connected (Phase 2).
"""

import MetaTrader5 as mt5
from config import MAX_DEVIATION, get_logger

logger = get_logger(__name__)

# Magic number to identify orders placed by this bot
# This helps you filter bot orders from manual orders in MT5
BOT_MAGIC = 234000


def send_market_order(
    symbol: str,
    order_type: str,
    lot_size: float,
    sl_price: float,
    tp_price: float,
    comment: str = "MT5_Bot_v1",
    deviation: int = MAX_DEVIATION,
) -> dict | None:
    """
    Send a market order (buy or sell) to MT5.

    Args:
        symbol:     Trading symbol, e.g. 'EURUSD'
        order_type: 'BUY' or 'SELL'
        lot_size:   Volume in lots (e.g. 0.01, 0.1, 1.0)
        sl_price:   Stop loss price level
        tp_price:   Take profit price level
        comment:    Order comment (shows in MT5 terminal)
        deviation:  Max allowed slippage in points

    Returns:
        Dictionary with order result, or None if failed.
    """
    # --- Step 1: Validate symbol ---
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"Symbol '{symbol}' not found!")
        return None

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logger.error(f"Failed to select symbol '{symbol}'")
            return None

    # --- Step 2: Get current price ---
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"Failed to get tick for {symbol}")
        return None

    # BUY at Ask price, SELL at Bid price
    if order_type.upper() == "BUY":
        mt5_order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    elif order_type.upper() == "SELL":
        mt5_order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        logger.error(f"Invalid order type: '{order_type}'. Must be 'BUY' or 'SELL'.")
        return None

    # --- Step 3: Build the order request ---
    request = {
        "action":    mt5.TRADE_ACTION_DEAL,       # market order
        "symbol":    symbol,
        "volume":    lot_size,
        "type":      mt5_order_type,
        "price":     price,
        "sl":        sl_price,
        "tp":        tp_price,
        "deviation": deviation,
        "magic":     BOT_MAGIC,
        "comment":   comment,
        "type_time": mt5.ORDER_TIME_GTC,           # good till cancelled
        "type_filling": mt5.ORDER_FILLING_IOC,     # immediate or cancel
    }

    logger.info(f"Sending {order_type} order: {symbol} | Lot: {lot_size} | "
                f"Price: {price:.5f} | SL: {sl_price:.5f} | TP: {tp_price:.5f}")

    # --- Step 4: Send the order ---
    result = mt5.order_send(request)

    if result is None:
        logger.error(f"order_send() returned None! Error: {mt5.last_error()}")
        return None

    # --- Step 5: Check result ---
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"Order EXECUTED successfully!")
        logger.info(f"  Ticket: {result.order}")
        logger.info(f"  Price:  {result.price}")
        logger.info(f"  Volume: {result.volume}")

        return {
            "success":  True,
            "ticket":   result.order,
            "price":    result.price,
            "volume":   result.volume,
            "type":     order_type,
            "symbol":   symbol,
            "sl":       sl_price,
            "tp":       tp_price,
            "comment":  result.comment,
        }
    else:
        logger.error(f"Order FAILED! Return code: {result.retcode}")
        logger.error(f"  Comment: {result.comment}")
        logger.error(f"  Request: {request}")
        _log_retcode(result.retcode)
        return None


def close_position(ticket: int, symbol: str = None) -> bool:
    """
    Close an open position by its ticket number.

    Args:
        ticket: The position ticket number (from send_market_order result)
        symbol: Trading symbol (if None, will look up from position)

    Returns:
        True if closed successfully, False otherwise
    """
    # Find the position
    positions = mt5.positions_get(ticket=ticket)
    if positions is None or len(positions) == 0:
        logger.error(f"Position with ticket {ticket} not found!")
        return False

    pos = positions[0]
    symbol = pos.symbol

    # Determine close type (opposite of open type)
    if pos.type == mt5.ORDER_TYPE_BUY:
        close_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        close_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask

    request = {
        "action":    mt5.TRADE_ACTION_DEAL,
        "symbol":    symbol,
        "volume":    pos.volume,
        "type":      close_type,
        "position":  ticket,
        "price":     price,
        "deviation": MAX_DEVIATION,
        "magic":     BOT_MAGIC,
        "comment":   "close_by_bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info(f"Closing position {ticket} | {symbol} | Vol: {pos.volume}")

    result = mt5.order_send(request)

    if result is None:
        logger.error(f"Close order returned None! Error: {mt5.last_error()}")
        return False

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"Position {ticket} closed successfully at {result.price}")
        return True
    else:
        logger.error(f"Failed to close position {ticket}! Code: {result.retcode}")
        _log_retcode(result.retcode)
        return False


def close_all_bot_positions(symbol: str = None) -> int:
    """
    Close all positions opened by this bot (identified by magic number).

    Args:
        symbol: If specified, only close positions for this symbol.

    Returns:
        Number of positions closed
    """
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()

    if positions is None or len(positions) == 0:
        logger.info("No open positions found.")
        return 0

    # Filter to only bot positions
    bot_positions = [p for p in positions if p.magic == BOT_MAGIC]

    if not bot_positions:
        logger.info("No bot positions found (looking for magic={BOT_MAGIC}).")
        return 0

    closed = 0
    for pos in bot_positions:
        if close_position(pos.ticket, pos.symbol):
            closed += 1

    logger.info(f"Closed {closed}/{len(bot_positions)} bot positions.")
    return closed


def get_open_positions(symbol: str = None) -> list:
    """
    Get all currently open positions (optionally filtered by symbol).

    Returns:
        List of position dictionaries
    """
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()

    if positions is None or len(positions) == 0:
        return []

    result = []
    for pos in positions:
        result.append({
            "ticket":     pos.ticket,
            "symbol":     pos.symbol,
            "type":       "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume":     pos.volume,
            "price_open": pos.price_open,
            "sl":         pos.sl,
            "tp":         pos.tp,
            "profit":     pos.profit,
            "magic":      pos.magic,
            "comment":    pos.comment,
        })

    return result


def _log_retcode(retcode: int):
    """Log human-readable explanation for common MT5 return codes."""
    codes = {
        10004: "REQUOTE -- price changed, try again",
        10006: "REJECT -- order rejected by broker",
        10007: "CANCEL -- order cancelled",
        10010: "DONE_PARTIAL -- partially filled",
        10013: "INVALID -- invalid request parameters",
        10014: "INVALID_VOLUME -- lot size out of range",
        10015: "INVALID_PRICE -- invalid price level",
        10016: "INVALID_STOPS -- invalid SL/TP levels",
        10018: "MARKET_CLOSED -- market is closed",
        10019: "NOT_ENOUGH_MONEY -- insufficient margin",
        10021: "NO_CHANGES -- no changes to order",
        10024: "TOO_MANY_ORDERS -- too many pending orders",
        10025: "NO_CHANGES -- no changes detected",
        10026: "SERVER_DISABLES_AT -- auto trading disabled on server",
        10027: "CLIENT_DISABLES_AT -- auto trading disabled in terminal",
    }
    msg = codes.get(retcode, f"Unknown return code: {retcode}")
    logger.error(f"  MT5 Return Code {retcode}: {msg}")

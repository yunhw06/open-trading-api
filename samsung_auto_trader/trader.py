# -*- coding: utf-8 -*-
"""
trader.py
---------
Core trading loop for the Samsung Electronics auto-trader.

Responsibilities
----------------
1.  Check whether the current time is inside the trading window
    (09:10 – 15:30 KST).
2.  Fetch the current price for 005930.
3.  Read account holdings and available cash (logged, not acted on for
    risk management – the logic only checks *whether* execution happened).
4.  Place a limit buy  at  current_price - BUY_OFFSET.
5.  Place a limit sell at  current_price + SELL_OFFSET.
6.  After each cycle, re-read holdings to check whether the orders were
    filled (best-effort check – execution confirmation via REST polling
    is approximate).
7.  Sleep POLL_INTERVAL_SECONDS between cycles.
8.  Stop automatically when the trading window closes.

Design notes
------------
- No websocket.  This is purely polling-based.
- The token is obtained once and reused; auth.get_access_token() handles
  same-day caching transparently.
- API calls per cycle: 1 price check + 2 balance checks (before/after)
  + 2 order submissions = ~5 calls per POLL_INTERVAL_SECONDS cycle.
"""

import time
from datetime import datetime, time as dt_time
from typing import Optional

import account
import auth
import config
import market_data
import orders
from account import AccountInfo
from logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Trading-window helpers
# ---------------------------------------------------------------------------

TRADE_START = dt_time(
    config.TRADE_START_HOUR, config.TRADE_START_MINUTE
)
TRADE_END = dt_time(
    config.TRADE_END_HOUR, config.TRADE_END_MINUTE
)


def _in_trading_window() -> bool:
    """Return ``True`` if local system time is within the trading window."""
    now = datetime.now().time()
    return TRADE_START <= now < TRADE_END


def _seconds_until_open() -> float:
    """Return seconds until the trading window opens (for pre-market sleep)."""
    now = datetime.now()
    target = now.replace(
        hour=config.TRADE_START_HOUR,
        minute=config.TRADE_START_MINUTE,
        second=0,
        microsecond=0,
    )
    diff = (target - now).total_seconds()
    return diff if diff > 0 else 0.0


# ---------------------------------------------------------------------------
# Per-cycle logic
# ---------------------------------------------------------------------------

def _log_holdings(label: str, info: Optional[AccountInfo]) -> None:
    """Log a summary of holdings with a descriptive label."""
    if info is None:
        logger.warning("[%s] Could not retrieve account info.", label)
        return

    logger.info(
        "[%s] Cash: %d KRW | Positions: %d",
        label, info.cash_balance, len(info.holdings),
    )
    for h in info.holdings:
        logger.info(
            "[%s]   %s (%s): qty=%d  avg=%.0f  current=%d  P/L=%.0f",
            label, h.symbol, h.name, h.qty, h.avg_price, h.current_price, h.profit_loss,
        )


def _check_execution(before: Optional[AccountInfo], after: Optional[AccountInfo]) -> None:
    """
    Compare holdings before and after orders to guess whether execution occurred.

    This is a best-effort confirmation.  For exact fill data a dedicated
    order-status API would be needed; that call is omitted here to conserve
    mock-environment rate-limit budget.
    """
    if before is None or after is None:
        return

    before_qty = sum(h.qty for h in before.holdings if h.symbol == config.SYMBOL)
    after_qty  = sum(h.qty for h in after.holdings  if h.symbol == config.SYMBOL)
    cash_diff  = after.cash_balance - before.cash_balance

    if after_qty != before_qty:
        logger.info(
            "[Execution] Quantity changed %d → %d for %s (Δ%+d).",
            before_qty, after_qty, config.SYMBOL, after_qty - before_qty,
        )
    else:
        logger.info(
            "[Execution] Quantity unchanged (%d). Orders may still be pending.",
            after_qty,
        )

    if cash_diff != 0:
        logger.info("[Execution] Cash changed by %+d KRW.", cash_diff)


def run_one_cycle(
    token: str,
    creds: config.Credentials,
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> None:
    """
    Execute a single trading cycle:

    1. Fetch price.
    2. Fetch holdings (before).
    3. Place buy order.
    4. Place sell order.
    5. Fetch holdings (after) and log execution confirmation.

    If the price or any critical step fails, the cycle is logged and skipped
    gracefully.

    Args:
        token:    Valid Bearer access token.
        creds:    Credentials object.
        base_url: API base URL.
        is_mock:  ``True`` for mock trading.
    """
    logger.info("=" * 60)
    logger.info("[Cycle] Starting trading cycle at %s", datetime.now().strftime("%H:%M:%S"))

    # --- Step 1: current price ------------------------------------------
    price = market_data.get_current_price(token, creds, base_url=base_url)
    if price is None:
        logger.warning("[Cycle] Skipping cycle – could not retrieve current price.")
        return

    buy_price  = price - config.BUY_OFFSET
    sell_price = price + config.SELL_OFFSET
    logger.info(
        "[Cycle] Price=%d  BuyLimit=%d  SellLimit=%d",
        price, buy_price, sell_price,
    )

    # Guard against negative buy price
    if buy_price <= 0:
        logger.warning(
            "[Cycle] Calculated buy price %d <= 0 – skipping orders.", buy_price
        )
        return

    # --- Step 2: holdings before -----------------------------------------
    info_before = account.get_account_info(token, creds, base_url, is_mock)
    _log_holdings("Before", info_before)

    # --- Step 3: buy order -----------------------------------------------
    buy_result = orders.place_buy_order(
        token=token,
        creds=creds,
        symbol=config.SYMBOL,
        qty=config.ORDER_QTY,
        price=buy_price,
        base_url=base_url,
        is_mock=is_mock,
    )
    if not buy_result.ok:
        logger.error("[Cycle] Buy order failed: %s", buy_result.error)
    else:
        logger.info(
            "[Cycle] Buy order submitted: order_no=%s price=%d qty=%d",
            buy_result.order_no, buy_result.price, buy_result.qty,
        )

    # --- Step 4: sell order ----------------------------------------------
    sell_result = orders.place_sell_order(
        token=token,
        creds=creds,
        symbol=config.SYMBOL,
        qty=config.ORDER_QTY,
        price=sell_price,
        base_url=base_url,
        is_mock=is_mock,
    )
    if not sell_result.ok:
        logger.error("[Cycle] Sell order failed: %s", sell_result.error)
    else:
        logger.info(
            "[Cycle] Sell order submitted: order_no=%s price=%d qty=%d",
            sell_result.order_no, sell_result.price, sell_result.qty,
        )

    # --- Step 5: holdings after ------------------------------------------
    info_after = account.get_account_info(token, creds, base_url, is_mock)
    _log_holdings("After", info_after)

    _check_execution(info_before, info_after)


# ---------------------------------------------------------------------------
# Main trading loop
# ---------------------------------------------------------------------------

def run_trading_loop(
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> None:
    """
    Run the trading loop until the market closes.

    - Before the window opens, the process sleeps until 09:10 (or exits if
      the window has already closed for today).
    - Inside the window, run_one_cycle() is called every
      ``POLL_INTERVAL_SECONDS`` seconds.
    - After 15:30, a final log message is written and the function returns.

    Args:
        base_url: API base URL (default: mock environment).
        is_mock:  ``True`` for mock trading (affects TR_IDs used for orders
                  and balance queries).
    """
    # --- Load credentials once -------------------------------------------
    try:
        creds = config.load_credentials()
    except EnvironmentError as exc:
        logger.critical("[Trader] %s", exc)
        return

    # --- Authenticate once (token reused for the whole day) --------------
    try:
        token = auth.get_access_token(creds, base_url=base_url)
    except RuntimeError as exc:
        logger.critical("[Trader] Authentication failed: %s", exc)
        return

    logger.info("[Trader] Authentication successful.  Token cached.")
    logger.info(
        "[Trader] Trading window: %02d:%02d – %02d:%02d",
        config.TRADE_START_HOUR, config.TRADE_START_MINUTE,
        config.TRADE_END_HOUR, config.TRADE_END_MINUTE,
    )

    # --- Wait for the window to open if we started early -----------------
    now = datetime.now().time()
    if now < TRADE_START:
        wait_secs = _seconds_until_open()
        logger.info(
            "[Trader] Market not open yet. Waiting %.0f seconds until %02d:%02d …",
            wait_secs,
            config.TRADE_START_HOUR,
            config.TRADE_START_MINUTE,
        )
        time.sleep(wait_secs)
    elif now >= TRADE_END:
        logger.info("[Trader] Trading window has already closed for today. Exiting.")
        return

    logger.info("[Trader] Trading window is open.  Starting polling loop.")

    # --- Main loop -------------------------------------------------------
    while _in_trading_window():
        try:
            run_one_cycle(token=token, creds=creds, base_url=base_url, is_mock=is_mock)
        except Exception as exc:
            # Broad catch so an unexpected error doesn't crash the loop.
            logger.exception("[Trader] Unexpected error in trading cycle: %s", exc)

        if not _in_trading_window():
            break

        logger.info(
            "[Trader] Sleeping %d seconds until next cycle …",
            config.POLL_INTERVAL_SECONDS,
        )
        time.sleep(config.POLL_INTERVAL_SECONDS)

    logger.info("[Trader] Trading window has closed.  Session complete.")

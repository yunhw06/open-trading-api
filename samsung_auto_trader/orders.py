# -*- coding: utf-8 -*-
"""
orders.py
---------
Place buy and sell orders for KRX-listed stocks (cash, limit-price orders).

Public functions
----------------
- :func:`place_buy_order`  – submit a limit buy order.
- :func:`place_sell_order` – submit a limit sell order.

Both return an :class:`OrderResult` dataclass so callers do not need to
inspect raw API payloads.

API reference
-------------
[국내주식] 주문/계좌 > 주식주문(현금) [v1_국내주식-001]
  POST /uapi/domestic-stock/v1/trading/order-cash
  TR_ID buy  (real) : TTTC0012U    (mock) : VTTC0012U
  TR_ID sell (real) : TTTC0011U    (mock) : VTTC0011U

Important
---------
The body keys MUST be upper-case (e.g. ``"CANO"``, not ``"cano"``).
ORD_QTY and ORD_UNPR must be passed as strings even though they represent
integers.
"""

from dataclasses import dataclass
from typing import Optional

import api_client
import config
from logger import get_logger

logger = get_logger(__name__)

_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OrderResult:
    """Outcome of a single order submission."""
    ok: bool                  # True = API accepted the order
    order_no: str             # KRX order number (odno) – empty on failure
    order_time: str           # Execution time returned by the API
    symbol: str               # Stock code
    side: str                 # "buy" or "sell"
    qty: int                  # Ordered quantity
    price: int                # Limit price in KRW
    error: str = ""           # Non-empty when ok=False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_order_payload(
    creds: config.Credentials,
    symbol: str,
    qty: int,
    price: int,
    side: str,
) -> dict:
    """
    Build the POST body for the order-cash endpoint.

    Note: all field names are UPPER-CASE as required by the API.
    """
    # SLL_TYPE is required only for sell orders; blank for buy orders.
    sll_type = "01" if side == "sell" else ""

    return {
        "CANO": creds.cano,
        "ACNT_PRDT_CD": creds.acnt_prdt_cd,
        "PDNO": symbol,
        "ORD_DVSN": config.ORD_DVSN_LIMIT,   # "00" = 지정가 (limit price)
        "ORD_QTY": str(qty),
        "ORD_UNPR": str(price),
        "EXCG_ID_DVSN_CD": config.EXCHANGE,   # "KRX"
        "SLL_TYPE": sll_type,
        "CNDT_PRIC": "",                       # Not used for plain limit orders
    }


def _submit_order(
    side: str,
    token: str,
    creds: config.Credentials,
    symbol: str,
    qty: int,
    price: int,
    base_url: str,
    is_mock: bool,
) -> OrderResult:
    """Internal dispatcher – shared by buy and sell paths."""
    if side == "buy":
        tr_id = config.TR_ORDER_BUY_MOCK if is_mock else config.TR_ORDER_BUY_REAL
    else:
        tr_id = config.TR_ORDER_SELL_MOCK if is_mock else config.TR_ORDER_SELL_REAL

    payload = _build_order_payload(creds, symbol, qty, price, side)

    logger.info(
        "[Order] Submitting %s order: symbol=%s qty=%d price=%d KRW (tr_id=%s)",
        side.upper(), symbol, qty, price, tr_id,
    )

    resp = api_client.post(
        base_url=base_url,
        path=_ORDER_PATH,
        token=token,
        appkey=creds.appkey,
        appsecret=creds.appsecret,
        tr_id=tr_id,
        payload=payload,
    )

    if not resp.ok:
        logger.error(
            "[Order] %s order FAILED: %s", side.upper(), resp.error
        )
        return OrderResult(
            ok=False,
            order_no="",
            order_time="",
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            error=resp.error,
        )

    output = resp.output()
    order_no = ""
    order_time = ""
    if isinstance(output, dict):
        order_no = output.get("odno", "")       # 주문번호
        order_time = output.get("ord_tmd", "")  # 주문시각

    logger.info(
        "[Order] %s order accepted: order_no=%s time=%s",
        side.upper(), order_no, order_time,
    )

    return OrderResult(
        ok=True,
        order_no=order_no,
        order_time=order_time,
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def place_buy_order(
    token: str,
    creds: config.Credentials,
    symbol: str = config.SYMBOL,
    qty: int = config.ORDER_QTY,
    price: int = 0,
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> OrderResult:
    """
    Submit a limit buy order.

    Args:
        token:    Valid Bearer access token.
        creds:    Credentials object.
        symbol:   KRX 6-digit stock code.
        qty:      Number of shares to buy.
        price:    Limit price in KRW (e.g. current_price - BUY_OFFSET).
        base_url: API base URL.
        is_mock:  ``True`` for mock trading.

    Returns:
        :class:`OrderResult`
    """
    return _submit_order(
        side="buy",
        token=token,
        creds=creds,
        symbol=symbol,
        qty=qty,
        price=price,
        base_url=base_url,
        is_mock=is_mock,
    )


def place_sell_order(
    token: str,
    creds: config.Credentials,
    symbol: str = config.SYMBOL,
    qty: int = config.ORDER_QTY,
    price: int = 0,
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> OrderResult:
    """
    Submit a limit sell order.

    Args:
        token:    Valid Bearer access token.
        creds:    Credentials object.
        symbol:   KRX 6-digit stock code.
        qty:      Number of shares to sell.
        price:    Limit price in KRW (e.g. current_price + SELL_OFFSET).
        base_url: API base URL.
        is_mock:  ``True`` for mock trading.

    Returns:
        :class:`OrderResult`
    """
    return _submit_order(
        side="sell",
        token=token,
        creds=creds,
        symbol=symbol,
        qty=qty,
        price=price,
        base_url=base_url,
        is_mock=is_mock,
    )

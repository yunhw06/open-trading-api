# -*- coding: utf-8 -*-
"""
market_data.py
--------------
Fetch current market price for a KRX-listed stock.

The only public function is :func:`get_current_price`, which returns the
latest trading price as an integer (KRW).

API reference
-------------
[국내주식] 기본시세 > 주식현재가 시세 [v1_국내주식-008]
  GET /uapi/domestic-stock/v1/quotations/inquire-price
  TR_ID : FHKST01010100  (same for real and mock trading)
"""

from typing import Optional

import api_client
import config
from logger import get_logger

logger = get_logger(__name__)

_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"


def get_current_price(
    token: str,
    creds: config.Credentials,
    symbol: str = config.SYMBOL,
    base_url: str = config.MOCK_BASE_URL,
) -> Optional[int]:
    """
    Return the current (latest) trading price for *symbol* in KRW.

    The price is read from the ``stck_prpr`` field of the API response, which
    holds the 주식 현재가 (current stock price).

    Args:
        token:    Valid Bearer access token.
        creds:    Credentials (appkey / appsecret).
        symbol:   KRX 6-digit stock code (default: ``config.SYMBOL``).
        base_url: API base URL (default: mock environment).

    Returns:
        Current price as an integer, or ``None`` if the call fails.
    """
    params = {
        "FID_COND_MRKT_DIV_CODE": config.MARKET_CODE,
        "FID_INPUT_ISCD": symbol,
    }

    resp = api_client.get(
        base_url=base_url,
        path=_PRICE_PATH,
        token=token,
        appkey=creds.appkey,
        appsecret=creds.appsecret,
        tr_id=config.TR_INQUIRE_PRICE,
        params=params,
    )

    if not resp.ok:
        logger.error(
            "[MarketData] Failed to fetch price for %s: %s", symbol, resp.error
        )
        return None

    output = resp.output()
    if output is None:
        logger.error("[MarketData] No 'output' field in response body.")
        return None

    # stck_prpr: 주식 현재가 (string in API response)
    price_str: str = output.get("stck_prpr", "")
    if not price_str:
        logger.error("[MarketData] 'stck_prpr' field missing in output: %s", output)
        return None

    try:
        price = int(price_str)
    except ValueError:
        logger.error(
            "[MarketData] Could not parse price '%s' as integer.", price_str
        )
        return None

    logger.info("[MarketData] %s current price: %d KRW", symbol, price)
    return price

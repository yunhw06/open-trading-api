# -*- coding: utf-8 -*-
"""
config.py
---------
All configuration constants and environment variable loading.

Required environment variables
-------------------------------
GH_ACCOUNT   : Trading account number.
               Accepted formats:
                 - "12345678-01"  (hyphen-separated 8+2)
                 - "1234567801"   (plain 10-digit string)
GH_APPKEY    : Korea Investment Open API App Key (mock trading key).
GH_APPSECRET : Korea Investment Open API App Secret (mock trading secret).

No credentials are ever hard-coded here.
"""

import os
from dataclasses import dataclass

from logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------
MOCK_BASE_URL: str = "https://openapivts.koreainvestment.com:29443"
REAL_BASE_URL: str = "https://openapi.koreainvestment.com:9443"

# ---------------------------------------------------------------------------
# Trading target
# ---------------------------------------------------------------------------
SYMBOL: str = "005930"          # Samsung Electronics KRX code
EXCHANGE: str = "KRX"           # Exchange identifier used in order API
MARKET_CODE: str = "J"          # FID_COND_MRKT_DIV_CODE for KRX equities

# ---------------------------------------------------------------------------
# Order pricing offsets (KRW below / above current price)
# Change these values to adjust the spread.
# ---------------------------------------------------------------------------
BUY_OFFSET: int = 1_000         # Buy limit = current_price - BUY_OFFSET
SELL_OFFSET: int = 1_000        # Sell limit = current_price + SELL_OFFSET

# ---------------------------------------------------------------------------
# Order quantity (number of shares per order)
# ---------------------------------------------------------------------------
ORDER_QTY: int = 1

# ---------------------------------------------------------------------------
# Trading window (KST / Korean Standard Time = UTC+9)
# The loop only places orders inside [TRADE_START, TRADE_END).
# ---------------------------------------------------------------------------
TRADE_START_HOUR: int = 9
TRADE_START_MINUTE: int = 10
TRADE_END_HOUR: int = 15
TRADE_END_MINUTE: int = 30

# ---------------------------------------------------------------------------
# Polling interval between trading loop iterations (seconds)
# Keep conservatively high for mock environment rate limits.
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS: int = 60

# ---------------------------------------------------------------------------
# HTTP settings
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT_SECONDS: int = 10
MAX_RETRIES: int = 3
RETRY_BACKOFF_SECONDS: float = 2.0

# ---------------------------------------------------------------------------
# Token cache file (written next to this file at runtime)
# ---------------------------------------------------------------------------
TOKEN_CACHE_FILE: str = "token_cache.json"

# ---------------------------------------------------------------------------
# TR_IDs  (transaction IDs for each API endpoint)
# These are isolated here so they can be easily edited if the API spec changes.
# ---------------------------------------------------------------------------

# Price inquiry – same TR_ID for real and mock
TR_INQUIRE_PRICE: str = "FHKST01010100"

# Balance inquiry
TR_BALANCE_REAL: str = "TTTC8434R"
TR_BALANCE_MOCK: str = "VTTC8434R"

# Order (cash) – buy
TR_ORDER_BUY_REAL: str = "TTTC0012U"
TR_ORDER_BUY_MOCK: str = "VTTC0012U"

# Order (cash) – sell
TR_ORDER_SELL_REAL: str = "TTTC0011U"
TR_ORDER_SELL_MOCK: str = "VTTC0011U"

# Limit-order division code ("00" = 지정가 / limit price order)
ORD_DVSN_LIMIT: str = "00"


# ---------------------------------------------------------------------------
# Credentials loaded from environment variables
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Credentials:
    """Holds the three credentials required by the API."""
    account_no: str       # Full account string, e.g. "1234567801"
    cano: str             # First 8 digits (종합계좌번호)
    acnt_prdt_cd: str     # Last 2 digits  (계좌상품코드)
    appkey: str
    appsecret: str


def load_credentials() -> Credentials:
    """
    Read credentials from environment variables and return a :class:`Credentials`
    instance.

    Raises:
        EnvironmentError: If any required variable is missing or the account
                          number cannot be parsed into an 8+2 format.
    """
    account_raw = os.environ.get("GH_ACCOUNT", "").strip()
    appkey = os.environ.get("GH_APPKEY", "").strip()
    appsecret = os.environ.get("GH_APPSECRET", "").strip()

    missing = [name for name, val in (
        ("GH_ACCOUNT", account_raw),
        ("GH_APPKEY", appkey),
        ("GH_APPSECRET", appsecret),
    ) if not val]

    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    # Normalise account number: remove hyphens, then split 8+2
    account_no = account_raw.replace("-", "")
    if len(account_no) != 10 or not account_no.isdigit():
        raise EnvironmentError(
            f"GH_ACCOUNT must be a 10-digit number (or '8-digit-2-digit' format). "
            f"Got: '{account_raw}'"
        )

    cano = account_no[:8]
    acnt_prdt_cd = account_no[8:]

    logger.debug("Credentials loaded. Account: %s-**", cano)

    return Credentials(
        account_no=account_no,
        cano=cano,
        acnt_prdt_cd=acnt_prdt_cd,
        appkey=appkey,
        appsecret=appsecret,
    )

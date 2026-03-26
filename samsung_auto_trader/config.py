# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - Configuration.

Loads settings from environment variables.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Trading system configuration loaded from environment variables."""

    # Account settings (populated in __post_init__ after validation)
    ACCOUNT: str = field(default="")
    APP_KEY: str = field(default="")
    APP_SECRET: str = field(default="")

    # Trading target
    STOCK_CODE: str = "005930"  # Samsung Electronics

    # API settings
    BASE_URL: str = "https://openapivts.koreainvestment.com:9443"  # mock trading
    TOKEN_ENDPOINT: str = "/oauth2/tokenP"
    PRICE_ENDPOINT: str = "/uapi/domestic-stock/v1/quotations/inquire-price"
    ORDER_ENDPOINT: str = "/uapi/domestic-stock/v1/trading/order-cash"
    BALANCE_ENDPOINT: str = "/uapi/domestic-stock/v1/trading/inquire-balance"

    # Polling intervals (seconds)
    POLL_INTERVAL: int = 30          # Normal polling interval (was 10 - too aggressive)
    POLL_INTERVAL_OUTSIDE: int = 60  # Interval outside trading window

    # Retry / circuit-breaker settings
    MAX_RETRIES: int = 3             # Maximum retry attempts per request
    RETRY_BASE_DELAY: float = 2.0    # Initial retry delay in seconds (was 1.0)
    RETRY_MAX_DELAY: float = 60.0    # Maximum retry delay in seconds
    CIRCUIT_BREAK_THRESHOLD: int = 5  # Consecutive failures before circuit opens
    CIRCUIT_BREAK_RESET: int = 3600   # Seconds to wait before half-opening circuit (1 hour)

    # Trading window (KST)
    TRADING_START: str = "09:00"
    TRADING_END: str = "15:30"

    # Logging
    LOG_FILE: str = "trading.log"
    LOG_LEVEL: str = "INFO"

    def __post_init__(self) -> None:
        missing = []
        for var in ("GH_ACCOUNT", "GH_APPKEY", "GH_APPSECRET"):
            if not os.environ.get(var):
                missing.append(var)
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Please set them before running:\n"
                "  export GH_ACCOUNT=<account>\n"
                "  export GH_APPKEY=<app_key>\n"
                "  export GH_APPSECRET=<app_secret>"
            )
        # Populate credentials from environment after validation
        self.ACCOUNT = os.environ["GH_ACCOUNT"]
        self.APP_KEY = os.environ["GH_APPKEY"]
        self.APP_SECRET = os.environ["GH_APPSECRET"]

    def __str__(self) -> str:
        account_masked = self.ACCOUNT[:4] + "****" if len(self.ACCOUNT) >= 4 else "****"
        return (
            f"Config(account={account_masked}, stock={self.STOCK_CODE}, "
            f"poll_interval={self.POLL_INTERVAL}s)"
        )

# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - Core trading loop.

Fixes applied vs. original implementation
──────────────────────────────────────────
1. Polling interval increased from 10 s to Config.POLL_INTERVAL (default 30 s)
   outside trading-window sleeps use POLL_INTERVAL_OUTSIDE (default 60 s).

2. Error-state tracking: consecutive_errors counter is incremented on every
   cycle that fails to obtain a price.  When the counter reaches
   MAX_ERRORS_BEFORE_LONG_SLEEP the loop backs off for
   LONG_ERROR_SLEEP_SECONDS (1 hour by default) before resuming.
   This prevents the "infinite retry" pattern observed in the logs.

3. The circuit-breaker in APIClient prevents lower-level request storms.
   Trader co-operates by catching CircuitOpenError and skipping the cycle
   rather than spinning.

4. Trading-window guard: API calls are only attempted when the Korean
   stock exchange is open.  Outside window → lightweight sleep, no API hits.
"""

import time
from datetime import datetime, time as dtime
from typing import Optional

from api_client import APIClient, CircuitOpenError
from auth import TokenManager
from config import Config
from logger import TradingLogger
from market_data import MarketData

# After this many consecutive errors without a successful price read,
# pause for LONG_ERROR_SLEEP_SECONDS before trying again.
_MAX_ERRORS_BEFORE_LONG_SLEEP = 3
_LONG_ERROR_SLEEP_SECONDS = 3600  # 1 hour


class Trader:
    """Simple momentum-based trader for a single stock."""

    def __init__(
        self,
        config: Config,
        logger: TradingLogger,
        token: str,
    ) -> None:
        self._config = config
        self._logger = logger
        self._token = token

        self._client = APIClient(
            base_url=config.BASE_URL,
            app_key=config.APP_KEY,
            app_secret=config.APP_SECRET,
            token=token,
            logger=logger,
            max_retries=config.MAX_RETRIES,
            retry_base_delay=config.RETRY_BASE_DELAY,
            retry_max_delay=config.RETRY_MAX_DELAY,
            circuit_break_threshold=config.CIRCUIT_BREAK_THRESHOLD,
            circuit_break_reset=config.CIRCUIT_BREAK_RESET,
        )
        self._market_data = MarketData(self._client, logger)
        self._consecutive_errors: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run_trading_loop(self) -> None:
        """
        Main trading loop.  Runs until interrupted (KeyboardInterrupt).

        The loop honours the Korean stock-exchange trading window and
        applies adaptive backoff when errors accumulate, preventing the
        server from being hammered by repeated failing requests.
        """
        self._logger.info("[LOOP] Trading loop started.")
        try:
            while True:
                now = datetime.now()

                if not self._is_trading_window(now):
                    self._logger.debug(
                        f"[WINDOW] Outside trading window ({now.strftime('%H:%M')}). "
                        f"Sleeping {self._config.POLL_INTERVAL_OUTSIDE}s."
                    )
                    time.sleep(self._config.POLL_INTERVAL_OUTSIDE)
                    continue

                self._run_cycle(now)
                time.sleep(self._config.POLL_INTERVAL)

        except KeyboardInterrupt:
            self._logger.info("[LOOP] Trading loop stopped by user.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_trading_window(self, now: datetime) -> bool:
        """Return True if *now* (KST) is within the configured trading window."""
        start = dtime.fromisoformat(self._config.TRADING_START)
        end = dtime.fromisoformat(self._config.TRADING_END)
        return start <= now.time() <= end

    def _run_cycle(self, now: datetime) -> None:
        """Execute one trading cycle: fetch price → decide → (optionally) trade."""
        self._logger.info(f"[CYCLE] Starting new trading cycle at {now.strftime('%H:%M:%S')}")

        try:
            price = self._market_data.get_current_price(self._config.STOCK_CODE)
        except CircuitOpenError as exc:
            self._logger.warning(f"[CYCLE] Skipping – circuit open: {exc}")
            self._handle_error()
            return

        if price is None:
            self._logger.warning("[CYCLE] Could not retrieve current price – skipping cycle.")
            self._handle_error()
            return

        # Price retrieved successfully – reset error counter
        self._consecutive_errors = 0
        self._logger.info(
            f"[CYCLE] {self._config.STOCK_CODE} current price: {price:,} KRW"
        )

        # Placeholder: add buy/sell decision logic here
        self._logger.debug("[CYCLE] No trade action taken (strategy not yet implemented).")

    def _handle_error(self) -> None:
        """
        Track consecutive errors and apply a long sleep when the threshold
        is reached to avoid hammering a failing or blocked API endpoint.
        """
        self._consecutive_errors += 1
        self._logger.warning(
            f"[ERROR] Consecutive error count: {self._consecutive_errors}/"
            f"{_MAX_ERRORS_BEFORE_LONG_SLEEP}"
        )
        if self._consecutive_errors >= _MAX_ERRORS_BEFORE_LONG_SLEEP:
            self._logger.error(
                f"[ERROR] {self._consecutive_errors} consecutive failures – "
                f"backing off for {_LONG_ERROR_SLEEP_SECONDS}s to avoid server overload."
            )
            time.sleep(_LONG_ERROR_SLEEP_SECONDS)
            self._consecutive_errors = 0

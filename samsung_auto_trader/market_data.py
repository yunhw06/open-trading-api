# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - Market data retrieval.

Fix applied
───────────
Previously, get_current_price() called the same API endpoint 3 times
(lines 55-57 of the original code), with each successive response
overwriting the previous one.  The method now issues a **single** API
call and returns its result directly, reducing KIS API load by ~66 %
for every price-check cycle.
"""

from typing import Optional

from api_client import APIClient, APIError, CircuitOpenError
from logger import TradingLogger


class MarketData:
    """Fetches real-time market data for a single stock symbol."""

    # KIS endpoint / TR-ID for domestic stock current price
    _PRICE_ENDPOINT = "/uapi/domestic-stock/v1/quotations/inquire-price"
    _PRICE_TR_ID = "FHKST01010100"

    def __init__(self, client: APIClient, logger: TradingLogger) -> None:
        self._client = client
        self._logger = logger

    def get_current_price(self, stock_code: str) -> Optional[int]:
        """
        Return the current price of *stock_code* in KRW, or *None* on failure.

        Only **one** API call is made per invocation.  The previous
        implementation issued three identical calls in sequence, causing
        unnecessary load on the KIS server.

        Args:
            stock_code: KRX stock code, e.g. "005930" for Samsung Electronics.

        Returns:
            Current price as an integer, or None if the request fails.
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }

        try:
            # Single API call (previously called 3 times, overwriting results)
            data = self._client.get(
                self._PRICE_ENDPOINT,
                params=params,
                tr_id=self._PRICE_TR_ID,
            )
            output = data.get("output", {})
            raw_price = output.get("stck_prpr", "")
            if raw_price:
                return int(raw_price)
            self._logger.warning(
                f"[MARKET] Price field missing in response for {stock_code}"
            )
            return None

        except CircuitOpenError as exc:
            self._logger.warning(f"[MARKET] Circuit open – skipping price fetch: {exc}")
            return None
        except APIError as exc:
            self._logger.error(f"[MARKET] Failed to fetch price for {stock_code}: {exc}")
            return None
        except (ValueError, KeyError) as exc:
            self._logger.error(f"[MARKET] Unexpected response format for {stock_code}: {exc}")
            return None

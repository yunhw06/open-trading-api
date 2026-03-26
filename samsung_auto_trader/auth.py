# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - Authentication / token management.

TokenManager obtains an OAuth2 access token from the KIS mock trading
server and caches it for 24 hours so the rest of the application does
not need to worry about re-authentication.
"""

import time
from typing import Optional

import requests

from config import Config
from logger import TradingLogger

_TOKEN_TTL_SECONDS = 86400  # 24 hours (KIS token validity)
_REQUEST_TIMEOUT = 10


class TokenManager:
    """Manages OAuth2 bearer-token lifecycle for the KIS API."""

    def __init__(self, config: Config, logger: TradingLogger) -> None:
        self._config = config
        self._logger = logger
        self._token: Optional[str] = None
        self._obtained_at: float = 0.0

    def get_token(self) -> Optional[str]:
        """Return a valid bearer token, refreshing it if necessary."""
        if self._token and not self._is_expired():
            return self._token
        return self._fetch_token()

    def _is_expired(self) -> bool:
        return (time.time() - self._obtained_at) >= _TOKEN_TTL_SECONDS

    def _fetch_token(self) -> Optional[str]:
        """Request a new token from KIS and cache it."""
        url = f"{self._config.BASE_URL}{self._config.TOKEN_ENDPOINT}"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._config.APP_KEY,
            "appsecret": self._config.APP_SECRET,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                if token:
                    self._token = token
                    self._obtained_at = time.time()
                    self._logger.info("[AUTH] Access token obtained successfully.")
                    return self._token
            self._logger.error(
                f"[AUTH] Token request failed – HTTP {resp.status_code}: {resp.text[:200]}"
            )
        except requests.RequestException as exc:
            self._logger.error(f"[AUTH] Network error during token request: {exc}")
        return None

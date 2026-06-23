# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - API Client.

Wraps HTTP calls to the KIS REST API with:
  - Exponential backoff on transient failures (fixes: fixed 1-second retry delay)
  - Circuit-breaker pattern to stop hammering a failing endpoint
    (fixes: no limit on repeated API calls when server rejects requests)
  - Per-request timeout to avoid indefinite blocking
"""

import time
from enum import Enum, auto
from typing import Any, Dict, Optional

import requests

from logger import TradingLogger


class CircuitState(Enum):
    CLOSED = auto()    # Normal operation – requests pass through
    OPEN = auto()      # Failing – requests are blocked immediately
    HALF_OPEN = auto() # Recovery probe – one request allowed through


class APIError(Exception):
    """Raised when an API call ultimately fails after all retries."""


class CircuitOpenError(APIError):
    """Raised when a request is blocked because the circuit is OPEN."""


class APIClient:
    """
    Resilient HTTP client for KIS Open API.

    Circuit-breaker state machine
    ──────────────────────────────
    CLOSED ──(threshold failures)──► OPEN ──(reset_timeout elapsed)──► HALF_OPEN
      ▲                                                                      │
      └──────────────────────(success)──────────────────────────────────────┘
                                 │ failure
                                 ▼
                               OPEN
    """

    def __init__(
        self,
        base_url: str,
        app_key: str,
        app_secret: str,
        token: str,
        logger: TradingLogger,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
        circuit_break_threshold: int = 5,
        circuit_break_reset: int = 3600,
        request_timeout: int = 10,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._app_key = app_key
        self._app_secret = app_secret
        self._token = token
        self._logger = logger

        # Retry settings
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._request_timeout = request_timeout

        # Circuit-breaker state
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._circuit_break_threshold = circuit_break_threshold
        self._circuit_break_reset = circuit_break_reset
        self._circuit_opened_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(
        self,
        endpoint: str,
        params: Dict[str, Any],
        tr_id: str,
    ) -> Dict[str, Any]:
        """Perform a GET request with retry and circuit-breaker logic."""
        return self._request("GET", endpoint, params=params, tr_id=tr_id)

    def post(
        self,
        endpoint: str,
        body: Dict[str, Any],
        tr_id: str,
    ) -> Dict[str, Any]:
        """Perform a POST request with retry and circuit-breaker logic."""
        return self._request("POST", endpoint, body=body, tr_id=tr_id)

    def update_token(self, token: str) -> None:
        """Replace the bearer token (e.g. after re-authentication)."""
        self._token = token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self, tr_id: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
            "authorization": f"Bearer {self._token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        tr_id: str = "",
    ) -> Dict[str, Any]:
        """Core request dispatcher with circuit-breaker and retry logic."""
        self._check_circuit()

        url = f"{self._base_url}{endpoint}"
        headers = self._build_headers(tr_id)
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            self._logger.debug(f"[RETRY] Attempt {attempt}/{self._max_retries} → {method} {endpoint}")
            try:
                if method == "GET":
                    resp = requests.get(
                        url,
                        headers=headers,
                        params=params,
                        timeout=self._request_timeout,
                    )
                else:
                    resp = requests.post(
                        url,
                        headers=headers,
                        json=body,
                        timeout=self._request_timeout,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("rt_cd") == "0":
                        self._on_success()
                        return data
                    # Application-level error (rt_cd != "0")
                    err_msg = data.get("msg1", "Unknown API error")
                    self._logger.warning(
                        f"[API] Application error (rt_cd={data.get('rt_cd')}): {err_msg}"
                    )
                    raise APIError(f"API error rt_cd={data.get('rt_cd')}: {err_msg}")

                # HTTP-level error
                self._logger.error(
                    f"[ERROR] HTTP {resp.status_code} from {endpoint}: {resp.text[:200]}"
                )
                last_exc = APIError(f"HTTP {resp.status_code}")

            except (requests.Timeout, requests.ConnectionError) as exc:
                self._logger.warning(f"[RETRY] Network error on attempt {attempt}: {exc}")
                last_exc = exc
            except APIError:
                # Application-level errors are not retried
                self._on_failure()
                raise

            # Exponential backoff before next attempt (only if more attempts remain)
            if attempt < self._max_retries:
                delay = min(
                    self._retry_base_delay * (2 ** (attempt - 1)),
                    self._retry_max_delay,
                )
                self._logger.info(f"[RETRY] Waiting {delay:.1f}s before attempt {attempt + 1}...")
                time.sleep(delay)

        # All attempts exhausted
        self._on_failure()
        raise APIError(
            f"All {self._max_retries} attempts failed for {method} {endpoint}"
        ) from last_exc

    # ------------------------------------------------------------------
    # Circuit-breaker logic
    # ------------------------------------------------------------------

    def _check_circuit(self) -> None:
        """Raise CircuitOpenError if the circuit is OPEN and the reset timeout
        has not yet elapsed; transition to HALF_OPEN when it has."""
        if self._circuit_state == CircuitState.CLOSED:
            return
        if self._circuit_state == CircuitState.OPEN:
            elapsed = time.time() - (self._circuit_opened_at or 0)
            if elapsed >= self._circuit_break_reset:
                self._logger.info(
                    f"[CIRCUIT] Half-opening after {elapsed:.0f}s – probing API..."
                )
                self._circuit_state = CircuitState.HALF_OPEN
            else:
                wait_remaining = self._circuit_break_reset - elapsed
                self._logger.warning(
                    f"[CIRCUIT] OPEN – blocking request. Resets in {wait_remaining:.0f}s."
                )
                raise CircuitOpenError(
                    f"Circuit is OPEN. Resets in {wait_remaining:.0f}s."
                )
        # HALF_OPEN: allow the request through (outcome handled in _on_success/_on_failure)

    def _on_success(self) -> None:
        """Record a successful call and close the circuit if it was half-open."""
        if self._circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            self._logger.info("[CIRCUIT] Success – closing circuit.")
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._circuit_opened_at = None

    def _on_failure(self) -> None:
        """Record a failed call and open the circuit if the threshold is reached."""
        self._failure_count += 1
        if self._circuit_state == CircuitState.HALF_OPEN:
            # Probe failed – stay OPEN
            self._logger.warning("[CIRCUIT] Probe failed – re-opening circuit.")
            self._circuit_state = CircuitState.OPEN
            self._circuit_opened_at = time.time()
        elif (
            self._circuit_state == CircuitState.CLOSED
            and self._failure_count >= self._circuit_break_threshold
        ):
            self._logger.error(
                f"[CIRCUIT] {self._failure_count} consecutive failures – "
                f"opening circuit for {self._circuit_break_reset}s."
            )
            self._circuit_state = CircuitState.OPEN
            self._circuit_opened_at = time.time()

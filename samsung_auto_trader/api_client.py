# -*- coding: utf-8 -*-
"""
api_client.py
-------------
Low-level HTTP client for Korea Investment Open API.

Responsibilities
----------------
- Build the standard request headers (Authorization, appkey, appsecret,
  tr_id, custtype, Content-Type …).
- Perform GET / POST calls with timeout and simple retry logic.
- Return a normalised :class:`APIResponse` that callers can inspect without
  parsing raw ``requests.Response`` objects.

This module contains no trading logic.  It only knows how to talk HTTP.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

import config
from logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------

@dataclass
class APIResponse:
    """
    Normalised response from a Korea Investment API call.

    Attributes:
        ok:          ``True`` when ``rt_cd == "0"`` and HTTP 200.
        rt_cd:       Return code string from the API body (``"0"`` = success).
        msg_cd:      API message code (e.g. ``"KIOK0000"``).
        msg:         Human-readable message from the API body.
        body:        Full parsed JSON body as a dict.
        http_status: Raw HTTP status code.
        error:       Non-empty string when an error occurred.
    """
    ok: bool = False
    rt_cd: str = ""
    msg_cd: str = ""
    msg: str = ""
    body: dict = field(default_factory=dict)
    http_status: int = 0
    error: str = ""

    # --- Convenience accessors -----------------------------------------------

    def output(self) -> Any:
        """Return the ``output`` field of the body (single record)."""
        return self.body.get("output")

    def output1(self) -> list:
        """Return the ``output1`` list (e.g. holdings rows)."""
        return self.body.get("output1", [])

    def output2(self) -> Any:
        """Return the ``output2`` field (e.g. account summary)."""
        return self.body.get("output2")


# ---------------------------------------------------------------------------
# Header builder
# ---------------------------------------------------------------------------

def _build_headers(
    token: str,
    appkey: str,
    appsecret: str,
    tr_id: str,
    tr_cont: str = "",
) -> dict[str, str]:
    """Build the standard headers required by Korea Investment API."""
    return {
        "Content-Type": "application/json",
        "Accept": "text/plain",
        "charset": "UTF-8",
        "authorization": f"Bearer {token}",
        "appkey": appkey,
        "appsecret": appsecret,
        "tr_id": tr_id,
        "tr_cont": tr_cont,
        "custtype": "P",  # P = 개인
    }


# ---------------------------------------------------------------------------
# Core request helpers
# ---------------------------------------------------------------------------

def _parse_response(resp: requests.Response) -> APIResponse:
    """Parse an HTTP response into an :class:`APIResponse`."""
    ar = APIResponse(http_status=resp.status_code)
    if resp.status_code != 200:
        ar.error = f"HTTP {resp.status_code}: {resp.text}"
        logger.error("[HTTP] %s", ar.error)
        return ar

    try:
        body = resp.json()
    except ValueError:
        ar.error = f"Non-JSON response: {resp.text[:200]}"
        logger.error("[HTTP] %s", ar.error)
        return ar

    ar.body = body
    ar.rt_cd = body.get("rt_cd", "")
    ar.msg_cd = body.get("msg_cd", "")
    ar.msg = body.get("msg1", "")
    ar.ok = ar.rt_cd == "0"

    if not ar.ok:
        ar.error = f"rt_cd={ar.rt_cd} msg_cd={ar.msg_cd} msg={ar.msg}"
        logger.warning("[API] Non-OK response: %s", ar.error)

    return ar


def _retry_call(func, *args, **kwargs) -> APIResponse:
    """
    Call ``func`` up to ``config.MAX_RETRIES`` times with exponential backoff.

    On :class:`requests.RequestException` (network error, timeout …) it waits
    and retries.  On HTTP/API errors it returns immediately – retrying would
    not help and would waste rate-limit budget.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except requests.Timeout as exc:
            last_exc = exc
            wait = config.RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "[HTTP] Timeout on attempt %d/%d – waiting %.1fs …",
                attempt, config.MAX_RETRIES, wait,
            )
            time.sleep(wait)
        except requests.RequestException as exc:
            last_exc = exc
            wait = config.RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "[HTTP] Request error on attempt %d/%d (%s) – waiting %.1fs …",
                attempt, config.MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)

    ar = APIResponse()
    ar.error = f"All {config.MAX_RETRIES} attempts failed: {last_exc}"
    logger.error("[HTTP] %s", ar.error)
    return ar


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get(
    base_url: str,
    path: str,
    token: str,
    appkey: str,
    appsecret: str,
    tr_id: str,
    params: dict,
    tr_cont: str = "",
) -> APIResponse:
    """
    Perform a GET request against the Korea Investment API.

    Args:
        base_url:  e.g. ``config.MOCK_BASE_URL``.
        path:      API path, e.g. ``"/uapi/domestic-stock/v1/quotations/inquire-price"``.
        token:     Bearer access token.
        appkey:    App key from credentials.
        appsecret: App secret from credentials.
        tr_id:     Transaction ID for this API call.
        params:    Query string parameters.
        tr_cont:   Continuation marker for paged responses (``""`` or ``"N"``).

    Returns:
        :class:`APIResponse`
    """
    url = base_url + path
    headers = _build_headers(token, appkey, appsecret, tr_id, tr_cont)
    logger.debug("[GET] %s  tr_id=%s  params=%s", url, tr_id, params)

    def _do_get():
        resp = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        return _parse_response(resp)

    return _retry_call(_do_get)


def post(
    base_url: str,
    path: str,
    token: str,
    appkey: str,
    appsecret: str,
    tr_id: str,
    payload: dict,
) -> APIResponse:
    """
    Perform a POST request against the Korea Investment API.

    Args:
        base_url:  e.g. ``config.MOCK_BASE_URL``.
        path:      API path.
        token:     Bearer access token.
        appkey:    App key.
        appsecret: App secret.
        tr_id:     Transaction ID.
        payload:   JSON body (will be serialised to JSON).

    Returns:
        :class:`APIResponse`
    """
    url = base_url + path
    headers = _build_headers(token, appkey, appsecret, tr_id)
    logger.debug("[POST] %s  tr_id=%s", url, tr_id)

    def _do_post():
        resp = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload),
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        return _parse_response(resp)

    return _retry_call(_do_post)

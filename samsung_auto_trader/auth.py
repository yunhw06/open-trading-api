# -*- coding: utf-8 -*-
"""
auth.py
-------
Authentication module for Korea Investment Open API (mock environment).

Responsibilities
----------------
- Issue a new access token via POST /oauth2/tokenP.
- Cache the token to ``token_cache.json`` so the same token is reused for
  the rest of the calendar day (the API issues the same value within a
  6-hour window anyway, but caching avoids unnecessary calls).
- Load a cached token and validate that it has not expired.
- Return the token string so that ``api_client.py`` can attach it to every
  request header.

No token is ever hard-coded.  Credentials come from ``config.py``.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

import config
from logger import get_logger

logger = get_logger(__name__)

# The cache file sits next to this source file (inside the project folder).
_CACHE_PATH = Path(__file__).parent / config.TOKEN_CACHE_FILE

# Date format used in the API response for token expiry.
_API_EXPIRY_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_cached_token() -> Optional[str]:
    """
    Read the token cache file and return the token string if it is still
    valid for today (calendar-day check).  Returns ``None`` otherwise.
    """
    if not _CACHE_PATH.exists():
        return None

    try:
        with _CACHE_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)

        token: str = data.get("access_token", "")
        expiry_str: str = data.get("expires_at", "")
        issued_date: str = data.get("issued_date", "")

        if not token or not expiry_str or not issued_date:
            return None

        # Only reuse the token if it was issued today (local date).
        today = datetime.now().strftime("%Y-%m-%d")
        if issued_date != today:
            logger.info("[Token] Cached token is from a previous day – will refresh.")
            return None

        # Check the expiry timestamp.
        expiry_dt = datetime.strptime(expiry_str, _API_EXPIRY_FORMAT)
        if datetime.now() >= expiry_dt:
            logger.info("[Token] Cached token has expired – will refresh.")
            return None

        logger.info("[Token] Reusing cached token (expires %s).", expiry_str)
        return token

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("[Token] Could not parse cache file: %s", exc)
        return None


def _save_token(token: str, expiry_str: str) -> None:
    """Persist token and metadata to the cache file."""
    today = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "access_token": token,
        "expires_at": expiry_str,
        "issued_date": today,
    }
    try:
        with _CACHE_PATH.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        logger.debug("[Token] Token cached to '%s'.", _CACHE_PATH)
    except OSError as exc:
        logger.warning("[Token] Could not write cache file: %s", exc)


def _issue_new_token(creds: config.Credentials, base_url: str) -> str:
    """
    Call the token endpoint to obtain a fresh access token.

    Args:
        creds:    Credentials object with appkey / appsecret.
        base_url: API base URL (mock or real).

    Returns:
        The new access token string.

    Raises:
        RuntimeError: If the API call fails or returns a non-200 status.
    """
    url = f"{base_url}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": creds.appkey,
        "appsecret": creds.appsecret,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/plain",
        "charset": "UTF-8",
    }

    logger.info("[Token] Requesting new access token from %s …", url)
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Token request failed: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Token endpoint returned {resp.status_code}: {resp.text}"
        )

    body = resp.json()
    token: str = body.get("access_token", "")
    expiry_str: str = body.get("access_token_token_expired", "")

    if not token:
        raise RuntimeError(f"No access_token in response: {body}")

    logger.info("[Token] New token issued (expires %s).", expiry_str)
    _save_token(token, expiry_str)
    return token


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_access_token(
    creds: config.Credentials,
    base_url: str = config.MOCK_BASE_URL,
    force_refresh: bool = False,
) -> str:
    """
    Return a valid access token, reusing a cached one when possible.

    The token is cached to ``token_cache.json`` in the project folder.
    On the same calendar day, the cached token is returned without any
    network call.  On a new day, or when ``force_refresh=True``, a new
    token is requested from the API.

    Args:
        creds:         Credentials loaded by :func:`config.load_credentials`.
        base_url:      API base URL.  Defaults to the mock trading URL.
        force_refresh: When ``True``, always request a fresh token.

    Returns:
        A valid Bearer token string.

    Raises:
        RuntimeError: If token issuance fails.
    """
    if not force_refresh:
        cached = _load_cached_token()
        if cached:
            return cached

    return _issue_new_token(creds, base_url)

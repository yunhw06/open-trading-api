# -*- coding: utf-8 -*-
"""
account.py
----------
Query account holdings and available cash balance.

Public functions
----------------
- :func:`get_holdings`     – returns a list of stock holdings.
- :func:`get_cash_balance` – returns the available cash (주문가능현금) in KRW.
- :func:`get_account_info` – convenience wrapper that returns both.

API reference
-------------
[국내주식] 주문/계좌 > 주식잔고조회 [v1_국내주식-006]
  GET /uapi/domestic-stock/v1/trading/inquire-balance
  TR_ID (real)  : TTTC8434R
  TR_ID (mock)  : VTTC8434R
"""

from dataclasses import dataclass
from typing import Optional

import api_client
import config
from logger import get_logger

logger = get_logger(__name__)

_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Holding:
    """Represents a single stock position in the account."""
    symbol: str           # 종목코드 (pdno)
    name: str             # 종목명  (prdt_name)
    qty: int              # 보유수량 (hldg_qty)
    avg_price: float      # 매입평균가격 (pchs_avg_pric)
    current_price: int    # 현재가 (prpr)
    profit_loss: float    # 평가손익금액 (evlu_pfls_amt)


@dataclass
class AccountInfo:
    """High-level account snapshot."""
    holdings: list[Holding]
    cash_balance: int     # 주문가능현금 (ord_psbl_cash) – available for ordering
    total_eval: int       # 총평가금액 (tot_evlu_amt)
    total_profit_loss: int  # 총평가손익금액


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_holding(row: dict) -> Optional[Holding]:
    """Convert one row from ``output1`` to a :class:`Holding`.

    Rows with zero quantity are skipped by the caller.
    """
    try:
        return Holding(
            symbol=row.get("pdno", ""),
            name=row.get("prdt_name", ""),
            qty=int(row.get("hldg_qty", "0") or "0"),
            avg_price=float(row.get("pchs_avg_pric", "0") or "0"),
            current_price=int(row.get("prpr", "0") or "0"),
            profit_loss=float(row.get("evlu_pfls_amt", "0") or "0"),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("[Account] Could not parse holding row %s: %s", row, exc)
        return None


def _fetch_balance_page(
    token: str,
    creds: config.Credentials,
    base_url: str,
    tr_id: str,
    fk100: str = "",
    nk100: str = "",
    tr_cont: str = "",
) -> api_client.APIResponse:
    """Perform one GET call to the balance endpoint."""
    params = {
        "CANO": creds.cano,
        "ACNT_PRDT_CD": creds.acnt_prdt_cd,
        "AFHR_FLPR_YN": "N",      # 시간외단일가 여부: N = 기본값
        "OFL_YN": "",
        "INQR_DVSN": "02",        # 02 = 종목별 조회
        "UNPR_DVSN": "01",        # 01 = 기본
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",        # 00 = 전일매매포함
        "CTX_AREA_FK100": fk100,
        "CTX_AREA_NK100": nk100,
    }
    return api_client.get(
        base_url=base_url,
        path=_BALANCE_PATH,
        token=token,
        appkey=creds.appkey,
        appsecret=creds.appsecret,
        tr_id=tr_id,
        params=params,
        tr_cont=tr_cont,
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_account_info(
    token: str,
    creds: config.Credentials,
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> Optional[AccountInfo]:
    """
    Retrieve current holdings and cash balance from the account.

    Handles multi-page responses automatically (up to 10 pages to avoid
    infinite loops in edge cases).

    Args:
        token:    Valid Bearer access token.
        creds:    Credentials object.
        base_url: API base URL.
        is_mock:  ``True`` for mock trading (uses VTTC8434R TR_ID).

    Returns:
        :class:`AccountInfo`, or ``None`` if the API call fails.
    """
    tr_id = config.TR_BALANCE_MOCK if is_mock else config.TR_BALANCE_REAL

    all_holdings: list[Holding] = []
    fk100 = ""
    nk100 = ""
    tr_cont = ""
    cash_balance = 0
    total_eval = 0
    total_profit_loss = 0

    for page in range(10):  # cap at 10 pages
        resp = _fetch_balance_page(
            token, creds, base_url, tr_id, fk100, nk100, tr_cont
        )

        if not resp.ok:
            logger.error("[Account] Balance query failed (page %d): %s", page, resp.error)
            return None

        # --- output1: per-stock holdings ---
        for row in resp.output1():
            holding = _parse_holding(row)
            if holding and holding.qty > 0:
                all_holdings.append(holding)

        # --- output2: account summary (only meaningful on first/last page) ---
        summary = resp.output2()
        if summary:
            # output2 can be a list or a single dict depending on the endpoint version
            if isinstance(summary, list) and summary:
                summary = summary[0]
            if isinstance(summary, dict):
                try:
                    cash_balance = int(summary.get("ord_psbl_cash", "0") or "0")
                    total_eval = int(summary.get("tot_evlu_amt", "0") or "0")
                    total_profit_loss = int(
                        summary.get("evlu_pfls_smtl_amt", "0") or "0"
                    )
                except (ValueError, TypeError) as exc:
                    logger.warning("[Account] Could not parse summary: %s", exc)

        # Check for more pages
        # tr_cont header: "M" or "F" means more data; "D" or "" means done.
        resp_tr_cont = resp.body.get("tr_cont", "")
        if resp_tr_cont not in ("M", "F"):
            break

        fk100 = resp.body.get("ctx_area_fk100", "")
        nk100 = resp.body.get("ctx_area_nk100", "")
        tr_cont = "N"

        logger.debug("[Account] Fetching next page (page %d)…", page + 1)
        import time
        time.sleep(0.5)  # conservative delay between paged requests

    info = AccountInfo(
        holdings=all_holdings,
        cash_balance=cash_balance,
        total_eval=total_eval,
        total_profit_loss=total_profit_loss,
    )

    logger.info(
        "[Account] Holdings: %d position(s), cash available: %d KRW",
        len(info.holdings),
        info.cash_balance,
    )
    for h in info.holdings:
        logger.info(
            "[Account]   %s (%s) qty=%d avg=%.0f current=%d P/L=%.0f",
            h.symbol, h.name, h.qty, h.avg_price, h.current_price, h.profit_loss,
        )

    return info


def get_holdings(
    token: str,
    creds: config.Credentials,
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> Optional[list[Holding]]:
    """
    Return the list of current stock holdings.

    Returns ``None`` if the API call fails.
    """
    info = get_account_info(token, creds, base_url, is_mock)
    return info.holdings if info is not None else None


def get_cash_balance(
    token: str,
    creds: config.Credentials,
    base_url: str = config.MOCK_BASE_URL,
    is_mock: bool = True,
) -> Optional[int]:
    """
    Return the available cash balance (주문가능현금) in KRW.

    Returns ``None`` if the API call fails.
    """
    info = get_account_info(token, creds, base_url, is_mock)
    return info.cash_balance if info is not None else None

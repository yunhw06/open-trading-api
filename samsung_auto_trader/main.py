# -*- coding: utf-8 -*-
"""
main.py
-------
Entry point for samsung_auto_trader.

Run this file to start the automated trading system::

    python main.py              # mock trading (default)
    python main.py --real       # real trading  ⚠  use with caution

The --real flag switches the base URL and TR_IDs to the live production
environment.  Only use it when you have a funded live account and have
thoroughly tested in mock first.

Environment variables required
-------------------------------
    GH_ACCOUNT   : Trading account number (e.g. "1234567801" or "12345678-01")
    GH_APPKEY    : Korea Investment Open API App Key
    GH_APPSECRET : Korea Investment Open API App Secret
"""

import argparse
import sys

import config
from logger import get_logger, setup_logging
from trader import run_trading_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Samsung Electronics (005930) automated trader – Korea Investment Open API"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        default=False,
        help=(
            "Use the REAL trading environment. "
            "⚠  Requires live-trading credentials and a funded account."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import logging
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)

    logger = get_logger(__name__)

    is_mock = not args.real
    base_url = config.REAL_BASE_URL if args.real else config.MOCK_BASE_URL

    env_label = "REAL TRADING ⚠" if args.real else "Mock Trading"
    logger.info("=" * 60)
    logger.info("Samsung Electronics Auto-Trader")
    logger.info("Environment : %s", env_label)
    logger.info("Symbol      : %s", config.SYMBOL)
    logger.info("Buy offset  : -%d KRW", config.BUY_OFFSET)
    logger.info("Sell offset : +%d KRW", config.SELL_OFFSET)
    logger.info("Order qty   : %d share(s)", config.ORDER_QTY)
    logger.info("Poll every  : %d seconds", config.POLL_INTERVAL_SECONDS)
    logger.info("=" * 60)

    run_trading_loop(base_url=base_url, is_mock=is_mock)

    logger.info("Trader exited.")
    sys.exit(0)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - Main entry point.

A simple automated trading system for Samsung Electronics (005930)
using Korea Investment & Securities API in mock trading environment.

Usage:
    python main.py

Environment variables required:
    GH_ACCOUNT    - Korea Investment & Securities account number
    GH_APPKEY     - API app key
    GH_APPSECRET  - API app secret

Example setup:
    export GH_ACCOUNT="12345678-01"
    export GH_APPKEY="your_app_key"
    export GH_APPSECRET="your_app_secret"
    python main.py
"""

import sys

from config import Config
from auth import TokenManager
from logger import TradingLogger
from trader import Trader


def main() -> int:
    """
    Main entry point for Samsung Auto-Trader.

    Returns:
        0 on success, 1 on error
    """
    try:
        # 1. Load configuration from environment variables
        config = Config()
        print(f"✓ Configuration loaded: {config}")

        # 2. Initialize logger
        logger = TradingLogger(
            log_file=config.LOG_FILE,
            log_level=config.LOG_LEVEL,
        )
        print(f"✓ Logger initialized: {config.LOG_FILE}")

        # 3. Authenticate and get/cache token
        logger.info("=== Samsung Auto-Trader Startup ===")
        logger.info("Initializing authentication...")

        token_manager = TokenManager(config, logger)
        token = token_manager.get_token()

        if not token:
            logger.error("Failed to obtain authentication token")
            return 1

        logger.info("✓ Authentication successful")

        # 4. Initialize trading system
        logger.info("Initializing trading system...")
        trader = Trader(config, logger, token)
        logger.info("✓ Trading system initialized")

        # 5. Start trading loop (blocking call)
        logger.info("Starting trading loop...")
        trader.run_trading_loop()

        return 0

    except EnvironmentError as e:
        print(f"❌ Configuration error: {e}", file=sys.stderr)
        print("Please set required environment variables:", file=sys.stderr)
        print("  export GH_ACCOUNT=<account>", file=sys.stderr)
        print("  export GH_APPKEY=<app_key>", file=sys.stderr)
        print("  export GH_APPSECRET=<app_secret>", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n✓ Trading stopped by user.")
        return 0
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

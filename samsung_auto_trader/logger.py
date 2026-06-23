# -*- coding: utf-8 -*-
"""
Samsung Auto-Trader - Logging utilities.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


class TradingLogger:
    """Structured logger for trading system with file and console output."""

    def __init__(
        self,
        log_file: str = "trading.log",
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 3,
    ) -> None:
        level = getattr(logging, log_level.upper(), logging.INFO)
        fmt = "%(asctime)s [%(levelname)s] %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt, datefmt=datefmt)

        self._logger = logging.getLogger("samsung_auto_trader")
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        # Rotating file handler
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        self._logger.addHandler(fh)

    # Convenience proxy methods
    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        self._logger.exception(msg, *args, **kwargs)

# -*- coding: utf-8 -*-
"""
logger.py
---------
Centralised logging configuration for samsung_auto_trader.

All modules import `get_logger(__name__)` rather than configuring
logging themselves so that formatting and handlers are set up once.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = "trader.log") -> None:
    """
    Configure root logger with a console handler and an optional file handler.

    Call this once from ``main.py`` before anything else.
    Subsequent calls are no-ops so that importing multiple modules does not
    reconfigure logging.

    Args:
        level:    Logging level (e.g. ``logging.DEBUG``).
        log_file: Path for the rotating log file.  Pass ``None`` to disable.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # --- File handler (optional) ---
    if log_file:
        log_path = Path(log_file)
        try:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            root.warning("Could not open log file '%s': %s", log_file, exc)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Modules should call::

        from logger import get_logger
        logger = get_logger(__name__)

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(name)

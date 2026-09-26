"""
core/logging_config.py
======================
Configure structured logging for the entire application.
Call `setup_logging()` once at startup (in main.py).
"""

import logging
import sys
from core.config import settings


def setup_logging() -> None:
    """Configure root logger with level and formatter from settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party logs unless debugging
    if not settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("multipart").setLevel(logging.WARNING)

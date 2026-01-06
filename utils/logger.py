# -*- coding: utf-8 -*-
"""
Logging configuration.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# Will be set by setup_logger
_logger: Optional[logging.Logger] = None


def setup_logger() -> logging.Logger:
    """
    Setup application logger with file and console handlers.
    """
    global _logger

    # Import here to avoid circular imports
    from app.config import Config

    # Create logs directory
    Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("trrcms")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        Config.LOG_PATH,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(levelname)-8s | %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a module.
    """
    global _logger

    if _logger is None:
        _logger = setup_logger()

    return _logger.getChild(name)

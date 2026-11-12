# -*- coding: utf-8 -*-
"""
Logging configuration.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# Will be set by setup_logger
_logger: Optional[logging.Logger] = None

# Debug mode (frozen builds only): console stream opened by AllocConsole
_debug_console_stream = None
_frozen_debug_active = False

_DEBUG_SETTING_KEY = "debug_mode"
_FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def is_debug_mode_enabled() -> bool:
    """Debug mode flag, persisted in data/settings.json."""
    try:
        from app.config import load_local_settings
        return bool(load_local_settings().get(_DEBUG_SETTING_KEY, False))
    except Exception:
        return False


def set_debug_mode(enabled: bool) -> None:
    """Persist the debug mode flag and apply it immediately."""
    from app.config import load_local_settings, save_local_settings
    settings = load_local_settings()
    if enabled:
        settings[_DEBUG_SETTING_KEY] = True
    else:
        settings.pop(_DEBUG_SETTING_KEY, None)
    save_local_settings(settings)
    setup_logger()


def get_debug_logs_dir() -> Path:
    """Folder holding debug-mode logs (and crash logs) of the exe."""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "TRRCMS" / "logs"
        return Path(sys.executable).parent / "logs"
    return Path(__file__).parent.parent / "logs"


def _open_debug_console():
    """Attach a console window to the windowed exe; return a UTF-8 stream."""
    global _debug_console_stream
    if _debug_console_stream is not None:
        return _debug_console_stream
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        if not kernel32.AllocConsole():
            return None
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleTitleW("TRRCMS - Debug")
        # Closing a console window kills its process: remove the close button,
        # debug mode is turned off from the app instead.
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            SC_CLOSE = 0xF060
            menu = user32.GetSystemMenu(hwnd, False)
            if menu:
                user32.DeleteMenu(menu, SC_CLOSE, 0)
        _debug_console_stream = open(
            "CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1
        )
        return _debug_console_stream
    except Exception:
        return None


def _close_debug_console():
    global _debug_console_stream
    if _debug_console_stream is None:
        return
    try:
        _debug_console_stream.close()
    except Exception:
        pass
    _debug_console_stream = None
    try:
        import ctypes
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def _setup_frozen_debug(logger: logging.Logger) -> None:
    """Debug mode in the exe: full log file + live console window."""
    logger.setLevel(logging.DEBUG)

    logs_dir = get_debug_logs_dir()
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_handler = RotatingFileHandler(
            logs_dir / f"debug-{timestamp}.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(_FILE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(file_handler)
    except Exception:
        pass

    stream = _open_debug_console()
    if stream is not None:
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
        ))
        logger.addHandler(console_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())


def setup_logger() -> logging.Logger:
    """
    Setup application logger with file and console handlers.

    In frozen (PyInstaller) builds, logging is silent unless debug mode is
    on (data/settings.json "debug_mode"): then a log file is written under
    %APPDATA%\\TRRCMS\\logs and a console window shows the live log.
    Development builds keep the full file + console handler stack.
    Safe to call again to apply a debug mode change.
    """
    global _logger, _frozen_debug_active

    is_frozen = getattr(sys, "frozen", False)

    logger = logging.getLogger("trrcms")
    debug_on = is_frozen and is_debug_mode_enabled()
    if debug_on and _frozen_debug_active and _logger is logger:
        # Already in debug mode (setup_logger runs at import and from main):
        # keep the current log file instead of opening a second one.
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    if is_frozen:
        logger.propagate = False
        _frozen_debug_active = debug_on
        if debug_on:
            _setup_frozen_debug(logger)
            logger.warning(
                f"Debug mode ON | version={_app_version()} | "
                f"logs={get_debug_logs_dir()}"
            )
        else:
            _close_debug_console()
            # Production exe: no file, no console — silent logger.
            logger.setLevel(logging.CRITICAL + 1)
            logger.addHandler(logging.NullHandler())
        _logger = logger
        return logger

    # Development: full logging to file + console
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.DEBUG)

    log_path = logs_dir / "app.log"
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler (WARNING and above — reduces terminal noise)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter(
        "%(levelname)-8s | %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Dedicated import-flow console handler — ALWAYS ON unless explicitly
    # disabled with DEBUG_IMPORT=0. The filter only lets [import-flow] lines
    # through, so this never drowns the console with unrelated INFO. Default-on
    # makes "open the wizard, watch the terminal" work without shell-specific
    # env-var syntax (bash vs PowerShell vs cmd).
    if os.environ.get("DEBUG_IMPORT") != "0":
        flow_console = logging.StreamHandler(sys.stdout)
        flow_console.setLevel(logging.INFO)
        flow_console.addFilter(
            lambda record: "[import-flow]" in record.getMessage()
        )
        flow_console.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(flow_console)

    _logger = logger
    return logger


def _app_version() -> str:
    try:
        from app.config import Config
        return str(Config.VERSION)
    except Exception:
        return "?"


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a module.
    """
    global _logger

    if _logger is None:
        _logger = setup_logger()

    return _logger.getChild(name)

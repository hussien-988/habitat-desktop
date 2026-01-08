# -*- coding: utf-8 -*-
"""
TRRCMS Application Core Module
"""

from .config import Config
from .main_window_v2 import MainWindow  # NEW DESIGN with Navbar
from .styles import get_stylesheet

__all__ = ["Config", "MainWindow", "get_stylesheet"]

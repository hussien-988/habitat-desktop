# -*- coding: utf-8 -*-
"""
Icon Component - مكون الأيقونة القابل لإعادة الاستخدام
Reusable icon component with automatic loading and fallback.
"""

from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
from enum import Enum
import os
import sys
from pathlib import Path
from typing import Optional, List


class IconSize(Enum):
    """Standard icon sizes following design system."""
    SMALL = 16
    MEDIUM = 20
    LARGE = 24
    XLARGE = 32


class Icon(QLabel):
    """Reusable icon component with automatic loading and fallback."""

    @staticmethod
    def _get_search_paths():
        """Get absolute search paths based on project root."""
        # Find project root (where main.py is located)
        import sys
        from pathlib import Path

        if hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle
            base_path = Path(sys._MEIPASS)
        else:
            # Running as script - find project root
            base_path = Path(__file__).parent.parent.parent

        return [
            base_path / "assets" / "images",  # Primary location (exists)
            base_path / "assets" / "icons",
            base_path / "assets" / "icon",
            base_path / "assets",
        ]

    # Keep backward compatibility
    SEARCH_PATHS = []  # Will be populated dynamically

    # Supported file extensions
    EXTENSIONS = [".png", ".svg"]

    def __init__(
        self,
        icon_name: str,
        size: int = IconSize.MEDIUM.value,
        fallback_text: str = "",
        parent=None
    ):
        """Initialize icon component."""
        super().__init__(parent)

        self.icon_name = icon_name
        self.icon_size = size
        self.fallback_text = fallback_text

        self._setup_ui()
        self._load_icon()

    def _setup_ui(self):
        """Setup icon UI properties."""
        self.setFixedSize(self.icon_size, self.icon_size)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)
        self.setStyleSheet("background: transparent; border: none;")

    def _load_icon(self):
        """Load icon from assets folder with automatic fallback."""
        icon_path = self._find_icon_path()

        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # Scale pixmap while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    self.icon_size,
                    self.icon_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.setPixmap(scaled_pixmap)
                return

        # Fallback: use text if icon not found
        if self.fallback_text:
            self.setText(self.fallback_text)
            self.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    font-size: {int(self.icon_size * 0.7)}px;
                }}
            """)
        else:
            pass

    def _find_icon_path(self) -> Optional[str]:
        """Find icon file path from search locations."""
        search_paths = Icon._get_search_paths()

        for search_path in search_paths:
            for extension in self.EXTENSIONS:
                # Try exact name
                icon_path = search_path / f"{self.icon_name}{extension}"
                if icon_path.exists():
                    return str(icon_path)

                # Try capitalized name (case variations)
                icon_path = search_path / f"{self.icon_name.capitalize()}{extension}"
                if icon_path.exists():
                    return str(icon_path)

                # Try uppercase name
                icon_path = search_path / f"{self.icon_name.upper()}{extension}"
                if icon_path.exists():
                    return str(icon_path)

        return None

    @staticmethod
    def load_qicon(icon_name: str, size: int = IconSize.MEDIUM.value) -> Optional[QIcon]:
        """Load QIcon for use in buttons/actions."""
        search_paths = Icon._get_search_paths()

        for search_path in search_paths:
            for extension in Icon.EXTENSIONS:
                icon_path = search_path / f"{icon_name}{extension}"
                if icon_path.exists():
                    return QIcon(str(icon_path))

                # Case variations
                icon_path = search_path / f"{icon_name.capitalize()}{extension}"
                if icon_path.exists():
                    return QIcon(str(icon_path))

                icon_path = search_path / f"{icon_name.upper()}{extension}"
                if icon_path.exists():
                    return QIcon(str(icon_path))

        return None

    @staticmethod
    def load_pixmap(icon_name: str, size: int = IconSize.MEDIUM.value) -> Optional[QPixmap]:
        """Load QPixmap for use in QLabels."""
        search_paths = Icon._get_search_paths()

        for search_path in search_paths:
            for extension in Icon.EXTENSIONS:
                icon_path = search_path / f"{icon_name}{extension}"
                if icon_path.exists():
                    pixmap = QPixmap(str(icon_path))
                    if not pixmap.isNull() and size:
                        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return pixmap

                # Case variations
                icon_path = search_path / f"{icon_name.capitalize()}{extension}"
                if icon_path.exists():
                    pixmap = QPixmap(str(icon_path))
                    if not pixmap.isNull() and size:
                        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return pixmap

                icon_path = search_path / f"{icon_name.upper()}{extension}"
                if icon_path.exists():
                    pixmap = QPixmap(str(icon_path))
                    if not pixmap.isNull() and size:
                        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return pixmap

        return None

    @staticmethod
    def get_all_search_paths(icon_name: str) -> List[str]:
        """Get all possible search paths for an icon (useful for debugging)."""
        paths = []
        search_paths = Icon._get_search_paths()

        for search_path in search_paths:
            for extension in Icon.EXTENSIONS:
                paths.append(str(search_path / f"{icon_name}{extension}"))
                paths.append(str(search_path / f"{icon_name.capitalize()}{extension}"))
                paths.append(str(search_path / f"{icon_name.upper()}{extension}"))
        return paths

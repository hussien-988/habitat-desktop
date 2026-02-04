# -*- coding: utf-8 -*-
"""
Map Constants - ثوابت موحدة لجميع الخرائط في التطبيق

DRY Principle: مصدر واحد للحقيقة (Single Source of Truth)
SOLID Principle: فصل الثوابت عن المنطق

Usage:
    from ui.constants.map_constants import MapConstants
    dialog.setFixedSize(MapConstants.DIALOG_WIDTH, MapConstants.DIALOG_HEIGHT)
"""


class MapConstants:
    """ثوابت موحدة لجميع الخرائط"""

    # ===== Dialog Dimensions (نفس BuildingMapWidget) =====
    DIALOG_WIDTH = 1100  # px
    DIALOG_HEIGHT = 700  # px
    DIALOG_BORDER_RADIUS = 32  # px
    DIALOG_PADDING = 24  # px

    # ===== Map View Dimensions =====
    # Width: 1100 - (24 * 2) = 1052px
    # Height: يختلف حسب المحتوى (title bar, search/instructions, etc.)
    MAP_WIDTH = DIALOG_WIDTH - (DIALOG_PADDING * 2)  # 1052px
    MAP_BORDER_RADIUS = 8  # px

    # ===== Default Map Center (Aleppo, Syria) =====
    DEFAULT_CENTER_LAT = 36.2021  # Latitude
    DEFAULT_CENTER_LON = 37.1343  # Longitude
    DEFAULT_ZOOM = 15  # Zoom level (Professional: Higher zoom = fewer initial buildings = better performance)

    # ===== Coordinate Bounds (Aleppo region) =====
    MIN_LAT = 36.0
    MAX_LAT = 36.5
    MIN_LON = 36.8
    MAX_LON = 37.5

    # ===== Zoom Levels =====
    MIN_ZOOM = 10
    MAX_ZOOM = 18
    MIN_ZOOM_FOR_LOADING = 12  # Professional: Don't load buildings below this zoom (performance)

    # ===== Status Colors (Building Status) =====
    # نفس الألوان المستخدمة في LeafletHTMLGenerator
    STATUS_COLORS = {
        'intact': '#28a745',          # أخضر - سليم
        'standing': '#28a745',        # أخضر - سليم
        'minor_damage': '#ffc107',    # أصفر - ضرر طفيف
        'damaged': '#ffc107',         # أصفر - متضرر
        'partially_damaged': '#fd7e14',  # برتقالي - متضرر جزئياً
        'major_damage': '#fd7e14',    # برتقالي - ضرر كبير
        'severely_damaged': '#dc3545',  # أحمر - متضرر بشدة
        'destroyed': '#dc3545',       # أحمر - مدمر
        'demolished': '#6c757d',      # رمادي - مهدم
        'rubble': '#6c757d',          # رمادي - ركام
        'under_construction': '#17a2b8'  # أزرق فاتح - قيد البناء
    }

    # ===== Status Labels (Arabic) =====
    STATUS_LABELS_AR = {
        'intact': 'سليم',
        'standing': 'سليم',
        'minor_damage': 'ضرر طفيف',
        'damaged': 'متضرر',
        'partially_damaged': 'متضرر جزئياً',
        'major_damage': 'ضرر كبير',
        'severely_damaged': 'متضرر بشدة',
        'destroyed': 'مدمر',
        'demolished': 'مهدم',
        'rubble': 'ركام',
        'under_construction': 'قيد البناء'
    }

    # ===== Polygon Colors =====
    EXISTING_POLYGON_COLOR = '#0072BC'  # أزرق - للمضلعات الموجودة
    EXISTING_POLYGON_OPACITY = 0.3

    DRAWN_POLYGON_COLOR = '#28a745'  # أخضر - للمضلع المرسوم الجديد
    DRAWN_POLYGON_OPACITY = 0.4

    # ===== Performance Limits =====
    MAX_MARKERS_PER_VIEWPORT = 1000  # Professional: Limit markers per viewport for performance

    # ===== Clustering Configuration =====
    CLUSTER_MAX_RADIUS = 80  # Cluster radius in pixels
    DISABLE_CLUSTERING_AT_ZOOM = 17  # Disable clustering at this zoom level

    # ===== Overlay =====
    OVERLAY_COLOR = 'rgba(45, 45, 45, 0.6)'  # رمادي شفاف

    # ===== Title Bar =====
    TITLE_BAR_HEIGHT = 32  # px

    # ===== Search Bar / Instructions =====
    SEARCH_BAR_HEIGHT = 42  # px
    INSTRUCTIONS_HEIGHT = 42  # px

    # ===== Spacing =====
    CONTENT_GAP = 12  # px - Gap between elements in dialog

    @classmethod
    def get_status_color(cls, status: str, default: str = '#6c757d') -> str:
        """
        Get color for building status.

        Args:
            status: Building status code
            default: Default color if status not found

        Returns:
            Hex color code
        """
        return cls.STATUS_COLORS.get(status, default)

    @classmethod
    def get_status_label(cls, status: str, default: str = 'غير محدد') -> str:
        """
        Get Arabic label for building status.

        Args:
            status: Building status code
            default: Default label if status not found

        Returns:
            Arabic status label
        """
        return cls.STATUS_LABELS_AR.get(status, default)

    @classmethod
    def calculate_map_height(cls, has_title_bar: bool = True,
                           has_search_bar: bool = False,
                           has_instructions: bool = False) -> int:
        """
        Calculate map height based on dialog components.

        Args:
            has_title_bar: Whether dialog has title bar
            has_search_bar: Whether dialog has search bar
            has_instructions: Whether dialog has instructions label

        Returns:
            Map height in pixels
        """
        height = cls.DIALOG_HEIGHT - (cls.DIALOG_PADDING * 2)  # 652px

        if has_title_bar:
            height -= cls.TITLE_BAR_HEIGHT
            height -= cls.CONTENT_GAP

        if has_search_bar:
            height -= cls.SEARCH_BAR_HEIGHT
            height -= cls.CONTENT_GAP

        if has_instructions:
            height -= cls.INSTRUCTIONS_HEIGHT
            height -= cls.CONTENT_GAP

        return height

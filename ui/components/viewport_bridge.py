# -*- coding: utf-8 -*-
"""
Viewport Bridge - للتواصل بين JavaScript و Python
====================================================

يتيح للخريطة إرسال معلومات الـ viewport إلى Python عند:
- Pan (تحريك الخريطة)
- Zoom (تكبير/تصغير)
- Initial load (التحميل الأولي)

Professional Best Practice:
- QWebChannel for JavaScript ↔ Python communication
- Debounced events to prevent excessive API calls
- Thread-safe signal/slot mechanism
"""

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
from typing import Dict, Optional, Callable
from utils.logger import get_logger

logger = get_logger(__name__)


class ViewportBridge(QObject):
    """
    جسر التواصل بين Leaflet.js (JavaScript) و PyQt5 (Python).

    الوظائف:
    - استقبال viewport changes من JavaScript
    - Debouncing للحد من الطلبات المتكررة
    - إشارات PyQt لتحديث البيانات

    Signals:
        viewportChanged: يُطلق عند تغيير viewport
            Parameters: dict with keys:
                - ne_lat, ne_lng: North-East corner
                - sw_lat, sw_lng: South-West corner
                - zoom: Current zoom level
                - center_lat, center_lng: Map center

    Usage:
        bridge = ViewportBridge(debounce_ms=300)
        bridge.viewportChanged.connect(on_viewport_changed)

        # في QWebEngineView:
        channel = QWebChannel()
        channel.registerObject('viewportBridge', bridge)
        web_view.page().setWebChannel(channel)
    """

    # Signal يُطلق عند تغيير viewport (بعد debouncing)
    viewportChanged = pyqtSignal(dict)

    def __init__(self, debounce_ms: int = 300, parent: Optional[QObject] = None):
        """
        Initialize viewport bridge.

        Args:
            debounce_ms: Debounce delay in milliseconds (default: 300ms)
            parent: Parent QObject
        """
        super().__init__(parent)

        self.debounce_ms = debounce_ms
        self._debounce_timer: Optional[QTimer] = None
        self._pending_viewport: Optional[Dict] = None
        self._last_viewport: Optional[Dict] = None

        # إحصائيات للتتبع
        self._stats = {
            'total_events': 0,      # إجمالي الأحداث المستقبلة
            'debounced_events': 0,  # الأحداث المُرسلة بعد debouncing
            'ignored_events': 0     # الأحداث المتجاهلة (نفس الـ viewport)
        }

        logger.info(f"✅ ViewportBridge initialized (debounce={debounce_ms}ms)")

    @pyqtSlot(float, float, float, float, int, float, float)
    def onViewportChanged(
        self,
        ne_lat: float,
        ne_lng: float,
        sw_lat: float,
        sw_lng: float,
        zoom: int,
        center_lat: float,
        center_lng: float
    ):
        """
        يُستدعى من JavaScript عند تغيير viewport.

        Professional Best Practice: Debouncing
        - لا نُرسل البيانات فوراً
        - ننتظر {debounce_ms}ms قبل الإرسال
        - إذا حدث تغيير آخر قبل انتهاء المؤقت، نُلغي المؤقت القديم
        - النتيجة: إرسال واحد فقط بعد توقف المستخدم عن التحريك

        Args:
            ne_lat: North-East latitude
            ne_lng: North-East longitude
            sw_lat: South-West latitude
            sw_lng: South-West longitude
            zoom: Current zoom level
            center_lat: Map center latitude
            center_lng: Map center longitude
        """
        self._stats['total_events'] += 1

        viewport_data = {
            'ne_lat': ne_lat,
            'ne_lng': ne_lng,
            'sw_lat': sw_lat,
            'sw_lng': sw_lng,
            'zoom': zoom,
            'center_lat': center_lat,
            'center_lng': center_lng
        }

        # تحقق: هل تغير الـ viewport فعلاً؟
        if self._is_same_viewport(viewport_data, self._last_viewport):
            self._stats['ignored_events'] += 1
            logger.debug(f"⏭️ Viewport unchanged, ignoring (event #{self._stats['total_events']})")
            return

        # حفظ البيانات المعلقة
        self._pending_viewport = viewport_data

        # إلغاء المؤقت القديم (إن وُجد)
        if self._debounce_timer and self._debounce_timer.isActive():
            self._debounce_timer.stop()

        # إنشاء مؤقت جديد
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_viewport_changed)
        self._debounce_timer.start(self.debounce_ms)

        logger.debug(
            f"⏱️ Viewport change pending (zoom={zoom}, "
            f"bbox=[{sw_lat:.3f},{sw_lng:.3f} - {ne_lat:.3f},{ne_lng:.3f}])"
        )

    def _emit_viewport_changed(self):
        """إرسال الـ signal بعد انتهاء debouncing."""
        if self._pending_viewport:
            self._stats['debounced_events'] += 1
            self._last_viewport = self._pending_viewport.copy()

            logger.info(
                f"🗺️ Viewport changed (#{self._stats['debounced_events']}): "
                f"zoom={self._pending_viewport['zoom']}, "
                f"bbox=[{self._pending_viewport['sw_lat']:.4f},{self._pending_viewport['sw_lng']:.4f} - "
                f"{self._pending_viewport['ne_lat']:.4f},{self._pending_viewport['ne_lng']:.4f}]"
            )

            # إطلاق الإشارة
            self.viewportChanged.emit(self._pending_viewport)
            self._pending_viewport = None

    def _is_same_viewport(self, viewport1: Optional[Dict], viewport2: Optional[Dict]) -> bool:
        """
        تحقق: هل viewport1 و viewport2 متطابقان؟

        Professional Best Practice: Avoid unnecessary updates
        - نقارن بدقة 4 أرقام عشرية (~11 متر)
        - zoom يجب أن يكون متطابقاً تماماً

        Args:
            viewport1: First viewport dict
            viewport2: Second viewport dict

        Returns:
            True إذا كانا متطابقين
        """
        if viewport1 is None or viewport2 is None:
            return False

        # مقارنة zoom (يجب أن يكون متطابقاً تماماً)
        if viewport1['zoom'] != viewport2['zoom']:
            return False

        # مقارنة bbox بدقة 4 أرقام (~11m accuracy)
        threshold = 0.0001
        for key in ['ne_lat', 'ne_lng', 'sw_lat', 'sw_lng']:
            if abs(viewport1[key] - viewport2[key]) > threshold:
                return False

        return True

    def get_stats(self) -> Dict[str, int]:
        """
        الحصول على إحصائيات الأداء.

        Returns:
            Dict with keys:
                - total_events: إجمالي الأحداث
                - debounced_events: الأحداث المُرسلة
                - ignored_events: الأحداث المتجاهلة
                - reduction: نسبة التخفيض (%)
        """
        total = self._stats['total_events']
        debounced = self._stats['debounced_events']
        reduction = ((total - debounced) / total * 100) if total > 0 else 0

        return {
            **self._stats,
            'reduction': round(reduction, 1)
        }

    def reset_stats(self):
        """إعادة تعيين الإحصائيات."""
        self._stats = {
            'total_events': 0,
            'debounced_events': 0,
            'ignored_events': 0
        }
        logger.debug("📊 ViewportBridge stats reset")

    @pyqtSlot()
    def requestInitialLoad(self):
        """
        طلب تحميل أولي للبيانات.

        يُستدعى من JavaScript عند تحميل الخريطة لأول مرة.
        """
        logger.info("🔄 Initial viewport load requested")
        # يمكن معالجة هذا بشكل خاص (مثل تحميل أكبر في البداية)
        # حالياً: ننتظر أول viewport change event

    def __del__(self):
        """Cleanup عند حذف الـ bridge."""
        if self._debounce_timer:
            self._debounce_timer.stop()

        stats = self.get_stats()
        logger.info(
            f"🏁 ViewportBridge destroyed - Stats: "
            f"{stats['debounced_events']}/{stats['total_events']} events "
            f"({stats['reduction']}% reduction)"
        )

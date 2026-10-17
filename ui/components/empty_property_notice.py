# -*- coding: utf-8 -*-
"""Read-only notice for a household unit found empty during a field survey."""

from PyQt5.QtWidgets import QLabel

from services.translation_manager import tr
from ui.font_utils import FontManager, create_font


def empty_property_text(household: dict) -> str:
    """'عقار فارغ — {justification}' for an empty-property household, else ''."""
    if not household or not household.get("is_empty_property"):
        return ""
    justification = (household.get("empty_property_justification") or "").strip()
    label = tr("wizard.household.empty_property")
    return f"{label} — {justification}" if justification else label


class EmptyPropertyNotice(QLabel):
    """Amber notice label; empty properties are set from the tablet only."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self.setStyleSheet(
            "QLabel { background-color: #FFFBEB; color: #B45309; "
            "border: 1px solid #FCD34D; border-radius: 8px; padding: 8px 10px; }"
        )

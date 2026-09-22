# -*- coding: utf-8 -*-
"""RTL-aware QComboBox for Arabic right-to-left support.

Uses editable + read-only lineEdit to control text alignment,
which is the recommended workaround for Qt's lack of QSS text-align
support on QComboBox (QTBUG-46245).
"""

from PyQt5.QtWidgets import QComboBox, QCompleter
from PyQt5.QtCore import Qt, QTimer


def _resize_popup_to_items(combo: QComboBox):
    """Force popup view height to match the actual item count.

    Inside frameless+translucent dialogs, the popup container can grow
    while the inner QListView keeps a tiny viewport, leaving empty space
    above and below the items. Setting an explicit fixed height on the
    view fixes this.

    Must be deferred via QTimer to avoid the resize event closing the
    popup immediately after it opens.
    """
    view = combo.view()
    if not view.isVisible():
        return
    count = combo.count()
    if count <= 0:
        return
    row_h = view.sizeHintForRow(0)
    if row_h <= 0:
        return
    visible = min(count, combo.maxVisibleItems())
    target_h = row_h * visible + 8
    if view.height() != target_h:
        view.setFixedHeight(target_h)


class RtlCombo(QComboBox):
    """QComboBox with centered text and full-field click support.
    Uses editable + read-only lineEdit to control text alignment.
    changeEvent ensures alignment survives stylesheet changes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setAlignment(Qt.AlignCenter)
        self.lineEdit().installEventFilter(self)

    def showPopup(self):
        super().showPopup()
        QTimer.singleShot(0, lambda: _resize_popup_to_items(self))

    def eventFilter(self, obj, event):
        if obj == self.lineEdit() and event.type() == event.MouseButtonPress:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.StyleChange and self.lineEdit():
            self.lineEdit().setAlignment(Qt.AlignCenter)
def enable_searchable_combo(combo: QComboBox) -> QComboBox:
    """Allow typing to search existing combo-box items only."""
    if getattr(combo, "_searchable_combo_enabled", False):
        return combo

    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.setFocusPolicy(Qt.StrongFocus)

    line_edit = combo.lineEdit()
    if line_edit is None:
        return combo

    line_edit.setReadOnly(False)

    state = {
        "data": None,
        "text": "",
        "has_selection": False,
    }

    def remember_selection(index):
        if index < 0:
            if not line_edit.hasFocus():
                state["data"] = None
                state["text"] = ""
                state["has_selection"] = False
            return

        state["data"] = combo.itemData(index)
        state["text"] = combo.itemText(index)
        state["has_selection"] = True

    def find_exact_text(text):
        wanted = str(text or "").strip().casefold()

        if not wanted:
            return -1

        for index in range(combo.count()):
            if combo.itemText(index).strip().casefold() == wanted:
                return index

        return -1

    def restore_last_selection():
        if state["has_selection"]:
            for index in range(combo.count()):
                if (
                    combo.itemData(index) == state["data"]
                    and combo.itemText(index) == state["text"]
                ):
                    combo.setCurrentIndex(index)
                    line_edit.setText(combo.itemText(index))
                    return

        combo.setCurrentIndex(-1)
        combo.clearEditText()

    def commit_text(text):
        index = find_exact_text(text)

        if index >= 0:
            combo.setCurrentIndex(index)
            line_edit.setText(combo.itemText(index))
            remember_selection(index)
            return

        restore_last_selection()

    remember_selection(combo.currentIndex())
    combo.currentIndexChanged.connect(remember_selection)

    completer = QCompleter(combo.model(), combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)

    combo.setCompleter(completer)

    completer.activated[str].connect(commit_text)
    line_edit.editingFinished.connect(
        lambda: commit_text(line_edit.text())
    )

    combo._searchable_combo_enabled = True
    combo._searchable_combo_completer = completer
    combo._searchable_combo_state = state

    return combo

class FixedPopupCombo(QComboBox):
    """QComboBox that resizes its popup view to fit items exactly.

    Use inside frameless+translucent dialogs to avoid empty space
    above/below the items in the dropdown.
    """

    def showPopup(self):
        super().showPopup()
        QTimer.singleShot(0, lambda: _resize_popup_to_items(self))

# -*- coding: utf-8 -*-
"""Central mapping of backend import package status codes to UI decisions.

Single source of truth — replaces inline dicts previously scattered across
import_packages_page.py and import_wizard_page.py.
"""

from typing import Dict


class PkgStatus:
    """Backend package status codes (integers 1..12)."""
    PENDING = 1
    VALIDATING = 2
    STAGING = 3
    VALIDATION_FAILED = 4
    QUARANTINED = 5
    REVIEWING_CONFLICTS = 6
    READY_TO_COMMIT = 7
    COMMITTING = 8
    COMPLETED = 9
    FAILED = 10
    PARTIALLY_COMPLETED = 11
    CANCELLED = 12


# Status groups
TRANSIENT = {PkgStatus.VALIDATING, PkgStatus.STAGING, PkgStatus.COMMITTING}
HISTORY = {PkgStatus.COMPLETED, PkgStatus.PARTIALLY_COMPLETED, PkgStatus.CANCELLED}
ACTIVE_QUEUE = {
    PkgStatus.PENDING,
    PkgStatus.VALIDATING,
    PkgStatus.STAGING,
    PkgStatus.VALIDATION_FAILED,
    PkgStatus.QUARANTINED,
    PkgStatus.REVIEWING_CONFLICTS,
    PkgStatus.READY_TO_COMMIT,
    PkgStatus.COMMITTING,
    PkgStatus.FAILED,
}

# Statuses where the user can take a productive action by opening the wizard:
# advance the package, resolve conflicts, or view the final success report.
# Everything else (Quarantined, Cancelled, Failed, ValidationFailed,
# PartiallyCompleted) is read-only history — the action button is disabled
# and clicking the row only selects, never opens the wizard.
ACTIONABLE = {
    PkgStatus.PENDING,
    PkgStatus.VALIDATING,
    PkgStatus.STAGING,
    PkgStatus.REVIEWING_CONFLICTS,
    PkgStatus.READY_TO_COMMIT,
    PkgStatus.COMMITTING,
    PkgStatus.COMPLETED,
}


# Visible wizard step: 0=Package Processing, 1=Review & Approve, 2=Final Report
_STATUS_STEP: Dict[int, int] = {
    PkgStatus.PENDING: 0,
    PkgStatus.VALIDATING: 0,
    PkgStatus.STAGING: 0,
    PkgStatus.VALIDATION_FAILED: 0,
    PkgStatus.QUARANTINED: 0,
    PkgStatus.REVIEWING_CONFLICTS: 1,
    PkgStatus.READY_TO_COMMIT: 1,
    PkgStatus.COMMITTING: 1,
    PkgStatus.COMPLETED: 2,
    PkgStatus.FAILED: 2,
    PkgStatus.PARTIALLY_COMPLETED: 2,
    PkgStatus.CANCELLED: 2,
}


_STATUS_ACTION_KEY: Dict[int, str] = {
    PkgStatus.PENDING: "page.import_packages.action.process",
    PkgStatus.VALIDATING: "page.import_packages.action.follow_validating",
    PkgStatus.STAGING: "page.import_packages.action.follow_staging",
    PkgStatus.VALIDATION_FAILED: "page.import_packages.action.view_validation_errors",
    PkgStatus.QUARANTINED: "page.import_packages.action.view_quarantine",
    PkgStatus.REVIEWING_CONFLICTS: "page.import_packages.action.resolve_conflicts",
    PkgStatus.READY_TO_COMMIT: "page.import_packages.action.review_and_import",
    PkgStatus.COMMITTING: "page.import_packages.action.follow_import",
    # Only COMPLETED is allowed to use the "view final report" label —
    # other statuses get their own status-specific labels.
    PkgStatus.COMPLETED: "page.import_packages.action.view_report",
    PkgStatus.FAILED: "page.import_packages.action.view_failure",
    PkgStatus.PARTIALLY_COMPLETED: "page.import_packages.action.view_partial",
    PkgStatus.CANCELLED: "page.import_packages.action.view_cancellation",
}


_STATUS_LABEL_KEY: Dict[int, str] = {
    PkgStatus.PENDING: "import_status.pending",
    PkgStatus.VALIDATING: "import_status.validating",
    PkgStatus.STAGING: "import_status.staging",
    PkgStatus.VALIDATION_FAILED: "import_status.validation_failed",
    PkgStatus.QUARANTINED: "import_status.quarantined",
    PkgStatus.REVIEWING_CONFLICTS: "import_status.reviewing_conflicts",
    PkgStatus.READY_TO_COMMIT: "import_status.ready_to_commit",
    PkgStatus.COMMITTING: "import_status.committing",
    PkgStatus.COMPLETED: "import_status.completed",
    PkgStatus.FAILED: "import_status.failed",
    PkgStatus.PARTIALLY_COMPLETED: "import_status.partially_completed",
    PkgStatus.CANCELLED: "import_status.cancelled",
}


_STATUS_COLOR: Dict[int, str] = {
    PkgStatus.PENDING: "#6B7280",
    PkgStatus.VALIDATING: "#3890DF",
    PkgStatus.STAGING: "#F59E0B",
    PkgStatus.VALIDATION_FAILED: "#EF4444",
    PkgStatus.QUARANTINED: "#DC2626",
    PkgStatus.REVIEWING_CONFLICTS: "#8B5CF6",
    PkgStatus.READY_TO_COMMIT: "#059669",
    PkgStatus.COMMITTING: "#3890DF",
    PkgStatus.COMPLETED: "#10B981",
    PkgStatus.FAILED: "#EF4444",
    PkgStatus.PARTIALLY_COMPLETED: "#F59E0B",
    PkgStatus.CANCELLED: "#9CA3AF",
}


_STATUS_BG_RGBA: Dict[int, str] = {
    PkgStatus.PENDING: "rgba(107,114,128,0.12)",
    PkgStatus.VALIDATING: "rgba(56,144,223,0.12)",
    PkgStatus.STAGING: "rgba(245,158,11,0.12)",
    PkgStatus.VALIDATION_FAILED: "rgba(239,68,68,0.12)",
    PkgStatus.QUARANTINED: "rgba(220,38,38,0.12)",
    PkgStatus.REVIEWING_CONFLICTS: "rgba(139,92,246,0.12)",
    PkgStatus.READY_TO_COMMIT: "rgba(5,150,105,0.12)",
    PkgStatus.COMMITTING: "rgba(56,144,223,0.12)",
    PkgStatus.COMPLETED: "rgba(16,185,129,0.12)",
    PkgStatus.FAILED: "rgba(239,68,68,0.12)",
    PkgStatus.PARTIALLY_COMPLETED: "rgba(245,158,11,0.12)",
    PkgStatus.CANCELLED: "rgba(156,163,175,0.12)",
}


_STATUS_BORDER: Dict[int, str] = {
    PkgStatus.PENDING: "#D1D5DB",
    PkgStatus.VALIDATING: "#93C5FD",
    PkgStatus.STAGING: "#FCD34D",
    PkgStatus.VALIDATION_FAILED: "#FCA5A5",
    PkgStatus.QUARANTINED: "#FCA5A5",
    PkgStatus.REVIEWING_CONFLICTS: "#C4B5FD",
    PkgStatus.READY_TO_COMMIT: "#6EE7B7",
    PkgStatus.COMMITTING: "#93C5FD",
    PkgStatus.COMPLETED: "#6EE7B7",
    PkgStatus.FAILED: "#FCA5A5",
    PkgStatus.PARTIALLY_COMPLETED: "#FCD34D",
    PkgStatus.CANCELLED: "#D1D5DB",
}


def status_meta(code: int) -> Dict:
    """Return UI metadata for a status code."""
    if code not in _STATUS_STEP:
        return {
            "label_key": "import_status.unknown",
            "action_key": "page.import_packages.action.view_report",
            "target_step": 0,
            "color_hex": "#6B7280",
            "bg_rgba": "rgba(107,114,128,0.12)",
            "border_hex": "#D1D5DB",
            "is_transient": False,
            "is_history": False,
        }
    return {
        "label_key": _STATUS_LABEL_KEY[code],
        "action_key": _STATUS_ACTION_KEY[code],
        "target_step": _STATUS_STEP[code],
        "color_hex": _STATUS_COLOR[code],
        "bg_rgba": _STATUS_BG_RGBA[code],
        "border_hex": _STATUS_BORDER[code],
        "is_transient": code in TRANSIENT,
        "is_history": code in HISTORY,
    }


def target_wizard_step(code: int) -> int:
    """Return visible wizard step (0, 1, or 2) for a status code."""
    return _STATUS_STEP.get(code, 0)


def action_label_key(code: int) -> str:
    """Return translation key for the primary card action button."""
    return _STATUS_ACTION_KEY.get(code, "page.import_packages.action.view_report")


def status_label_key(code: int) -> str:
    """Return translation key for a status label."""
    return _STATUS_LABEL_KEY.get(code, "import_status.unknown")


def is_history_status(code: int) -> bool:
    """True if status belongs to the history group (Completed/Partial/Cancelled)."""
    return code in HISTORY


def is_transient_status(code: int) -> bool:
    """True if status is actively being processed (polling required)."""
    return code in TRANSIENT


def is_actionable_status(code: int) -> bool:
    """True if the user can productively open the wizard for this status.

    Actionable: Pending, Validating, Staging, ReviewingConflicts,
    ReadyToCommit, Committing, Completed.
    Non-actionable (read-only history / dead-end): Quarantined, Cancelled,
    Failed, ValidationFailed, PartiallyCompleted.
    """
    return code in ACTIONABLE


def needs_stage_and_detect(code: int) -> bool:
    """True only for PENDING — the only state where stage+detect-duplicates should run."""
    return code == PkgStatus.PENDING


# Active-queue display priority. Lower number = shown higher in the list.
# Order: in-progress first, then needs-user, then blocked/terminal. Failed
# sits at the bottom so Validating always appears above it.
_QUEUE_SORT_PRIORITY: Dict[int, int] = {
    PkgStatus.COMMITTING: 1,
    PkgStatus.VALIDATING: 2,
    PkgStatus.STAGING: 3,
    PkgStatus.READY_TO_COMMIT: 4,
    PkgStatus.REVIEWING_CONFLICTS: 5,
    PkgStatus.PENDING: 6,
    PkgStatus.VALIDATION_FAILED: 7,
    PkgStatus.QUARANTINED: 8,
    PkgStatus.FAILED: 9,
}


def queue_sort_priority(code: int) -> int:
    """Return the display-rank of a status in the active queue.

    Lower number = shown first. Unknown/history codes fall to the end.
    """
    return _QUEUE_SORT_PRIORITY.get(code, 999)

# -*- coding: utf-8 -*-
"""
Dialogs for Office Survey Wizard.

This package contains reusable dialog windows for:
- Person registration
- Evidence/document attachment
- Unit creation
"""

from .unit_dialog import UnitDialog
from .person_dialog import PersonDialog
from .evidence_dialog import EvidenceDialog

__all__ = [
    'UnitDialog',
    'PersonDialog',
    'EvidenceDialog'
]

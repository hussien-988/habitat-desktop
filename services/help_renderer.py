# -*- coding: utf-8 -*-
"""Help text renderer for dynamic vocabulary placeholders.

Supported tokens:
    {vocab:<Name>:<code>}   -> single label
    {vocab_list:<Name>}     -> separator-joined labels
"""

import re

from services.vocab_service import get_label, get_options


_PATTERN = re.compile(r"\{(vocab|vocab_list):([^:}]+)(?::([^}]+))?\}")

_AR_SEPARATOR = "\u060c "
_EN_SEPARATOR = ", "


def render(text: str) -> str:
    if not text or "{" not in text:
        return text

    def _replace(m):
        kind = m.group(1)
        name = m.group(2)
        code = m.group(3)
        if kind == "vocab" and code is not None:
            return get_label(name, code)
        if kind == "vocab_list":
            opts = get_options(name)
            if not opts:
                return m.group(0)
            sep = _AR_SEPARATOR if _is_arabic() else _EN_SEPARATOR
            return sep.join(label for _, label in opts)
        return m.group(0)

    return _PATTERN.sub(_replace, text)


def _is_arabic() -> bool:
    try:
        from services.translation_manager import is_rtl
        return is_rtl()
    except Exception:
        return False

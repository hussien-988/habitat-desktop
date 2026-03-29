# -*- coding: utf-8 -*-
"""
Internationalization (i18n) - thin bridge to TranslationManager.
Kept for backward compatibility with pages that use self.i18n.t(key).
"""


class I18n:
    """Bridge to TranslationManager for backward compatibility."""

    def __init__(self, default_language: str = "ar"):
        self._language = default_language

    def set_language(self, language: str):
        if language in ("en", "ar"):
            self._language = language

    def get_language(self) -> str:
        return self._language

    def is_arabic(self) -> bool:
        return self._language == "ar"

    def t(self, key: str, **kwargs) -> str:
        from services.translation_manager import tr
        return tr(key, **kwargs)

# -*- coding: utf-8 -*-
"""Centralized Translation Manager for i18n support."""

from typing import Callable, List
from PyQt5.QtCore import Qt
from utils.logger import get_logger

logger = get_logger(__name__)


class TranslationManager:
    """Singleton Translation Manager with RTL/LTR support."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_language = "ar"
            cls._instance._translations = {}
            cls._instance._listeners: List[Callable] = []
            cls._instance._load_translations()
        return cls._instance

    def _load_translations(self):
        try:
            from services.translations.ar import AR_TRANSLATIONS
            from services.translations.en import EN_TRANSLATIONS
            self._translations = {
                "ar": AR_TRANSLATIONS,
                "en": EN_TRANSLATIONS,
            }
        except ImportError as e:
            logger.error(f"Failed to load translations: {e}")
            self._translations = {"ar": {}, "en": {}}

    def on_language_changed(self, callback: Callable):
        self._listeners.append(callback)

    def set_language(self, lang_code: str):
        if lang_code not in self._translations:
            lang_code = "ar"
        if self._current_language != lang_code:
            self._current_language = lang_code
            logger.info(f"Language changed to: {lang_code}")
            for callback in self._listeners:
                try:
                    callback(lang_code)
                except Exception as e:
                    logger.error(f"Language change callback error: {e}")

    def get_language(self) -> str:
        return self._current_language

    def tr(self, key: str, **kwargs) -> str:
        translation = self._translations.get(
            self._current_language, {}
        ).get(key)
        if translation is None:
            return key
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return translation

    def is_rtl(self) -> bool:
        return self._current_language in ("ar", "he", "fa")

    def get_layout_direction(self):
        return Qt.RightToLeft if self.is_rtl() else Qt.LeftToRight

    def get_text_alignment(self):
        return Qt.AlignRight if self.is_rtl() else Qt.AlignLeft


_translator = TranslationManager()


def tr(key: str, **kwargs) -> str:
    return _translator.tr(key, **kwargs)


def set_language(lang_code: str):
    _translator.set_language(lang_code)


def get_language() -> str:
    return _translator.get_language()


def is_rtl() -> bool:
    return _translator.is_rtl()


def get_layout_direction():
    return _translator.get_layout_direction()


def get_text_alignment():
    return _translator.get_text_alignment()

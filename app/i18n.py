# app/i18n.py
# Internationalization (i18n) framework

import json
import locale
import os
import sys
from typing import Dict, Any
from app.logger import get_logger
from app.path_helper import get_i18n_path

DEFAULT_LOCALE = "en"
_current_locale = None
_translations = {}
_WINDOWS_LOCALE_NAME_MAP = {
    "english": "en",
    "korean": "ko",
}


def _detect_windows_locale() -> str | None:
    """Return the Windows UI locale in ``ll_CC`` form when available."""
    if sys.platform != "win32":
        return None

    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(lang_id)
    except OSError:
        return None


def _normalize_locale_code(candidate: str) -> str | None:
    """Normalize a locale string to a short language code."""
    if not candidate:
        return None

    normalized = candidate.split(".")[0].replace("-", "_").strip()
    if not normalized:
        return None

    if "_" in normalized:
        language = normalized.split("_")[0].lower()
        return _WINDOWS_LOCALE_NAME_MAP.get(language, language)

    lowered = normalized.lower()
    if len(lowered) in (2, 3) and lowered.isalpha():
        return lowered

    return _WINDOWS_LOCALE_NAME_MAP.get(lowered, lowered)


def get_system_locale() -> str:
    """
    Detect system locale.

    Returns:
        Locale code (e.g., "en", "ko")
    """
    candidates = []

    windows_locale = _detect_windows_locale()
    if windows_locale:
        candidates.append(windows_locale)

    try:
        current_locale = locale.getlocale()[0]
        if current_locale:
            candidates.append(current_locale)
    except (TypeError, ValueError):
        pass

    for env_key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        env_value = os.environ.get(env_key)
        if env_value:
            candidates.append(env_value)

    for candidate in candidates:
        normalized = _normalize_locale_code(candidate)
        if normalized:
            return normalized

    return DEFAULT_LOCALE


def load_translations(locale_code: str = None) -> Dict[str, Any]:
    """
    Load translations from JSON file.

    Args:
        locale_code: Locale to load (e.g., "en", "ko"). If None, auto-detect.

    Returns:
        Translation dictionary
    """
    global _current_locale, _translations
    logger = get_logger()

    if locale_code is None:
        locale_code = get_system_locale()

    locale_file = get_i18n_path(f"{locale_code}.json")

    # Fallback to default if locale file not found
    if not locale_file.exists():
        logger.warning(f"Locale file not found: {locale_file}, falling back to {DEFAULT_LOCALE}")
        locale_code = DEFAULT_LOCALE
        locale_file = get_i18n_path(f"{locale_code}.json")

    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            _translations = json.load(f)
        _current_locale = locale_code
        logger.info(f"Loaded translations for locale: {locale_code}")
        return _translations
    except (OSError, IOError) as e:
        logger.error(f"Failed to load translations: {e}")
        _translations = {}
        _current_locale = DEFAULT_LOCALE
        return {}


def get_current_locale() -> str:
    """Get the currently loaded locale code."""
    return _current_locale if _current_locale else DEFAULT_LOCALE


def tr(key: str, *args) -> str:
    """
    Translate a key to localized string.

    Args:
        key: Translation key (e.g., "menu.file.open")
        *args: Placeholder values for {0}, {1}, etc.

    Returns:
        Translated string with placeholders replaced

    Example:
        >>> tr("error.cannot_open", "file.pdf")
        "Cannot open file: file.pdf"
    """
    global _translations

    # Load translations if not already loaded
    if not _translations:
        load_translations()

    # Get translation or fall back to key
    translated = _translations.get(key, key)

    # Replace placeholders
    for i, arg in enumerate(args):
        translated = translated.replace(f"{{{i}}}", str(arg))

    return translated


def set_locale(locale_code: str) -> bool:
    """
    Manually set the locale.

    Args:
        locale_code: Locale to set (e.g., "en", "ko")

    Returns:
        True if successful, False otherwise
    """
    logger = get_logger()
    try:
        load_translations(locale_code)
        logger.info(f"Locale manually set to: {locale_code}")
        return True
    except (OSError, ValueError) as e:
        logger.error(f"Failed to set locale: {e}")
        return False

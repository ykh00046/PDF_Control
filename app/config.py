# app/config.py
# Configuration management for persistent settings

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict

from app.logger import get_logger
from app.path_helper import get_config_path, get_resource_path

PDF_POINTS_PER_INCH = 72
BYTES_PER_MIB = 1024 * 1024
RGBA_BYTES_PER_PIXEL = 4
RGB_BYTES_PER_PIXEL = 3

DEFAULT_REMOVE_SECTION_DPI = 300
DEFAULT_REMOVE_SECTION_FORMAT = "jpeg"
JPEG_QUALITY = 90

FONT_FLAG_ITALIC = 2
FONT_FLAG_SERIF = 4
FONT_FLAG_MONOSPACE = 8
FONT_FLAG_BOLD = 16

# Encryption (password protection) dialog defaults — single source for the
# default permission toggles shown in app/encryption_dialog.py.
ENCRYPTION_DEFAULT_ALLOW_PRINT = True
ENCRYPTION_DEFAULT_ALLOW_COPY = True
ENCRYPTION_DEFAULT_ALLOW_MODIFY = True
ENCRYPTION_DEFAULT_ALLOW_ANNOTATE = True

TEXT_DEFAULT_FONT_SIZE = 12.0
TEXT_DEFAULT_COLOR = (0.0, 0.0, 0.0)
TEXT_PREVIEW_BLACK_COLOR = (0.15, 0.15, 0.15)
TEXT_BOX_X_PADDING = 14
TEXT_BOX_Y_PADDING = 12
TEXT_AUTOFIT_WIDTH_RATIO = 0.95
TEXT_AUTOFIT_MIN_FONT_SIZE = 6.0
TEXT_AUTOFIT_ITERATIONS = 4
TEXT_SHRINK_ITERATIONS = 4
TEXT_SHRINK_MIN_FONT_SIZE = 8
TEXT_SHRINK_FACTOR = 0.85
TEXT_METADATA_RECT_HEIGHT_RATIO = 0.6
TEXT_METADATA_MIN_FONT_SIZE = 8
TEXT_METADATA_MAX_FONT_SIZE = 72

# --- Text word-wrap (multiline replacement) ---
# When a replacement string does not fit on a single line, prefer wrapping it
# onto multiple lines (expanding the box downward) over shrinking the font.
# Wrapping preserves readability; shrinking is kept only as a fallback for
# cases where wrapping cannot help (an unbreakable word wider than the box, or
# not enough vertical room before the page edge).
TEXT_WRAP_ENABLED = True  # master switch for the wrap-first policy
TEXT_WRAP_LINE_HEIGHT_FACTOR = 1.2  # line height = fontsize * this factor
TEXT_WRAP_BOTTOM_MARGIN = 4.0  # keep at least this gap (pt) from page bottom

DEFAULT_CONFIG = {
    "window": {"width": 1200, "height": 800, "x": 100, "y": 100},
    "last_directory": "",
    "zoom_level": 1.0,
    "ui": {"history_panel_visible": True},
    "memory": {
        "remove_section_dpi_cap_mb": 500,
        "remove_section_large_warn_mb": 100,
        "merge_warn_mb": 50,
        "merge_abort_mb": 200,
    },
}


def _config_path() -> Path:
    """Resolve the writable config path at runtime."""
    return get_config_path()


def _legacy_config_path() -> Path:
    """Return the legacy project-root config path for migration."""
    return get_resource_path("config.json")


def _default_config() -> Dict[str, Any]:
    """Return a fresh deep copy of the default configuration."""
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json.

    Returns:
        Configuration dictionary with default values for missing keys
    """
    logger = get_logger()
    config_path = _config_path()
    legacy_path = _legacy_config_path()

    source_path = None
    prefer_isolated_config = bool(os.environ.get("PDF_CONTROL_APP_DATA_DIR"))
    if config_path.exists():
        source_path = config_path
    elif not prefer_isolated_config and legacy_path.exists():
        source_path = legacy_path

    if source_path is None:
        logger.info("Config file not found, using defaults")
        return _default_config()

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        # Merge with defaults (in case new keys were added)
        config = _default_config()
        _deep_update(config, user_config)

        logger.info(f"Config loaded from {source_path}")
        return config
    except (OSError, IOError) as e:
        logger.error(f"Failed to load config: {e}, using defaults")
        return _default_config()


def save_config(config: Dict[str, Any]) -> bool:
    """
    Save configuration to config.json.

    Args:
        config: Configuration dictionary to save

    Returns:
        True if successful, False otherwise
    """
    logger = get_logger()
    config_path = _config_path()

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        logger.info(f"Config saved to {config_path}")
        return True
    except (OSError, IOError) as e:
        logger.error(f"Failed to save config: {e}")
        return False


def _deep_update(base_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> None:
    """
    Recursively update base_dict with values from update_dict.

    Args:
        base_dict: Dictionary to update (modified in-place)
        update_dict: Dictionary with new values
    """
    for key, value in update_dict.items():
        if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
            _deep_update(base_dict[key], value)
        else:
            base_dict[key] = value


def get_config_value(config: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get a nested config value.

    Args:
        config: Configuration dictionary
        *keys: Nested keys to access (e.g., "window", "width")
        default: Default value if key not found

    Returns:
        Config value or default

    Example:
        >>> get_config_value(config, "window", "width", default=800)
        1200
    """
    try:
        value = config
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def set_config_value(config: Dict[str, Any], *keys: str, value: Any) -> None:
    """
    Safely set a nested config value.

    Args:
        config: Configuration dictionary (modified in-place)
        *keys: Nested keys to access (e.g., "window", "width")
        value: Value to set

    Example:
        >>> set_config_value(config, "window", "width", value=1400)
    """
    if len(keys) == 0:
        return

    # Navigate to the parent dictionary
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Set the final value
    current[keys[-1]] = value

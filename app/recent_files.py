"""Recent-files list helpers (File -> Open Recent).

Pure functions over the config dict so the menu code stays thin and the
policy (most-recent-first, de-duplicated, capped, missing files pruned on
demand) is testable without Qt.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from app.config import get_config_value, set_config_value

RECENT_FILES_KEY = "recent_files"
RECENT_FILES_LIMIT = 10


def _normalize(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def get_recent_files(config: Dict[str, Any]) -> List[str]:
    """Return the stored recent file paths, most recent first."""
    stored = get_config_value(config, RECENT_FILES_KEY, default=[])
    if not isinstance(stored, list):
        return []
    return [p for p in stored if isinstance(p, str) and p]


def add_recent_file(config: Dict[str, Any], path: str, limit: int = RECENT_FILES_LIMIT) -> List[str]:
    """Move ``path`` to the front of the recent list (deduplicated, capped).

    Mutates ``config`` in place and returns the new list. The caller is
    responsible for persisting the config.
    """
    if not path:
        return get_recent_files(config)
    key = _normalize(path)
    kept = [p for p in get_recent_files(config) if _normalize(p) != key]
    updated = [os.path.abspath(path), *kept][: max(limit, 0)]
    set_config_value(config, RECENT_FILES_KEY, value=updated)
    return updated


def remove_recent_file(config: Dict[str, Any], path: str) -> List[str]:
    """Drop ``path`` from the recent list (e.g. the file no longer exists)."""
    key = _normalize(path)
    updated = [p for p in get_recent_files(config) if _normalize(p) != key]
    set_config_value(config, RECENT_FILES_KEY, value=updated)
    return updated


def clear_recent_files(config: Dict[str, Any]) -> None:
    """Empty the recent list."""
    set_config_value(config, RECENT_FILES_KEY, value=[])

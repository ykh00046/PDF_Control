# ruff: noqa: E501  -- SVG path data is one string per icon by design
"""Built-in monochrome line icons (Fluent-style, 24px grid).

The app ships no image assets: every icon is an inline SVG path drawn with
``stroke="currentColor"`` and rendered through QtSvg at request time, tinted
with a theme token. Icons are cached per (name, color, size).

Why inline SVG instead of QStyle standard pixmaps: the standard set is the
1990s Windows look that made the toolbar feel dated; these are thin,
consistent 1.6px strokes with round caps like the WinUI icon font.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.theme import LIGHT_THEME

_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'

# Path data only; wrapped into a full <svg> by ``_svg``.
_PATHS: Dict[str, str] = {
    # --- document -------------------------------------------------------
    "open": '<path d="M3 7.5V18a1.5 1.5 0 0 0 1.5 1.5h15A1.5 1.5 0 0 0 21 18v-8A1.5 1.5 0 0 0 19.5 8.5H12l-2-2.5H4.5A1.5 1.5 0 0 0 3 7.5z"/>',
    "save": '<path d="M5 3.5h11l3 3V19a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 19V5a1.5 1.5 0 0 1 1.5-1.5z"/><path d="M8 3.5v5h7v-5M8 20.5v-6h8v6"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "doc": '<path d="M7 3h7l5 5v12a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 20V4.5A1.5 1.5 0 0 1 7.5 3z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    # --- history --------------------------------------------------------
    "undo": '<path d="M8 8H4V4"/><path d="M4.5 8A8 8 0 1 1 6 16.5"/>',
    "redo": '<path d="M16 8h4V4"/><path d="M19.5 8A8 8 0 1 0 18 16.5"/>',
    # --- selection edits ------------------------------------------------
    "delete": '<path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l.8 12.2A1.5 1.5 0 0 0 8.8 20.5h6.4a1.5 1.5 0 0 0 1.5-1.3L17.5 7"/><path d="M10 11v6M14 11v6"/>',
    "replace": '<path d="M4 9.5V6a2 2 0 0 1 2-2h6M12 4l-2.5-2.5M12 4 9.5 6.5"/><path d="M20 14.5V18a2 2 0 0 1-2 2h-6M12 20l2.5 2.5M12 20l2.5-2.5"/><path d="M6 13h5M6 17h3M14 7.5h4M14 11h2.5"/>',
    "find": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/>',
    "batch": '<circle cx="9" cy="9" r="5"/><path d="M12.5 12.5 16 16"/><path d="M14 20h7M18 17.5 21 20l-3 2.5"/>',
    # --- navigation -----------------------------------------------------
    "prev": '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
    "next": '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
    "up": '<path d="M5.5 14.5 12 8l6.5 6.5"/>',
    "down": '<path d="M5.5 9.5 12 16l6.5-6.5"/>',
    # --- zoom -----------------------------------------------------------
    "zoom-in": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21M7.5 10.5h6M10.5 7.5v6"/>',
    "zoom-out": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21M7.5 10.5h6"/>',
    "fit-width": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M7 12h10M9.5 9.5 7 12l2.5 2.5M14.5 9.5 17 12l-2.5 2.5"/>',
    # --- pages ----------------------------------------------------------
    "rotate-left": '<path d="M7 9H3V5"/><path d="M3.5 9A8 8 0 1 1 5 17"/>',
    "rotate-right": '<path d="M17 9h4V5"/><path d="M20.5 9A8 8 0 1 0 19 17"/>',
    "rotate-180": '<path d="M4 12a8 8 0 0 1 14.5-4.6M20 12a8 8 0 0 1-14.5 4.6"/><path d="M18.5 3.5v4h-4M5.5 20.5v-4h4"/>',
    "insert-page": '<path d="M7 3h7l5 5v12a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 20V4.5A1.5 1.5 0 0 1 7.5 3z"/><path d="M14 3v5h5M12 11v6M9 14h6"/>',
    "duplicate": '<rect x="8" y="8" width="12" height="12" rx="1.5"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
    "extract": '<path d="M7 3h7l5 5v5"/><path d="M14 3v5h5M7 3a1.5 1.5 0 0 0-1.5 1.5V20A1.5 1.5 0 0 0 7 21.5h6"/><path d="M17 15v7M14 19l3 3 3-3"/>',
    "merge": '<path d="M5 4v6a4 4 0 0 0 4 4h6M5 20v-6"/><path d="M12 11l3 3-3 3M19 4v16"/>',
    "split": '<path d="M12 3v18"/><path d="M4 8h5v8H4zM15 8h5v8h-5z"/>',
    "pages": '<rect x="4" y="3" width="10" height="13" rx="1.5"/><path d="M8 7h12a0 0 0 0 1 0 0v12.5a1.5 1.5 0 0 1-1.5 1.5H10a2 2 0 0 1-2-2V7z"/>',
    # --- misc -----------------------------------------------------------
    "watermark": '<path d="M4 20h16M6.5 16l5.5-13 5.5 13M8.5 11.5h7"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.7"/><path d="M21 16l-5-5-7.5 7.5M3 18l4.5-4.5 3 3"/>',
    "crop": '<path d="M6 2v14a2 2 0 0 0 2 2h14M2 6h14a2 2 0 0 1 2 2v14"/>',
    "erase": '<path d="M4.5 15.5 13 7l5 5-8.5 8.5H6l-1.5-1.5a2 2 0 0 1 0-2.8z"/><path d="M13 7l3-3 5 5-3 3M9 20.5h11"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3M12 14.5v2.5"/>',
    "unlock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 7.6-1.7M12 14.5v2.5"/>',
    "export": '<path d="M12 3v11M8 10l4 4 4-4"/><path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.7M12 17h.01"/>',
    "log": '<path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "history": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "check": '<path d="M5 12.5 9.5 17 19 7.5"/>',
    "warning": '<path d="M12 3.5 21 19.5H3z"/><path d="M12 10v4.5M12 17.2h.01"/>',
    "case": '<path d="M3 17 7.5 6l4.5 11M4.6 13h5.8"/><path d="M15 10.5h4a2 2 0 0 1 2 2V17h-6a2 2 0 0 1 0-4h6"/>',
}


def has_icon(name: str) -> bool:
    return name in _PATHS


def _svg(name: str, color: str) -> bytes:
    body = _PATHS[name].replace("currentColor", color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
        f"<g {_STROKE.replace('currentColor', color)}>{body}</g></svg>"
    ).encode("utf-8")


@lru_cache(maxsize=512)
def icon_pixmap(name: str, color: str, size: int) -> QPixmap:
    """Render one icon to a square pixmap (device-pixel aware via 2x raster)."""
    renderer = QSvgRenderer(QByteArray(_svg(name, color)))
    px = max(size, 1) * 2
    image = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


@lru_cache(maxsize=256)
def icon(name: str, color: str | None = None, size: int = 20, disabled_color: str | None = None) -> QIcon:
    """Theme-tinted QIcon with a lighter Disabled state.

    Unknown names return an empty QIcon so a typo never crashes the UI.
    """
    if name not in _PATHS:
        return QIcon()
    color = color or LIGHT_THEME.text
    disabled_color = disabled_color or LIGHT_THEME.text_disabled
    result = QIcon()
    for px in (size, size * 2):
        result.addPixmap(icon_pixmap(name, color, px), QIcon.Mode.Normal)
        result.addPixmap(icon_pixmap(name, disabled_color, px), QIcon.Mode.Disabled)
    return result


def accent_icon(name: str, size: int = 20) -> QIcon:
    """Icon tinted with the accent color (primary buttons, selected states)."""
    return icon(name, LIGHT_THEME.accent, size)

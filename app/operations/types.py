"""Type definitions for the operation application service.

Kept dependency-free so the rest of the package can import these without
circular references.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple, TypedDict


class TextMetadata(TypedDict):
    """Font metadata extracted from source text for replacement operations."""

    fontsize: float
    color: Tuple[float, float, float]
    font_flags: int
    fontname: str
    # First-line baseline y of the source text (None when no text was found).
    # Used to anchor the replacement on the original baseline (text-fidelity).
    baseline: Optional[float]
    # Distance between consecutive source baselines (None for a single line);
    # multi-line replacements reuse it so paragraph leading is preserved.
    line_pitch: Optional[float]
    # How far the replacement may extend on the same line before hitting the
    # next glyph / vertical rule (None -> no probe, stay inside the rect).
    limit_left: Optional[float]
    limit_right: Optional[float]
    # Text that was inside the rect (drives auto alignment: numbers -> right).
    source_text: str
    # A glyph immediately follows the rect on its line (mid-sentence), so a
    # numeric source stays left-aligned instead of keeping its right edge.
    glyph_after: bool


class ApplyMode(Enum):
    """Mode for applying operations to PDF pages."""

    SAVE = "save"  # Destructive: use redactions, permanent changes
    PREVIEW = "preview"  # Non-destructive: use draw_rect, temporary preview

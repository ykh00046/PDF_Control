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


class ApplyMode(Enum):
    """Mode for applying operations to PDF pages."""

    SAVE = "save"        # Destructive: use redactions, permanent changes
    PREVIEW = "preview"  # Non-destructive: use draw_rect, temporary preview

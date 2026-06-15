"""Operation to_dict -> from_dict round-trip equivalence (r4-bugfix PDCA).

Regression net for the r4 B2 bug: ``RedactReplace.to_dict`` serialized
``wrap`` but ``Operation.from_dict`` dropped it on restore, so the render
worker (which always rebuilds ops via ``from_dict``) ignored the per-replace
wrap choice -- a silent preview!=save divergence. Comparing the full
``to_dict`` payloads keeps any future field addition inside this net
automatically.
"""

import fitz
import pytest

from app.operations.base import Operation
from app.operations.crop import CropMargins
from app.operations.redact import RedactDelete, RedactReplace
from app.operations.remove_section import RemoveSectionAsImage
from app.operations.watermark import WatermarkImage, WatermarkText


def _round_trip(op: Operation) -> None:
    data = op.to_dict()
    restored = Operation.from_dict(data)
    assert type(restored) is type(op)
    assert restored.to_dict() == data


def test_redact_delete_round_trip():
    _round_trip(RedactDelete(2, [fitz.Rect(10, 20, 110, 40)]))


@pytest.mark.parametrize("wrap", [True, False, None], ids=["wrap", "shrink", "global"])
def test_redact_replace_round_trip_preserves_wrap(wrap):
    op = RedactReplace(
        1,
        [fitz.Rect(5, 5, 200, 25)],
        "replacement text",
        fontname="helv",
        fontsize=11,
        align=1,
        fontfile=None,
        color=(0.0, 0.0, 0.0),
        font_flags=0,
        wrap=wrap,
    )
    _round_trip(op)
    assert Operation.from_dict(op.to_dict()).wrap == wrap


def test_redact_replace_legacy_payload_without_wrap_defaults_to_global():
    """Pre-r4 serialized data has no "wrap" key -> None (follow global)."""
    op = RedactReplace(0, [fitz.Rect(0, 0, 50, 10)], "text")
    data = op.to_dict()
    data.pop("wrap")
    restored = Operation.from_dict(data)
    assert restored.wrap is None


def test_crop_margins_round_trip():
    _round_trip(CropMargins(0, 10, 20, 30, 40))


def test_remove_section_round_trip():
    _round_trip(RemoveSectionAsImage(3, fitz.Rect(50, 50, 300, 200), 150, "png"))


def test_watermark_round_trip():
    op = WatermarkText(
        2,
        "CONFIDENTIAL",
        fontsize=48.0,
        color=(0.4, 0.4, 0.4),
        opacity=0.25,
        angle=30.0,
    )
    _round_trip(op)
    restored = Operation.from_dict(op.to_dict())
    assert restored.text == "CONFIDENTIAL"
    assert restored.color == (0.4, 0.4, 0.4)
    assert restored.opacity == 0.25
    assert restored.angle == 30.0
    assert restored.tile is False


def test_watermark_tile_round_trip():
    op = WatermarkText(0, "TILED", tile=True)
    _round_trip(op)
    assert Operation.from_dict(op.to_dict()).tile is True


def test_watermark_legacy_payload_uses_defaults():
    """Only 'text' is mandatory; missing optional keys fall back to defaults."""
    restored = Operation.from_dict(
        {
            "type": "WatermarkText",
            "page_index": 0,
            "rects": [],
            "text": "DRAFT",
        }
    )
    assert restored.fontsize == 40.0
    assert restored.color == (0.5, 0.5, 0.5)
    assert restored.opacity == 0.3
    assert restored.angle == 45.0
    assert restored.tile is False  # pre-tiling payload defaults to centered


def test_image_watermark_round_trip():
    op = WatermarkImage(1, "/tmp/logo.png", opacity=0.4, scale=0.6, rotate=90, tile=True)
    _round_trip(op)
    restored = Operation.from_dict(op.to_dict())
    assert restored.image_path == "/tmp/logo.png"
    assert restored.opacity == 0.4
    assert restored.scale == 0.6
    assert restored.rotate == 90
    assert restored.tile is True


def test_image_watermark_legacy_payload_uses_defaults():
    restored = Operation.from_dict(
        {
            "type": "WatermarkImage",
            "page_index": 0,
            "rects": [],
            "image_path": "/tmp/x.png",
        }
    )
    assert restored.opacity == 0.3
    assert restored.scale == 0.5
    assert restored.rotate == 0

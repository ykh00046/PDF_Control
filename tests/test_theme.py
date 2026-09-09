"""Design-system guards: tokens are the single source of visual truth."""

import re
from pathlib import Path

import pytest

from app.theme import (
    LIGHT_THEME,
    Theme,
    build_stylesheet,
    callout_style,
    invalid_field_style,
    label_style,
)

ROOT = Path(__file__).parent.parent
APP = ROOT / "app"


def test_stylesheet_keeps_dark_mode_contract():
    """Popup surfaces pin a light background + menu items keep padding."""
    style = build_stylesheet(LIGHT_THEME)
    assert "QMenu::item { padding:" in style
    assert "QMessageBox QLabel { color: #1a1a1a" in style
    for selector in ("QDialog", "QMessageBox", "QComboBox QAbstractItemView", "QToolTip", "QMenu {"):
        assert selector in style


def test_tokens_propagate_into_stylesheet():
    custom = Theme(accent="#123456", bg_app="#abcdef", font_family="TestFont")
    style = build_stylesheet(custom)
    assert "#123456" in style and "#abcdef" in style and "TestFont" in style
    # and the default accent is gone
    assert LIGHT_THEME.accent not in style


def test_stylesheet_has_no_stray_placeholders():
    style = build_stylesheet(LIGHT_THEME)
    assert "{t." not in style and "}}" not in style and "{{" not in style


@pytest.mark.parametrize("kind", ["muted", "info", "success", "warning", "error"])
def test_label_style_kinds(kind):
    css = label_style(LIGHT_THEME, kind)
    assert css.startswith("color: #")
    assert "font-weight" not in css
    assert "font-weight: 600" in label_style(LIGHT_THEME, kind, emphasis=True)


def test_callout_and_invalid_styles_use_tokens():
    assert LIGHT_THEME.warning_bg in callout_style(LIGHT_THEME, "warning")
    assert LIGHT_THEME.bg_layer in callout_style(LIGHT_THEME, "neutral")
    assert LIGHT_THEME.error in invalid_field_style(LIGHT_THEME)


def test_no_hardcoded_colors_outside_theme():
    """Widgets must not carry ad-hoc hex colors / named colors in setStyleSheet."""
    offenders = []
    pattern = re.compile(r'setStyleSheet\(\s*f?"[^"]*(#[0-9a-fA-F]{3,6}|\b(red|blue|green|gray|orange)\b)')
    for path in APP.rglob("*.py"):
        if path.name == "theme.py":
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            # The watermark color swatch legitimately reflects a user-picked RGB.
            if "rgb(" in match.group(0):
                continue
            offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)[:60]}")
    assert offenders == [], offenders

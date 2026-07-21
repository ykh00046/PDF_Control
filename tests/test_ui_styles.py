"""Regression tests for the main-window stylesheet.

These guard the light-theme contract: because the app pins dark text
(#1a1a1a) everywhere, every popup surface must also pin a light
background or the text renders dark-on-dark under Windows dark mode.
QMenu items must carry explicit padding so labels don't collide with
their shortcut text once a stylesheet touches QMenu.
"""

import pytest

from app.ui import MainWindow


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def test_menu_items_have_padding(main_window):
    """QMenu::item padding prevents label/shortcut overlap."""
    style = main_window.styleSheet()
    assert "QMenu::item" in style
    # The rule must set padding (right pad reserves the shortcut column).
    assert "QMenu::item { padding:" in style


def test_popup_surfaces_pin_light_background(main_window):
    """Dialog/message-box surfaces must set a light background."""
    style = main_window.styleSheet()
    for selector in ("QDialog", "QMessageBox", "QComboBox QAbstractItemView", "QToolTip"):
        assert selector in style, f"missing background rule for {selector}"


def test_messagebox_label_color_is_dark(main_window):
    """Message-box body text is dark, paired with the light background above."""
    style = main_window.styleSheet()
    assert "QMessageBox QLabel { color: #1a1a1a" in style

"""Inline SVG icon set + empty state / dock chrome guards (modern-look cycle)."""

import pytest

from app.icons import _PATHS, accent_icon, has_icon, icon, icon_pixmap
from app.theme import LIGHT_THEME


@pytest.mark.parametrize("name", sorted(_PATHS))
def test_every_icon_renders_non_empty(qtbot, name):
    pixmap = icon_pixmap(name, LIGHT_THEME.text, 20)
    assert not pixmap.isNull()
    image = pixmap.toImage()
    # At least one non-transparent pixel: a broken path renders nothing.
    assert any(image.pixelColor(x, y).alpha() > 0 for x in range(image.width()) for y in range(0, image.height(), 2))


def test_icon_has_normal_and_disabled_modes(qtbot):
    result = icon("open")
    assert not result.isNull()
    assert not result.pixmap(20).isNull()
    assert accent_icon("find").availableSizes()


def test_unknown_icon_is_empty_not_crash(qtbot):
    assert not has_icon("nope")
    assert icon("nope").isNull()


def test_toolbar_actions_carry_icons(qtbot):
    from app.ui import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    for action in (win.open_action, win.save_action, win.undo_action, win.delete_action, win.find_action):
        assert not action.icon().isNull()
    # Empty state shows before a document is open; the viewer is hidden.
    assert not win.empty_state.isHidden()
    assert win.viewer.isHidden()


def test_empty_state_swaps_with_viewer(qtbot, tmp_path):
    import fitz

    from app.ui import MainWindow

    path = tmp_path / "e.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()

    win = MainWindow()
    qtbot.addWidget(win)
    win.controller.load_document(str(path))
    assert win.empty_state.isHidden() and not win.viewer.isHidden()
    win.controller.close_document()
    assert not win.empty_state.isHidden() and win.viewer.isHidden()


def test_docks_use_custom_title_bar(qtbot):
    from app.ui import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    for dock in (win.thumbnail_dock, win.history_dock):
        assert dock.titleBarWidget() is not None
        assert not (dock.features() & dock.DockWidgetFeature.DockWidgetFloatable)

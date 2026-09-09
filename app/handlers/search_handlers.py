"""Find-in-document handlers for :class:`app.ui.MainWindow`.

Exposes :class:`SearchHandlerMixin`: shows the :class:`~app.find_bar.FindBar`,
runs :meth:`DocumentSession.find_text`, steps through hits (wrapping), moves
the viewer to the hit's page and keeps the highlight overlay in sync with
page changes and re-renders.

Search state (``_search_hits``, ``_search_current``) lives on MainWindow like
every other handler state; the mixin itself is stateless.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from app.i18n import tr
from app.text_search import SearchHit, next_hit_index

if TYPE_CHECKING:
    from app.ui import MainWindow


class SearchHandlerMixin:
    """Ctrl+F find bar: search, next/prev, highlight sync."""

    # ------------------------------------------------------------ show/hide
    def show_find_bar(self: "MainWindow") -> None:  # type: ignore[misc]
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return
        self.find_bar.show()
        self.find_bar.focus_query()

    def _on_find_bar_closed(self: "MainWindow") -> None:  # type: ignore[misc]
        self._reset_search()
        self.viewer.setFocus()

    # --------------------------------------------------------------- search
    def _reset_search(self: "MainWindow", *_args) -> None:  # type: ignore[misc]
        """Drop hits + highlights (document changed/closed, bar closed)."""
        self._search_hits: List[SearchHit] = []
        self._search_current = -1
        self.viewer.clear_highlights()
        if not self.find_bar.isHidden():
            self.find_bar.set_result_count(-1, 0)

    def _on_find_query(self: "MainWindow", query: str, case_sensitive: bool) -> None:  # type: ignore[misc]
        session = self.controller.session
        if not session:
            self._reset_search()
            return
        try:
            self._search_hits = session.find_text(query, case_sensitive=case_sensitive)
        except Exception as e:  # search must never take the window down
            self.logger.error(f"Find failed: {e}")
            self._search_hits = []
        self._search_current = -1
        if self._search_hits:
            # Start from the first hit on or after the current page so the
            # user is not yanked back to page 1 for every keystroke.
            page = self.viewer.current_page_index
            first = next((i for i, h in enumerate(self._search_hits) if h.page_index >= page), 0)
            self._select_hit(first)
        else:
            self.viewer.clear_highlights()
            self.find_bar.set_result_count(-1, 0)
        self.logger.info(f"Find '{query}': {len(self._search_hits)} hit(s)")

    def _rerun_search(self: "MainWindow") -> None:  # type: ignore[misc]
        """Re-run the current query (page set changed under the hits).

        ``isHidden`` (not ``isVisible``) so the bar's own state counts even
        while the main window itself is not shown (offscreen tests).
        """
        if not self.find_bar.isHidden() and self.find_bar.query().strip():
            self._on_find_query(self.find_bar.query(), self.find_bar.case_sensitive())
        else:
            self._reset_search()

    def find_next(self: "MainWindow") -> None:  # type: ignore[misc]
        self._step_hit(+1)

    def find_prev(self: "MainWindow") -> None:  # type: ignore[misc]
        self._step_hit(-1)

    def _step_hit(self: "MainWindow", step: int) -> None:  # type: ignore[misc]
        hits = getattr(self, "_search_hits", [])
        index = next_hit_index(len(hits), getattr(self, "_search_current", -1), step)
        if index < 0:
            return
        self._select_hit(index)

    def _select_hit(self: "MainWindow", index: int) -> None:  # type: ignore[misc]
        self._search_current = index
        hit = self._search_hits[index]
        if hit.page_index != self.viewer.current_page_index:
            self._go_to_page(hit.page_index)  # page_changed re-applies highlights
        self._apply_search_highlights()
        self.find_bar.set_result_count(index, len(self._search_hits))

    # ----------------------------------------------------------- highlights
    def _apply_search_highlights(self: "MainWindow", *_args) -> None:  # type: ignore[misc]
        """Push this page's hit rects (and the current one) to the viewer."""
        hits = getattr(self, "_search_hits", [])
        if not hits:
            self.viewer.clear_highlights()
            return
        page = self.viewer.current_page_index
        rects = [h.rect for h in hits if h.page_index == page]
        current = getattr(self, "_search_current", -1)
        current_rect = None
        if 0 <= current < len(hits) and hits[current].page_index == page:
            current_rect = hits[current].rect
        self.viewer.set_highlights(rects, current_rect)

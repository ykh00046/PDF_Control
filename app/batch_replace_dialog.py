import re
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.i18n import tr
from app.logger import get_logger
from app.text_utils import parse_page_range, sanitize_unicode


class BatchReplaceDialog(QDialog):
    # Signal to emit when replacements are confirmed
    replacements_confirmed = Signal(list) # List of dicts: {"page_index": int, "rect": fitz.Rect, "new_text": str}

    def __init__(self, document_session, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("batch.title"))
        self.setGeometry(200, 200, 800, 600)

        self.document_session = document_session
        self.matches: List[Dict[str, Any]] = [] # Stores all found matches
        self.logger = get_logger()

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Find/Replace Input ---
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel(tr("batch.find_what")))
        self.find_what_input = QLineEdit()
        input_layout.addWidget(self.find_what_input)
        input_layout.addWidget(QLabel(tr("batch.replace_with")))
        self.replace_with_input = QLineEdit()
        input_layout.addWidget(self.replace_with_input)

        self.use_regex_checkbox = QCheckBox(tr("batch.use_regex"))
        self.use_regex_checkbox.setToolTip(tr("batch.use_regex.tooltip"))
        input_layout.addWidget(self.use_regex_checkbox)

        self.find_button = QPushButton(tr("batch.button.find"))
        self.find_button.clicked.connect(self._find_all_matches)
        input_layout.addWidget(self.find_button)

        main_layout.addLayout(input_layout)

        # --- Page Range Filter ---
        page_range_layout = QHBoxLayout()
        page_range_layout.addWidget(QLabel(tr("batch.page_range")))
        self.page_range_input = QLineEdit()
        self.page_range_input.setPlaceholderText(tr("batch.page_range.placeholder"))
        self.page_range_input.setToolTip(tr("batch.page_range.tooltip"))
        self.page_range_input.setMaximumWidth(200)
        page_range_layout.addWidget(self.page_range_input)
        page_range_layout.addStretch()
        main_layout.addLayout(page_range_layout)

        # --- Font Size Options ---
        font_layout = QHBoxLayout()
        self.use_fixed_font_checkbox = QCheckBox(tr("batch.use_fixed_font"))
        self.use_fixed_font_checkbox.setToolTip(tr("batch.use_fixed_font.tooltip"))
        self.use_fixed_font_checkbox.toggled.connect(self._on_fixed_font_toggled)
        font_layout.addWidget(self.use_fixed_font_checkbox)

        font_layout.addWidget(QLabel(tr("batch.font_size")))
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 72)
        self.font_size_spinbox.setValue(12)
        self.font_size_spinbox.setSuffix(" pt")
        self.font_size_spinbox.setEnabled(False)  # Disabled by default
        font_layout.addWidget(self.font_size_spinbox)

        # Word-wrap policy: when checked (default), overflowing replacements
        # wrap onto multiple lines; when unchecked, the font shrinks instead.
        self.use_wrap_checkbox = QCheckBox(tr("batch.use_wrap"))
        self.use_wrap_checkbox.setToolTip(tr("batch.use_wrap.tooltip"))
        self.use_wrap_checkbox.setChecked(True)
        font_layout.addWidget(self.use_wrap_checkbox)

        font_layout.addStretch()
        main_layout.addLayout(font_layout)

        # --- Status Label ---
        self.status_label = QLabel(tr("batch.status.initial"))
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(self.status_label)

        # --- Matches Table ---
        self.matches_table = QTableWidget()
        self.matches_table.setColumnCount(4)
        self.matches_table.setHorizontalHeaderLabels([
            tr("batch.header.page"), tr("batch.header.context"),
            tr("batch.header.found_text"), tr("batch.header.replace"),
        ])
        self.matches_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.matches_table.setSelectionBehavior(QAbstractItemView.SelectRows) # Select whole rows
        main_layout.addWidget(self.matches_table)

        # --- Control Buttons ---
        button_layout = QHBoxLayout()
        self.replace_all_button = QPushButton(tr("batch.button.replace_selected"))
        self.replace_all_button.clicked.connect(self._confirm_replacements)
        self.replace_all_button.setEnabled(False) # Disable until matches are found
        button_layout.addWidget(self.replace_all_button)

        self.cancel_button = QPushButton(tr("batch.button.cancel"))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

    def _on_fixed_font_toggled(self, checked):
        """Enable/disable font size spinbox based on checkbox state."""
        self.font_size_spinbox.setEnabled(checked)

    def _get_target_pages(self):
        """Parse page range input and return set of 0-based page indices."""
        page_range_text = self.page_range_input.text().strip()
        total_pages = self.document_session.doc.page_count

        if not page_range_text:
            return set(range(total_pages))

        try:
            return parse_page_range(page_range_text, total_pages)
        except ValueError as e:
            QMessageBox.warning(
                self,
                tr("batch.error.page_range.title"),
                tr("batch.error.page_range.message", str(e))
            )
            return None

    def _find_all_matches(self):
        find_text = self.find_what_input.text()
        if not find_text:
            QMessageBox.warning(self, tr("batch.error.input.title"), tr("batch.error.input.message"))
            return

        target_pages = self._get_target_pages()
        if target_pages is None:
            return

        use_regex = self.use_regex_checkbox.isChecked()

        self.matches.clear()
        self.matches_table.setRowCount(0)
        self.replace_all_button.setEnabled(False)
        self.status_label.setText(tr("batch.status.searching"))
        self.status_label.setStyleSheet("color: blue; font-style: italic;")

        if use_regex:
            self._find_with_regex(find_text, target_pages)
        else:
            self._find_exact_string(find_text, target_pages)

        self._populate_matches_table()

        if self.matches:
            self.replace_all_button.setEnabled(True)
            mode_str = tr("batch.mode.regex") if use_regex else tr("batch.mode.string")
            self.status_label.setText(tr("batch.status.found", len(self.matches), mode_str, find_text))
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.logger.info(f"Batch find: Found {len(self.matches)} occurrences (regex={use_regex})")
        else:
            self.status_label.setText(tr("batch.status.not_found"))
            self.status_label.setStyleSheet("color: orange; font-style: italic;")
            self.logger.info(f"Batch find: No occurrences found (regex={use_regex})")

    def _find_exact_string(self, find_text: str, target_pages=None):
        """Find exact string matches using PyMuPDF's search_for."""
        all_pages = range(self.document_session.doc.page_count)
        for page_idx in all_pages:
            if target_pages is not None and page_idx not in target_pages:
                continue
            page = self.document_session.doc[page_idx]
            found_rects = page.search_for(find_text)

            for rect in found_rects:
                context_text = page.get_textbox(rect.expanded(20))

                self.matches.append({
                    "page_index": page_idx,
                    "rect": rect,
                    "found_text": find_text,
                    "context": context_text,
                    "replace": True
                })

    def _find_with_regex(self, pattern: str, target_pages=None):
        """Find matches using regular expression pattern."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            QMessageBox.critical(self, tr("batch.error.regex.title"), tr("batch.error.regex.message", e))
            self.status_label.setText(tr("batch.error.regex.message", e))
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        for page_idx in range(self.document_session.doc.page_count):
            if target_pages is not None and page_idx not in target_pages:
                continue
            page = self.document_session.doc[page_idx]

            # Get page text for regex matching (sanitize invalid Unicode)
            page_text = sanitize_unicode(page.get_text())

            # Find all matches in the page text
            for match in regex.finditer(page_text):
                matched_text = match.group(0)

                # Find the corresponding rectangle(s) for this match
                # This is approximate: we search for the matched text
                found_rects = page.search_for(matched_text)

                if found_rects:
                    rect = found_rects[0]  # Use first match (may not be perfect)
                    context_text = page.get_textbox(rect.expanded(20))

                    self.matches.append({
                        "page_index": page_idx,
                        "rect": rect,
                        "found_text": matched_text,
                        "context": context_text,
                        "replace": True
                    })

    def _populate_matches_table(self):
        self.matches_table.setRowCount(len(self.matches))
        for i, match in enumerate(self.matches):
            self.matches_table.setItem(i, 0, QTableWidgetItem(str(match["page_index"] + 1))) # Page number
            self.matches_table.setItem(i, 1, QTableWidgetItem(match["context"]))
            self.matches_table.setItem(i, 2, QTableWidgetItem(match["found_text"]))

            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Checked if match["replace"] else Qt.Unchecked)
            self.matches_table.setItem(i, 3, checkbox_item)

            # Connect checkbox state change to update internal match data
            checkbox_item.setData(Qt.UserRole, i) # Store row index
            # This would require connecting signal, which is more complex for direct table item
            # For simplicity, we'll read all checkboxes on _confirm_replacements

    def _confirm_replacements(self):
        replacements_to_emit = []
        replace_text = self.replace_with_input.text()

        # Get fixed font size if enabled
        fixed_fontsize = None
        if self.use_fixed_font_checkbox.isChecked():
            fixed_fontsize = self.font_size_spinbox.value()

        # Word-wrap policy chosen by the user for this batch.
        wrap_enabled = self.use_wrap_checkbox.isChecked()

        for i, match in enumerate(self.matches):
            checkbox_item = self.matches_table.item(i, 3)
            if checkbox_item.checkState() == Qt.Checked:
                replacements_to_emit.append({
                    "page_index": match["page_index"],
                    "rect": match["rect"],
                    "new_text": replace_text,
                    "fontsize": fixed_fontsize,  # None for auto, or fixed value
                    "wrap": wrap_enabled         # True=wrap, False=shrink
                })

        if replacements_to_emit:
            self.replacements_confirmed.emit(replacements_to_emit)
            self.accept()
        else:
            QMessageBox.information(self, tr("batch.error.no_selection.title"), tr("batch.error.no_selection.message"))


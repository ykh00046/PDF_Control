from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QMessageBox, QDoubleSpinBox, QGroupBox)
from PySide6.QtCore import Qt, Signal
from app.i18n import tr
import fitz

class RemoveSectionDialog(QDialog):
    """영역 제거 (이미지 변환) 다이얼로그 - 정밀 좌표 입력 기능 포함"""

    remove_confirmed = Signal(dict)  # {"dpi": int, "format": str, "rect": fitz.Rect}

    def __init__(self, page: fitz.Page, selected_rect: fitz.Rect, parent=None):
        super().__init__(parent)
        self.page = page
        self.selected_rect = fitz.Rect(selected_rect) # Copy
        self.page_rect = page.rect

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(tr("remove.dialog.title"))
        self.setModal(True)
        self.resize(500, 550)

        layout = QVBoxLayout(self)

        # 1. 경고 메시지
        warning_label = QLabel(f"<h3>⚠️ {tr('remove.warning.title')}</h3><p>{tr('remove.warning.message')}</p>")
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("background-color: #fff3cd; color: #664d03; padding: 10px; border: 1px solid #ffc107; border-radius: 4px;")
        layout.addWidget(warning_label)

        # 2. 정밀 좌표 입력 그룹
        coord_group = QGroupBox(tr("remove.precision.title") if "remove.precision.title" in tr("remove.precision.title") else "Precision Adjustment")
        coord_layout = QVBoxLayout(coord_group)

        # Y0 (상단)
        y0_layout = QHBoxLayout()
        y0_label = QLabel(f"{tr('remove.info.y0') if 'remove.info.y0' in tr('remove.info.y0') else 'Top (Y0)'}:")
        self.y0_spin = QDoubleSpinBox()
        self.y0_spin.setRange(0, self.page_rect.height)
        self.y0_spin.setValue(self.selected_rect.y0)
        self.y0_spin.setSuffix(" pt")
        self.y0_spin.setDecimals(1)
        self.y0_spin.valueChanged.connect(self._on_coords_changed)
        
        y0_snap_btn = QPushButton(tr("remove.snap.top") if "remove.snap.top" in tr("remove.snap.top") else "To Top")
        y0_snap_btn.setFixedWidth(80)
        y0_snap_btn.clicked.connect(lambda: self.y0_spin.setValue(0))
        
        y0_layout.addWidget(y0_label)
        y0_layout.addWidget(self.y0_spin)
        y0_layout.addWidget(y0_snap_btn)
        coord_layout.addLayout(y0_layout)

        # Y1 (하단)
        y1_layout = QHBoxLayout()
        y1_label = QLabel(f"{tr('remove.info.y1') if 'remove.info.y1' in tr('remove.info.y1') else 'Bottom (Y1)'}:")
        self.y1_spin = QDoubleSpinBox()
        self.y1_spin.setRange(0, self.page_rect.height)
        self.y1_spin.setValue(self.selected_rect.y1)
        self.y1_spin.setSuffix(" pt")
        self.y1_spin.setDecimals(1)
        self.y1_spin.valueChanged.connect(self._on_coords_changed)
        
        y1_snap_btn = QPushButton(tr("remove.snap.bottom") if "remove.snap.bottom" in tr("remove.snap.bottom") else "To Bottom")
        y1_snap_btn.setFixedWidth(80)
        y1_snap_btn.clicked.connect(lambda: self.y1_spin.setValue(self.page_rect.height))
        
        y1_layout.addWidget(y1_label)
        y1_layout.addWidget(self.y1_spin)
        y1_layout.addWidget(y1_snap_btn)
        coord_layout.addLayout(y1_layout)

        layout.addWidget(coord_group)

        # 3. 결과 정보 (실시간 갱신됨)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 10px; border: 1px solid #ccc; border-radius: 4px; background-color: #f8f9fa; color: #1a1a1a;")
        layout.addWidget(self.info_label)
        self._update_info_label()

        # 4. 설정 (DPI, 포맷)
        settings_layout = QHBoxLayout()
        dpi_label = QLabel(tr("remove.option.dpi"))
        self.dpi_combo = QComboBox()
        self.dpi_combo.addItems(["150", "300", "600"])
        self.dpi_combo.setCurrentIndex(1)
        settings_layout.addWidget(dpi_label)
        settings_layout.addWidget(self.dpi_combo)
        settings_layout.addSpacing(20)
        format_label = QLabel(tr("remove.option.format"))
        self.format_combo = QComboBox()
        self.format_combo.addItem(tr("remove.format.jpeg"), "jpeg")
        self.format_combo.addItem(tr("remove.format.png"), "png")
        settings_layout.addWidget(format_label)
        settings_layout.addWidget(self.format_combo)
        layout.addLayout(settings_layout)

        layout.addStretch()

        # 5. 버튼
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton(tr("remove.button.cancel"))
        apply_btn = QPushButton(tr("remove.button.apply"))
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self.apply_remove)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(apply_btn)
        layout.addLayout(button_layout)

    def _on_coords_changed(self):
        """좌표 입력 변경 시 내부 rect와 정보 레이블 업데이트"""
        y0 = self.y0_spin.value()
        y1 = self.y1_spin.value()
        
        # 유효성 검사 (y1은 y0보다 커야 함)
        if y1 <= y0:
            self.y1_spin.setStyleSheet("border: 1px solid red;")
            self.y0_spin.setStyleSheet("border: 1px solid red;")
        else:
            self.y1_spin.setStyleSheet("")
            self.y0_spin.setStyleSheet("")
            
        self.selected_rect.y0 = y0
        self.selected_rect.y1 = y1
        self._update_info_label()

    def _update_info_label(self):
        removed_height = self.selected_rect.height
        new_height = max(0, self.page_rect.height - removed_height)

        info_html = f"""
        <p><b>{tr("remove.info.title")}</b></p>
        <p>{tr("remove.info.remove_area")}: {self.selected_rect.y0:.1f}pt ~ {self.selected_rect.y1:.1f}pt
           ({tr("remove.info.height")}: {removed_height:.1f}pt)</p>
        <p>{tr("remove.info.result_height")}: {new_height:.1f}pt
           ({tr("remove.info.original")}: {self.page_rect.height:.1f}pt)</p>
        """
        self.info_label.setText(info_html)

    def apply_remove(self):
        if self.selected_rect.y1 <= self.selected_rect.y0:
            QMessageBox.warning(self, tr("dialog.error"), "Invalid range: Y1 must be greater than Y0")
            return
            
        dpi = int(self.dpi_combo.currentText())
        format_type = self.format_combo.currentData()

        self.remove_confirmed.emit({
            "dpi": dpi,
            "format": format_type,
            "rect": self.selected_rect # Pass the modified rect
        })
        self.accept()

# Design: ui_handlers.py 4-Mixin 파일 분리

> **Plan ref**: [`01-plan/features/ui-handlers-split.plan.md`](../../01-plan/features/ui-handlers-split.plan.md)
> **Status**: 🟢 Approved
> **Created**: 2026-05-27

---

## 1. Target Architecture

### Before
```
app/
└── ui_handlers.py    894 lines  (4 mixins in one file)
```

### After
```
app/
├── ui_handlers.py            ~15 lines  (backward-compat shim)
└── handlers/
    ├── __init__.py           ~15 lines  (re-export 4 mixins)
    ├── file_handlers.py     ~150 lines  (FileHandlerMixin)
    ├── edit_handlers.py     ~215 lines  (EditHandlerMixin)
    ├── dialog_handlers.py   ~310 lines  (DialogHandlerMixin)
    └── state_handlers.py    ~200 lines  (StateUpdateMixin)
```

## 2. Module Responsibility Matrix

| Module | Mixin | Methods | 주요 의존 |
|---|---|---|---|
| `file_handlers.py` | FileHandlerMixin | `open_file`, `save_file_as`, `closeEvent`, `dragEnterEvent`, `dropEvent` | `QFileDialog`, `QMessageBox`, `config.save_config/set_config_value` |
| `edit_handlers.py` | EditHandlerMixin | `undo_operation`, `redo_operation`, `delete_selection`, `_snap_selection_to_text`, `_prompt_replacement_text`, `_resolve_replacement_font`, `replace_selection`, `select_replacement_font` | `fitz`, `QInputDialog`, `QFontDialog`, `model.RedactDelete/Replace`, `text_utils.contains_hangul` |
| `dialog_handlers.py` | DialogHandlerMixin | `open_batch_replace_dialog`, `process_batch_replacements`, `open_crop_dialog`, `apply_crop`, `open_remove_section_dialog`, `apply_remove_section`, `open_page_manager_dialog`, `_on_pages_changed`, `view_logs`, `show_help` | `QProgressDialog`, `BatchReplaceDialog`, `CropPreviewDialog`, `RemoveSectionDialog`, `PageManagerDialog`, `logger.get_log_file_path`, `model.CropMargins/RemoveSectionAsImage` |
| `state_handlers.py` | StateUpdateMixin | `on_document_loaded`, `_on_warnings_changed`, `on_document_closed`, `on_operation_applied`, `_handle_page_changed`, `on_error_occurred`, `handle_selection_made`, `_get_operation_display_name`, `_update_history_panel`, `_update_edit_action_states`, `_toggle_history_panel`, `_on_page_spinbox_changed` | `QListWidgetItem`, `QStyle`, `model.RedactDelete/RedactReplace/CropMargins/RemoveSectionAsImage` |

## 3. Backward-Compat Strategy

### `app/handlers/__init__.py`
```python
"""Event handler mixins for MainWindow (split package).

Re-exports the four mixins so legacy imports keep working:

    from app.handlers import FileHandlerMixin, ...
"""
from app.handlers.dialog_handlers import DialogHandlerMixin
from app.handlers.edit_handlers import EditHandlerMixin
from app.handlers.file_handlers import FileHandlerMixin
from app.handlers.state_handlers import StateUpdateMixin

__all__ = [
    "FileHandlerMixin",
    "EditHandlerMixin",
    "DialogHandlerMixin",
    "StateUpdateMixin",
]
```

### `app/ui_handlers.py` (shim)
```python
"""Backward-compat shim. Mixins now live in :mod:`app.handlers`.

Existing call sites such as ``from app.ui_handlers import FileHandlerMixin``
continue to work; new code should prefer :mod:`app.handlers`.
"""
from app.handlers import (  # noqa: F401
    DialogHandlerMixin,
    EditHandlerMixin,
    FileHandlerMixin,
    StateUpdateMixin,
)

__all__ = [
    "FileHandlerMixin",
    "EditHandlerMixin",
    "DialogHandlerMixin",
    "StateUpdateMixin",
]
```

이 전략의 효과:
- `app/ui.py` 변경 0 줄
- 향후 신규 코드는 `app.handlers.*`를 명시적으로 사용 가능
- `ui_handlers.py`의 제거 시점은 별도 PDCA 결정 (지금 삭제하지 않음 → 안전성 우선)

## 4. Per-File Import 분리 원칙

각 핸들러 모듈은 **자기 코드에서 실제 사용하는 심볼만** import.
원본의 글로벌 import 블록을 그대로 복사하지 않음 (lint 잡음 방지).

| Symbol | file | edit | dialog | state |
|---|:---:|:---:|:---:|:---:|
| `os` | ✓ | ✓ | ✓ | ✓ |
| `subprocess`, `sys` |   |   | ✓ |   |
| `time` |   |   |   | ✓ |
| `fitz` |   | ✓ |   |   |
| `Qt` |   |   | ✓ |   |
| `QApplication` |   |   | ✓ |   |
| `QFileDialog`, `QInputDialog`, `QLineEdit` | ✓ | ✓ |   |   |
| `QMessageBox` | ✓ | ✓ | ✓ | ✓ |
| `QProgressDialog` |   |   | ✓ |   |
| `QListWidgetItem`, `QStyle` |   |   |   | ✓ |
| `BatchReplaceDialog` |   |   | ✓ |   |
| `save_config`, `set_config_value` | ✓ | ✓ |   | ✓ |
| `tr` | ✓ | ✓ | ✓ | ✓ |
| `get_log_file_path` |   |   | ✓ |   |
| `RedactDelete`, `RedactReplace` |   | ✓ |   | ✓ |
| `CropMargins`, `RemoveSectionAsImage` |   |   | ✓ | ✓ |
| `contains_hangul` |   | ✓ |   |   |

지연 import는 원본과 동일하게 보존 (예: `app.crop_dialog`는 `open_crop_dialog` 안에서, `app.fonts.get_default_korean_font_path`는 `_resolve_replacement_font` 안에서).

## 5. TYPE_CHECKING 전략

모든 핸들러 모듈은 동일 패턴:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.ui import MainWindow
```
런타임 순환 import 방지 + IDE/mypy의 `MainWindow` 타입 추론 유지.

## 6. 무결성 보장 (Migration Invariants)

1. **메서드 시그니처 보존**: 어떤 메서드도 시그니처/return type/decorator 변경 없음
2. **메서드 위치 외 동작 변경 0**: 함수 본문 한 줄도 수정하지 않음 — Mixin 클래스 사이의 빈 줄/구분선만 제거
3. **클래스 docstring은 보존**, 모듈 docstring은 단일 Mixin 범위로 축소
4. **`# noqa` 주석 보존**: 원본의 `# noqa: F401`, `# type: ignore[misc]` 등 그대로
5. **encoding**: UTF-8(no BOM) 유지

## 7. Test Plan (QA Phase 사전 정의)

```
1. Smoke import (4 modules + shim) — Python 인터프리터 직접 실행
2. pytest tests/test_smoke.py                       — 핵심 동선
3. pytest tests/test_ui.py                          — UI 핸들러
4. pytest tests/test_regressions.py                 — 회귀
5. pytest tests/                                    — 전체
6. mypy app/operations_service.py                   — 기존 게이트
```

## 8. Decision Log

| 결정 | 채택안 | 대안 | 사유 |
|---|---|---|---|
| 분리 단위 | 패키지(`app/handlers/`) | 평탄(`app/file_handlers.py` 등 4파일) | 4개 파일이 의미상 단일 그룹 → 패키지가 의도 명확 |
| `ui_handlers.py` 처리 | shim 유지 | 즉시 삭제 | `ui.py`의 import 안정성. 다음 PDCA에서 삭제 검토 |
| import 재구성 | per-file 최소화 | 모든 파일에 동일 블록 | unused-import 잡음 방지, 의존 관계 명시화 |
| `_extract_text_metadata` lazy import | 보존 | top-level로 승격 | 원본 위치(`replace_selection` 안)에서 의도된 지연 → 변경하지 않음 |

---

**Next**: implementation in Phase 3 (Do).

# CLAUDE.md

> **Summary**: PDF Control - Desktop PDF editing application with text selection, deletion, replacement, cropping, and section imaging capabilities
>
> **Project Level**: Starter
> **Tech Stack**: PySide6 + PyMuPDF
> **Status**: Active Development
> **Created**: 2025-12-16
> **Last Modified**: 2026-06-10

---

## Project Overview

PDF Control is a desktop application that enables users to:

- Select and manipulate text in PDF files (delete, replace)
- Crop and remove sections with image conversion
- Batch find/replace operations
- Undo/redo history management
- Multi-language support (en/ko)

### Key Features

- PDF open/save with preview
- Text selection-based operations (delete, replace)
- Custom and system font support
- Batch find/replace with regex
- History panel with undo/redo
- Viewer with zoom/pan controls
- Crop/section removal with image conversion
- i18n support (English/Korean)

---

## Project Level: Starter

### Detection Criteria Met

- Single desktop application
- No backend services
- No infrastructure (terraform, k8s, docker-compose)
- No monorepo structure
- Simple dependency management (requirements.txt)

### Level-Specific Rules

- **Explanation**: Friendly, detailed comments for beginners
- **Code Comments**: Detailed explanations for complex logic
- **Error Handling**: Step-by-step user guidance
- **Documentation**: Simple, practical guides

---

## Tech Stack

### Core

- **PySide6**: Desktop UI framework (Qt for Python)
- **PyMuPDF (fitz)**: PDF manipulation library
- **Pillow**: Image processing

### Development

- **pytest**: Testing framework
- **pytest-qt**: Qt-specific testing utilities

### Build/Deployment

- **PyInstaller**: Executable packaging

---

## Project Structure

```
PDF_Control/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── config.json               # Application configuration
├── app/                      # Main application package
│   ├── ui.py                # Main window UI
│   ├── viewer.py            # PDF viewer widget
│   ├── model.py             # Document session & operations
│   ├── controller.py        # Application controller
│   ├── config.py            # Configuration management
│   ├── fonts.py             # Font management
│   ├── logger.py            # Logging utilities
│   ├── i18n.py             # Internationalization
│   ├── i18n/               # Translation files
│   │   ├── en.json
│   │   └── ko.json
│   ├── batch_replace_dialog.py
│   ├── crop_dialog.py
│   └── remove_section_dialog.py
├── tests/                    # Test suite
├── .appdata/                 # Dev-only runtime config/log output
├── build/                    # PyInstaller intermediate output
├── dist/                     # Frozen build output
└── logs/                     # Test/review scratch output
```

## Source Boundary

- Source of truth: `app/`, `tests/`, `scripts/`, `docs/`, and top-level project files
- Generated runtime/test/build output: `.appdata/`, `.pytest_cache/`, `.pytest_tmp/`, `build/`, `dist/`, `logs/`, `__pycache__/`
- Development logs/config should land in `.appdata/`
- Frozen build logs/config should land in the platform app-data directory

---

## Development Rules

### Code Quality Standards

#### DRY (Don't Repeat Yourself)

- Extract to common function on 2nd use
- Reuse existing utilities in `app/` modules

#### SRP (Single Responsibility Principle)

- One function, one responsibility
- Keep functions focused and testable

#### No Hardcoding

- Use `config.py` for configuration
- Use i18n for all user-facing strings

#### Extensibility

- Write in generalized patterns
- Design for future enhancements

### Refactoring Triggers

- Same code appears 2nd time → Extract to function
- Function exceeds 50 lines → Split into smaller functions
- if-else nests 3+ levels → Simplify logic
- Same parameters passed to multiple functions → Create config object

---

## Naming Conventions

### Python Files

- `snake_case.py` for modules (e.g., `batch_replace_dialog.py`)
- `PascalCase` for classes (e.g., `MainWindow`, `DocumentSession`)
- `snake_case` for functions/methods (e.g., `apply_operations_to_page`)

### Constants

- `UPPER_SNAKE_CASE` for constants (e.g., `DEFAULT_CONFIG`)

### Variables

- Descriptive names (e.g., `temp_doc`, `render_worker`)
- Avoid single letters except for common iterators (i, j)

---

## Testing Strategy

### Current Coverage

- Basic smoke tests
- Undo/redo functionality
- Remove section operations
- Async rendering

### Test Organization

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_ui.py              # UI integration tests
├── test_model.py           # Document session tests
└── test_operations.py      # Operation logic tests
```

### Testing Guidelines

- Use `pytest-qt` for UI tests
- Use fixtures for PDF creation (avoid file dependencies)
- Test preview=save equivalence
- Test i18n key completeness

---

## Known Issues & Risks

### Current Issues

_None currently tracked. Open a new item here if one surfaces._

### Resolved (2026-04-14 review)

- ~~Config default pollution~~: `_default_config()` uses `copy.deepcopy` (`app/config.py:37-39`)
- ~~Preview temp document close leak~~: `finally` block ensures close (`app/pdf_engine.py:85-113`)
- ~~RemoveSection memory guard~~: DPI auto-cap + memory budget (`app/model.py:163-264`)
- ~~Preview-Save logic divergence~~: Unified via `ApplyMode` enum (`app/operations_service.py:65-143`)

### Resolved (2026-04-15)

- ~~Long Text in Narrow Areas~~: Structured `OpWarning` surfaces shrink/overflow into status bar, history badge, and save-time guard (`app/operations_service.py:33-60`, `app/ui.py:780-822`)

### Resolved (2026-06-11, r7-history-policy PDCA)

- ~~히스토리 정책 비대칭~~: delete/insert는 히스토리 인덱스를 보정하는데 move/duplicate/merge/드래그 정렬은 전부 폐기하던 비대칭 해소. `_remap_history_after_reorder(remap)` 공통 헬퍼로 **재배열 시 미저장 편집이 물리 페이지를 따라 보존**(redo는 무효화 — delete와 동일). move 리매핑은 PyMuPDF `move_page` 시맨틱 실측("원래 번호 기준 to 앞 삽입": `frm<to→to-1`, `frm>to→to`) 기반. 신규 `DocumentSession.reorder_pages(new_order)`가 드래그 정렬을 캡슐화(`page_manager_dialog`의 `session.doc.select`+private 호출 제거). `_rebuild_after_reorder` 삭제.
- ~~RemoveSection 가짜 진행률~~: 2026-06-10 검토 H3 재검증 결과 op 추가는 즉시 완료(무거운 렌더는 이미 렌더 워커 서브프로세스에서 비동기)였고, 25/50/75 진행률은 실제 작업과 무관한 장식 — QProgressDialog 제거, 미사용 i18n 키 6종(en/ko) 정리. 235 tests pass.

### Resolved (2026-06-10, r6-quality PDCA)

- ~~controller 예외 평탄화~~: 페이지 관리·내보내기 10개 메서드가 반복하던 `try/except Exception → log → emit` 보일러플레이트를 `_run_session_action` 가드 헬퍼 1곳으로 통합. `ValueError`(사용자 검증 거부)는 warning, 내부 오류는 error 로그로 분리 — emit 동작은 동일. 신규 `tests/test_controller_guard.py` 5종. 부수 수정: `merge_pdfs`/`duplicate_pages`/`export_text`의 int 반환이 0일 때 거짓 실패로 읽히지 않도록 결과 명시 폐기.
- ~~applicator 함수 내 지연 import·과대 함수~~: `from app.model import` 6회를 모듈 상단 직수입(형제 모듈 + `text_metadata`)으로 통합(순환 없음 확인). `_insert_text_with_autofit`(~150줄)를 `_compute_text_layout`/`_grow_rect_for_wrap`/`_shrink_fontsize_to_width`로 분해 — 경고 코드·폴백 순서 동작 불변.
- ~~typing-legacy-core~~: `pdf_engine`/`document_session`/`document_model`/`model` 4개 모듈 mypy strict 승격(`warn_return_any=False`, fitz 무스텁 정책은 operations 게이트와 동일). `operations_service` 셰임 경유 import를 `app.operations` 직수입으로 교체. STRICT_LEAF_MODULES 12개로 확대. 226 tests pass.

### Added (2026-06-10, r5-infra PDCA)

- **CI + 의존성 고정 + 루트 정리**: `.github/workflows/ci.yml` 신설(windows-latest, Python 3.13, `QT_QPA_PLATFORM=offscreen`, `pytest tests -q` — mypy 게이트·i18n·drift 가드 포함). `requirements.txt` 전 항목 `==` 핀 고정 + 테스트 의존성(mypy, pytest-timeout, PyYAML) 명시. `app/ui_handlers.py` 셰임 제거(`ui.py`가 `app.handlers` 직수입). deprecated 루트 문서 3종 → `docs/archive/legacy-root/`, 스크래치 스크립트 5종 → `scripts/`(경로 부트스트랩 보정). pyproject/ruff는 별도 사이클로 보류.

### Resolved (2026-06-10, r4-bugfix PDCA)

- ~~mypy 게이트 인코딩 회귀~~: `mypy.ini` 주석의 em-dash(U+2014)가 cp949 로케일에서 mypy 기동을 깨뜨려 `test_mypy.py` 2개 실패. ASCII 정리 + 파일 머리에 ASCII-only 재발방지 주석 (`mypy.ini:1-3`).
- ~~preview≠save wrap 회귀~~: `Operation.from_dict`가 `RedactReplace.wrap`을 복원하지 않아 렌더 워커(미리보기)가 교체별 줄바꿈/축소 선택을 무시. `wrap=data.get("wrap", None)` 전달 (`app/operations/base.py:61`). 재발 방지: op 4종 `to_dict→from_dict` round-trip 테스트 (`tests/test_op_serialization.py`).
- ~~렌더 비밀번호 평문 디스크 기록~~ (보안): 암호화 PDF 미리보기마다 비번이 temp의 평문 job JSON에 기록되던 것을 **stdin 파이프 1줄 프로토콜**로 전환(job 파일엔 `password_stdin` 플래그만). `DocumentSession.render_password()` 접근자 신설로 `_password` 캡슐화 (`app/viewer.py:149-186`, `app/render_worker.py:30-56`). 비암호화 경로 100% 불변. 221 tests pass.

### Added (2026-06-08, replace-wrap-toggle PDCA)

- **교체별 줄바꿈/축소 토글**: 선행 `text-wrap-replace`가 전역 상수(`TEXT_WRAP_ENABLED`)로만 제어하던 wrap-first 정책을 **교체 단위 사용자 선택**으로 노출. `RedactReplace`에 `wrap: Optional[bool]=None`(None=전역 따름 / True=줄바꿈 / False=폰트축소) 추가, `applicator._insert_text_with_autofit(wrap_enabled=...)`로 스레딩(기본값=`TEXT_WRAP_ENABLED`라 직접 호출 무영향). UI: `BatchReplaceDialog`에 "긴 텍스트 줄바꿈" 체크박스(기본 on) → `process_batch_replacements`가 `RedactReplace`로 전달. i18n `batch.use_wrap` 키. 100% 하위 호환. 195 tests pass.

### Added (2026-06-08, pdf-open-decrypt PDCA)

- **암호화 PDF 열기 + 보호 해제(복호화)**: 선행 `pdf-encryption`의 *짝*(쓰기 전용 반쪽 상태 해소). 암호화 PDF를 열면(드롭 포함) 비밀번호 프롬프트 + 오답 재시도, File → "Remove Protection (Decrypt)…"(Ctrl+Alt+D)로 평문 사본 저장. 엔진 경계 `open_document(path, password=)`가 `doc.needs_pass` 감지→인증, 실패 시 `PasswordRequired`/`IncorrectPassword`(둘 다 `EncryptedPDFError`, `app/encryption.py` strict) 발생. 세션이 `_password`/`is_encrypted` 단일 소유, 소스 재오픈 전 경로(`save_document_copy(password=)`, `render_page_preview(password=)`+render_worker job JSON, 저장 후 재바인드)에 스레딩. 저장 시 출력 보호 상태로 `is_encrypted` 재계산(암호화/복호화/평문). 복호화는 `_commit_save(encryption=None, decrypt=True)` 재사용(신규 저장 경로 없음). 컨트롤러는 Qt 비의존(예외만 전파), 프롬프트는 `file_handlers._load_with_password_prompt`(open/drop 공용). i18n `dialog.password.*`/`menu.file.remove_protection`/`status.decrypted`/`status.not_encrypted`. 100% 하위 호환, 매치율 100%, 208 tests pass. Known limit: 빈 사용자암호+소유자암호만 있는 파일은 프롬프트 없이 열려 `is_encrypted=False`.

### Added (2026-06-08, pdf-encryption PDCA)

- **Password protection + permissions**: New pure, mypy-strict `app/encryption.py` (`EncryptionSettings`) builds AES-256 `Document.save` kwargs (user/owner passwords + print/copy/modify/annotate permission bits) with an `is_active()` guard so an unprotected policy saves normally. Threaded through `pdf_engine.save_document_copy` → `document_session.save_document` → `controller.save_document` as an optional `encryption=` kwarg (100% backward compatible). After an encrypted save the session re-binds via `authenticate(unlock_password())`. UI: `app/encryption_dialog.py` + File → "Encrypt & Save As…" (Ctrl+Alt+S); shared save logic extracted to `file_handlers._commit_save`. Strict gate expanded to `app.encryption`. 191 tests pass.

### Added (2026-06-02, page-merge-split PDCA)

- **Document split + batch merge**: New `app/page_split.py` (pure, mypy-strict) provides `SplitMode` (SINGLE / EVERY_N / RANGES), `parse_page_ranges`, and `compute_split_groups`. `DocumentSession.split_document` writes one PDF per page-index group (read-only, source unchanged — same contract as `extract_pages`). `DocumentSession.merge_pdfs` inserts several PDFs in order; `merge_pdf` now delegates to it (backward-compatible). UI: `app/split_dialog.py` + a "Split" action in `PageManagerDialog`; merge now accepts multiple files. 177 tests pass.

### Resolved (2026-06-02, text-wrap-replace PDCA)

- ~~Long text shrunk to unreadable size / dropped~~: Replacement text that overflows one line now **word-wraps onto multiple lines** by expanding the box height within the page bound, preserving the intended font size. Font shrinking is now a fallback only for unbreakable words wider than the box or insufficient vertical room. New `text.wrapped` (info) warning surfaces in status bar + history badge. Controlled by `TEXT_WRAP_*` constants in `app/config.py`; core logic in `app/operations/applicator.py::_wrap_line_count` + `_insert_text_with_autofit`. 146 tests pass.

### Resolved (2026-06-02, r2-quality-fixes PDCA)

- ~~`get_text_length` API broken~~: PyMuPDF 1.26+ removed `Page.get_text_length`; replaced with `fitz.Font.text_length()` in `app/operations/applicator.py`. Recovered 11 failing tests.
- ~~autofit shrink warning gap~~: autofit-driven font shrink now emits `text.shrunk` (previously only the fallback path did).
- ~~mypy strict scope too narrow~~: gate expanded to `config`, `logger`, `path_helper`, `text_utils`, `text_metadata`, `fonts` (all 0 strict errors), enforced by `tests/test_mypy.py::test_strict_leaf_modules_pass_mypy`. Deferred: `document_session`, `model`, `pdf_engine` → `typing-legacy-core` cycle.

### Risks

- Packaging with PyInstaller: Relative path/data bundling not yet tested
- Memory usage: Large section removal with high DPI - mitigated via auto-cap, monitor logs
- Save-time operation application is synchronous on the UI thread (all ops, incl. high-DPI RemoveSection) — a save with heavy pending ops can block the UI for seconds. Async save (worker + session rebind) is a candidate for a future cycle. (noted 2026-06-11, r7-history-policy)

---

## PDCA Document Structure

### Current Status

- bkit-standard PDCA docs in use under `docs/` (see Target Structure below)
- Legacy root documents (`PROJECT_STATUS.md`, `IMPROVEMENT_PLAN.md`, `NEXT_STEPS.md`)
  were deprecated stubs; archived to `docs/archive/legacy-root/` (2026-06-10, r5-infra)

### Target Structure

```
docs/
├── _INDEX.md                # Document index
├── 01-plan/
│   └── features/
│       └── {feature}.plan.md
├── 02-design/
│   └── features/
│       └── {feature}.design.md
├── 03-analysis/
│   └── features/
│       └── {feature}.analysis.md
└── 04-report/
    └── features/
        └── {feature}.report.md
```

---

## Language & i18n

### Supported Languages

- English (en)
- Korean (ko)

### i18n Rules

- All UI strings must use i18n keys
- Translation files: `app/i18n/en.json`, `app/i18n/ko.json`
- Validation: Check for missing keys, placeholder mismatches

---

## Logging

### Log Levels

- **DEBUG**: Detailed flow (font size calculation, operations)
- **INFO**: User actions (open, save, replace)
- **WARNING**: Non-critical issues (text scaling, preview mismatch)
- **ERROR**: Critical failures (save error, render crash)

### Log Location

- `logs/` directory
- Timestamped files for each session

---

## Version Control

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Example:

```
feat: Add fixed font size option for text replacement

- Add checkbox in Replace dialog for fixed font size
- Prevent auto-scaling when option is enabled
- Update i18n strings for new option

Closes #12
```

---

## Next Development Phases

Based on current status and improvement plan:

1. **Phase 1: Immediate Fixes** (Priority: High)
   - Fix config default pollution (deep copy)
   - Close preview temp documents properly
   - Add memory guards for RemoveSection

2. **Phase 2: Core Refactor** (Priority: High)
   - Unify preview-save logic
   - Extract operation application to pure function
   - Add operation validation

3. **Phase 3: UX Enhancement** (Priority: Medium)
   - Add fixed font size option
   - Improve status messages
   - Enhance history panel

4. **Phase 4: Testing & i18n** (Priority: Medium)
   - Add preview=save equivalence tests
   - Create i18n validation script
   - Add long text/narrow area tests

5. **Phase 5: Packaging** (Priority: Low)
   - Create PyInstaller spec
   - Add path helpers for frozen/unfrozen
   - Separate build requirements

---

## References

### External Documentation

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)

### Internal Documents

- `docs/03-analysis/features/current-state.analysis.md`: Current status
- `docs/01-plan/features/improvement.plan.md`: Improvement roadmap
- `docs/01-plan/features/next-steps.plan.md`: Next action items
- `docs/archive/legacy-root/`: archived pre-PDCA root documents

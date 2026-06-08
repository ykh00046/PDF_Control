# Plan: text-export

> **Feature**: PDF 텍스트 내보내기 (txt / md)
> **Project**: PDF Control (Starter / PySide6 + PyMuPDF)
> **Date**: 2026-06-02
> **Status**: ✅ Approved
> **PDCA Phase**: Plan

---

## 1. 목적 (Why)

사용자가 PDF의 텍스트를 외부 편집기/문서에서 재사용할 수 있도록, 페이지 단위 또는
문서 전체의 텍스트를 `.txt` 또는 `.md` 파일로 내보내는 기능을 추가한다.

`page-advanced-ops` 리포트(§6.3)에서 후속 우선순위 3번으로 식별된 항목이며,
구현 난이도 대비 사용자 가치(ROI)가 가장 높은 기능으로 평가되었다.

---

## 2. 범위 (Scope)

### In Scope

- 텍스트 추출 범위 선택: **전체 문서 / 현재 페이지** (scope 라디오)
- 출력 형식: **txt**(일반 텍스트), **md**(페이지별 `## Page N` 헤더)
- UI: Tools 메뉴 진입점(Ctrl+Shift+T) + 내보내기 옵션 다이얼로그 + 저장 경로 선택 다이얼로그
- PyMuPDF `page.get_text("text")` 기반 추출
- i18n(en/ko) 전체 적용
- 원본 변경 없음(read-only), 따라서 undo/redo 비대상

### Out of Scope (향후 확장)

- **페이지 범위 문자열 입력(`1,3,5-7`)** — 후속 사이클 `text-export-range`로 분리.
  엔진 레벨(`extract_text(page_indices, fmt)`)은 이미 임의 인덱스 리스트를 지원하므로
  다이얼로그에 입력 위젯 + 파서만 추가하면 됨.
- OCR(스캔 PDF 이미지 텍스트 인식) — 별도 사이클(`ocr-integration`)
- 표/레이아웃 보존 추출(HTML/JSON 등)
- 폰트/스타일 메타데이터 포함 내보내기

---

## 3. 기존 코드 재사용 전략 (DRY)

`page-advanced-ops`의 **extract_pages** 경로를 그대로 미러링한다:

| 레이어 | 기존 참조 | 신규 (as-built) |
|--------|-----------|------|
| 순수 로직 | (신규) | `app/text_export.py` — Qt 비의존 순수 함수 (`extract_text`/`export_text_to_file`) |
| Session | `DocumentSession.extract_pages` | `DocumentSession.extract_text` + `export_text` (thin delegate) |
| Controller | `EditorController.extract_pages` (emit 생략) | `EditorController.export_text` (emit 생략) |
| Dialog | `crop_dialog` 컨벤션(설정만 emit, 저장은 caller) | `app/text_export_dialog.py` (`TextExportDialog`) |
| Handler | `DialogHandlerMixin.open_*_dialog` | `open_text_export_dialog` + `apply_text_export` |
| Menu | `MenuBuilder._build_tools_menu` | Tools 메뉴에 `Export Text...`(Ctrl+Shift+T) 추가 |

읽기 전용 작업이므로 `extract_pages`와 동일하게 `operation_applied`를 emit하지 않는다.

---

## 4. Acceptance Criteria

| # | 기준 | 검증 방법 |
|---|------|-----------|
| AC1 | 전체 문서 텍스트를 txt로 내보내면 모든 페이지 텍스트가 포함된다 | 단위 테스트 |
| AC2 | 현재 페이지만 내보내면 해당 페이지 텍스트만 포함된다 | 단위 테스트 |
| AC3 | md 형식은 각 페이지에 `## Page N` 헤더가 붙고 txt에는 헤더가 없다 | 단위 테스트 |
| AC4 | 지원하지 않는 형식/빈 경로/없는 디렉터리/범위 초과 인덱스는 명시적 예외 | 단위 테스트 |
| AC5 | 원본 PDF 경로로 덮어쓰기를 차단한다 | 단위 테스트 |
| AC6 | 내보내기는 원본을 변경하지 않는다(`modified` 불변, 페이지 수 불변) | 단위 테스트 |
| AC7 | `export_text`는 기록한 문자 수를 반환한다 | 단위 테스트 |
| AC8 | Tools 메뉴에 "Export Text..." 진입점이 존재한다 (Ctrl+Shift+T) | 코드 검토 |
| AC9 | 문서 미오픈 시 상태바 안내 후 무동작 | 코드 검토 |
| AC10 | i18n 키가 en/ko에 동일하게 추가되고 플레이스홀더 일치 | i18n 검증 테스트 |

목표 Acceptance 충족률: **100% (10/10)**

---

## 5. 예상 산출물

- 신규: `app/text_export.py`, `app/text_export_dialog.py`, `tests/test_text_export.py`
- 수정: `app/document_session.py`, `app/controller.py`, `app/handlers/dialog_handlers.py`,
  `app/ui_menu.py`, `app/i18n/en.json`, `app/i18n/ko.json`, `CHANGELOG.md`, `docs/_INDEX.md`
- 신규 단위 테스트: 14개 (추출 6 + 파일 출력 6 + 엔진 견고성 2)

---

## 6. 리스크 & 대응

| 리스크 | 대응 |
|--------|------|
| 빈 페이지/이미지 전용 페이지 → 빈 문자열 | 빈 결과도 정상 파일로 저장(md 헤더는 유지) |
| 잘못된 인덱스/형식 | `resolve_indices`(IndexError) + `build_text`(ValueError)로 명시적 차단 |
| 인코딩 깨짐 | UTF-8 + `newline="\n"` 고정 |

---

## Related Documents

- Design: [text-export.design.md](../../02-design/features/text-export.design.md)
- Analysis: [text-export.analysis.md](../../03-analysis/features/text-export.analysis.md)
- Report: [text-export.report.md](../../04-report/features/text-export.report.md)
- 선행: [page-advanced-ops.report.md](../../04-report/features/page-advanced-ops.report.md)

## Version History

| Version | Date       | Changes       | Author        |
| ------- | ---------- | ------------- | ------------- |
| 1.0     | 2026-06-02 | Initial plan  | Claude (bkit) |

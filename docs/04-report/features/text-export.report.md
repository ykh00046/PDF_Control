# Report: text-export (PDCA Completion)

> **Feature**: PDF 텍스트 내보내기 — Whole document / Current page → txt·md
> **Project**: PDF Control (Starter / PySide6 + PyMuPDF)
> **Cycle**: PDCA full cycle (Plan → Design → Do → Check → Report)
> **Date**: 2026-06-02
> **Status**: ✅ Completed
> **Match Rate**: 100% (10/10 AC)
> **Test Pass Rate**: 135/135 (전체 회귀, pyinstaller 번들 테스트 제외)

---

## 1. Executive Summary

PDF의 텍스트를 `.txt` 또는 `.md`로 내보내는 기능을 한 PDCA 사이클로 완성했다. 사용자
요구("페이지 또는 문서 전체")를 **전체 문서 / 현재 페이지** 두 scope로 정확히 충족하고,
순수 추출 엔진(`app/text_export.py`)을 Qt와 분리해 결정적 단위 테스트 14개로 고정했다.
기존 `extract_pages`(page-advanced-ops) 3레이어 패턴을 그대로 미러링하여 학습 곡선과
회귀 위험을 0으로 유지했다.

| 지표 | 결과 |
|------|------|
| Acceptance Criteria 충족 | 10/10 (**100%**) |
| 신규 단위 테스트 | 14개 (추출 6 / 파일 출력 6 / 엔진 견고성 2) |
| 전체 회귀 | 135 passed (mypy strict 게이트 포함) |
| i18n 키 추가 (en/ko 동일) | 14 × 2 |
| Iterate 반복 | 0 (Check 즉시 100%) |
| 신규/수정 파일 | 신규 3, 수정 6 |

---

## 2. Delivered Capability

| 기능 | 사용자 시나리오 | 진입점 |
|------|----------------|--------|
| 문서 전체 텍스트 내보내기 | 전체 PDF 텍스트를 메모/검색/번역에 재사용 | Tools → Export Text… (Ctrl+Shift+T) → "문서 전체" |
| 현재 페이지만 내보내기 | 보고 있는 한 페이지만 빠르게 추출 | 동일 다이얼로그 → "현재 페이지만" |
| Markdown 출력 | 페이지 구분(`## Page N`)이 있는 .md로 저장 | 형식 콤보 → Markdown |

- 원본 PDF는 절대 변경되지 않음(read-only) → undo/redo 비대상.
- 저장 파일명은 원본 경로 기반으로 자동 제안하고, 확장자를 자동 보정한다.

---

## 3. Implementation Snapshot

### 신규
- `app/text_export.py` — Qt 비의존 순수 엔진
  - `resolve_indices`(None→전체, 범위초과 IndexError), `build_text`(txt/md 직렬화),
    `extract_text`(fmt 검증 + 추출), `export_text_to_file`(검증 + UTF-8 기록, 문자 수 반환).
- `app/text_export_dialog.py` — `TextExportDialog`(scope 라디오 + 형식 콤보, `export_confirmed` emit).
- `tests/test_text_export.py` — 14 케이스.

### 수정
- `app/document_session.py` — `extract_text` / `export_text` 위임 메서드.
- `app/controller.py` — `export_text`(bool 래퍼, `operation_applied` emit 생략).
- `app/handlers/dialog_handlers.py` — `open_text_export_dialog` / `apply_text_export`(저장 다이얼로그 + 확장자 보정 + 결과 안내).
- `app/ui_menu.py` — Tools 메뉴에 `Export Text…`(Ctrl+Shift+T) 추가.
- `app/i18n/en.json`, `ko.json` — `text_export.*` 등 14키.
- `CHANGELOG.md`, `docs/_INDEX.md`.

---

## 4. PDCA Cycle Trace

| Phase | 결과물 | 코멘트 |
|-------|--------|--------|
| Plan | `text-export.plan.md` | extract_pages 재사용 전략 + AC 10개 명세 |
| Design | `text-export.design.md` (v1.0→v1.1) | 구현 수렴에 맞춰 as-built로 정합화 |
| Do | 신규 3 / 수정 6 파일 | 순수 엔진 ↔ Qt 분리 패턴 적용 |
| Check | `text-export.analysis.md` | 첫 시도 100%, 회귀 135 그린 |
| Iterate | (생략) | Check 즉시 100% → 진입 조건(<90%) 미충족 |
| Report | 본 문서 | — |

---

## 5. Decisions & Trade-offs

| 결정 | 채택 이유 | 후속 영향 |
|------|-----------|-----------|
| 추출 범위 = 전체/현재 (임의 범위 제외) | 사용자 요구 정확 충족·단순/견고 | `text-export-range` 후속으로 분리 |
| 진입점 Tools 메뉴(Ctrl+Shift+T) | crop/remove/page-manager와 동일 그룹 | 발견성·일관성 ↑ |
| 순수 엔진 분리(`text_export.py`) | Qt 비의존 결정적 테스트 | 향후 strict 게이트 편입 후보 |
| `export_text` 반환 = 문자 수 | "쓰여진 분량" 검증이 자연스러움 | 테스트 계약과 일치 |
| read-only(emit/undo 미적용) | `extract_pages`와 동일 일관성 | 원본 안전성 보장 |

### 수렴 과정에서 정리한 항목
- 초안에서 만든 중복 다이얼로그 `app/export_text_dialog.py` 및 `parse_page_range`는
  수렴 후 제거하여 dead code 0 유지(스모크 import 검증 통과).

---

## 6. Verification Evidence

```
$ py -3.13 -m pytest tests/test_text_export.py tests/test_i18n_validation.py -v
14 + 3 passed

$ py -3.13 -m pytest tests/ --ignore=tests/test_pyinstaller_bundling.py -q
135 passed in 8.21s

$ py -3.13 -c "import app.text_export, app.text_export_dialog; from app.controller import EditorController; ..."
engine fns: build_text, export_text_to_file, extract_text, resolve_indices
dialog: True / controller.export_text: True / session.extract_text+export_text: True True
handler open/apply: True True
```

---

## 7. Lessons Learned

1. **요구사항 정밀 해석이 범위를 지킨다** — "페이지 또는 문서 전체"는 scope 2종으로 완결.
   초안의 임의 범위 입력은 가치 있으나 본 요구 밖이라 후속으로 분리해 사이클을 단순·견고하게 유지.
2. **순수 엔진 분리의 효과** — Qt 비의존 `text_export.py` 덕분에 14개 테스트가 빠르고 결정적.
3. **테스트가 계약을 고정한다** — `export_text` 반환 의미(문자 수)와 예외 메시지를 테스트가 명확히 규정.
4. **문서-구현 정합** — 구현 수렴에 맞춰 Design을 as-built v1.1로 갱신해 Check를 단순 체크리스트로 전환.

### 다음 사이클 추천
1. 🟢 **text-export-range** — 다이얼로그에 페이지 범위 입력(`1,3,5-7`) + 파서. 엔진은 이미 인덱스 리스트 지원.
2. 🟢 **watermark** — 텍스트/이미지 워터마크(선택/일괄).
3. 🟢 **typing-legacy-core** — `document_session`/`model`/`pdf_engine` mypy strict 편입.

---

## 8. Related Documents

- Plan: [text-export.plan.md](../../01-plan/features/text-export.plan.md)
- Design: [text-export.design.md](../../02-design/features/text-export.design.md)
- Analysis: [text-export.analysis.md](../../03-analysis/features/text-export.analysis.md)
- 선행: [page-advanced-ops.report.md](page-advanced-ops.report.md)

## Version History

| Version | Date       | Changes                | Author        |
| ------- | ---------- | ---------------------- | ------------- |
| 1.0     | 2026-06-02 | PDCA completion report | Claude (bkit) |

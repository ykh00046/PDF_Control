# Analysis: text-export (Gap Analysis / Check)

> **Feature**: PDF 텍스트 내보내기 (txt / md)
> **Project**: PDF Control (Starter / PySide6 + PyMuPDF)
> **Date**: 2026-06-02
> **Status**: ✅ Approved
> **PDCA Phase**: Check
> **Match Rate**: **100% (10/10 AC)**

---

## 1. 요약

설계(as-built v1.1) 대비 구현 일치도를 검증했다. 구현 도중 사용자 요구("페이지 또는
문서 전체")를 정확히 충족하는 scope 방식으로 수렴하고 문서를 as-built로 정합화했으므로,
설계-구현 간 격차는 없다. 전체 회귀 **135 passed**(mypy 게이트 포함), 신규 텍스트 내보내기
단위 테스트 **14개** 모두 통과.

---

## 2. Acceptance Criteria 충족 매트릭스

| # | 기준 | 상태 | 근거 |
|---|------|:----:|------|
| AC1 | 전체 문서 txt에 모든 페이지 텍스트 포함 | ✅ | `test_whole_document_txt` |
| AC2 | 현재 페이지만 추출 시 해당 페이지만 | ✅ | `test_current_page_only` |
| AC3 | md는 `## Page N` 헤더, txt는 헤더 없음 | ✅ | `test_markdown_has_page_headings`, `test_txt_has_no_markdown_headers` |
| AC4 | 미지원 fmt/빈 경로/없는 디렉터리/범위초과 예외 | ✅ | `test_invalid_format_raises`, `test_empty_path_raises`, `test_nonexistent_dir_raises`, `test_out_of_range_index_raises` |
| AC5 | 원본 PDF 덮어쓰기 차단 | ✅ | `test_overwrite_source_blocked` |
| AC6 | 내보내기는 원본 무변경(`modified`/페이지 수 불변) | ✅ | `test_source_document_unchanged` |
| AC7 | `export_text`는 기록 문자 수 반환 | ✅ | `test_writes_txt_file`, `test_char_count_matches_written_file` |
| AC8 | Tools 메뉴 "Export Text..." (Ctrl+Shift+T) | ✅ | `app/ui_menu.py:138-141` |
| AC9 | 문서 미오픈 시 상태바 안내 후 무동작 | ✅ | `dialog_handlers.py:open_text_export_dialog` 가드 |
| AC10 | i18n en/ko 동일 키 + 플레이스홀더 일치 | ✅ | `test_i18n_validation.py` 3/3 |

**충족률: 10/10 = 100%** → Iterate(자동 개선) 진입 조건(<90%) 미충족, 생략.

---

## 3. 설계 항목별 구현 대조

| 설계 항목 | 구현 위치 | 일치 |
|-----------|-----------|:----:|
| `text_export.resolve_indices/build_text/extract_text/export_text_to_file` | `app/text_export.py` | ✅ |
| `DocumentSession.extract_text` / `export_text` | `app/document_session.py:290-316` | ✅ |
| `EditorController.export_text` (emit 생략) | `app/controller.py:203-213` | ✅ |
| `TextExportDialog` (scope+fmt, export_confirmed) | `app/text_export_dialog.py` | ✅ |
| `open_text_export_dialog` / `apply_text_export` | `app/handlers/dialog_handlers.py:263-315` | ✅ |
| Tools 메뉴 진입점(Ctrl+Shift+T) | `app/ui_menu.py:138-141` | ✅ |
| i18n `text_export.*` (en/ko) | `app/i18n/en.json`, `ko.json` | ✅ |

격차 항목: **없음**.

---

## 4. 구현 중 의사결정(설계 수렴) 기록

| 사항 | 초안(v1.0) | 최종(as-built v1.1) | 사유 |
|------|-----------|--------------------|------|
| 추출 범위 | 전체/현재/임의범위(`1,3,5-7`) | 전체/현재 | 사용자 요구 정확 충족·단순/견고, 범위는 향후 분리 |
| 진입점 | File 메뉴 Ctrl+E | Tools 메뉴 Ctrl+Shift+T | crop/remove/page-manager와 동일 그룹 일관성 |
| `export_text` 반환 | 페이지 수 | 문자 수 | 호출부 "쓰여진 분량" 검증이 자연스러움(테스트 계약) |
| 다이얼로그 책임 | 인덱스 직접 해석 | scope만 emit, 해석은 handler | crop/remove 다이얼로그 관례 일치 |

> 초안에서 만들었던 `parse_page_range`/`export_text_dialog.py`(중복 다이얼로그)는 수렴
> 과정에서 제거했다. 임의 페이지 범위는 기존 `app/text_utils.py`에 이미 유사 파서가 있어
> 향후 `text-export-range` 사이클에서 재사용 가능하다.

---

## 5. 품질 게이트

| 게이트 | 결과 |
|--------|------|
| 전체 회귀(pyinstaller 제외) | **135 passed** |
| 신규 text-export 단위 테스트 | **14 passed** |
| i18n 검증 | **3 passed** (키/플레이스홀더 일치) |
| mypy strict leaf 게이트 | passed (`test_mypy.py` 회귀 내 포함) |
| 잔여 dead code / 깨진 참조 | 없음(고아 다이얼로그 삭제 확인) |

---

## 6. 결론

설계-구현 일치율 **100%**, 전체 그린. **Iterate 불필요**, Report 단계로 진행.

---

## Related Documents

- Plan: [text-export.plan.md](../../01-plan/features/text-export.plan.md)
- Design: [text-export.design.md](../../02-design/features/text-export.design.md)
- Report: [text-export.report.md](../../04-report/features/text-export.report.md)

## Version History

| Version | Date       | Changes          | Author        |
| ------- | ---------- | ---------------- | ------------- |
| 1.0     | 2026-06-02 | Gap analysis 100%| Claude (bkit) |

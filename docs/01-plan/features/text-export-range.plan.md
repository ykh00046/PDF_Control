# Text Export Range - Plan (design integrated)

> **Summary**: 텍스트 내보내기의 "페이지 범위" 옵션 완성 — 다이얼로그에 range 라디오·입력란·i18n은 이미 있으나 `get_settings()`가 range를 무시해 **현재 페이지만 내보내지던 끊긴 기능**을 연결. 기존 `parse_page_ranges`(page-merge-split) 재사용
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%, 287 passed)
> **Cycle**: text-export-range

---

## 1. 배경 (Why)

`TextExportDialog`는 이미 "페이지 범위" 라디오(`scope_range`) + 입력란(`range_edit`, placeholder) + i18n 키(`text_export.scope.range`, `text_export.range.placeholder`)를 갖고 있다. 그러나:

- `get_settings()`(text_export_dialog.py:88-93)는 `scope`를 `"all"`/`"current"`로만 반환하고 `range_edit` 값을 **읽지 않는다** — 사용자가 범위를 선택·입력해도 `"current"`로 떨어져 **현재 페이지만 내보내진다**(조용한 오동작). docstring(L31-32)은 `{"scope": "all"|"current"|"range", "range"}`를 약속하지만 구현 미완.
- `apply_text_export`(dialog_handlers.py:284-295)도 `scope == "current"` / else(전체)만 처리, range 분기 없음.

백엔드는 이미 완비: `resolve_indices`(text_export.py:23-36)가 임의 page_indices를 정렬·중복제거하고, `parse_page_ranges`(page_split.py:22-70)가 `"3-7, 10"` → 0-based 그룹을 파싱하며, `controller.export_text(page_indices=)`가 그대로 전달한다. **UI/핸들러 연결만 빠진 상태** — save-integrity와 같은 "끊긴 연결" 패턴.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `TextExportDialog.get_settings()` 완성 — 3-scope(`all`/`current`/`range`) + `range` 문자열 반환. range 선택 시 입력란 값 포함.
- **M2**: `apply_text_export`에 range 분기 — `scope == "range"`면 `parse_page_ranges(spec, page_count)` 결과를 평탄화해 `page_indices`로(`resolve_indices`가 정렬·중복제거). `ValueError`(빈/잘못된/범위초과 spec) → 에러 메시지 표시, 내보내기 중단. `parse_page_ranges` 재사용(DRY — 신규 파서 금지).
- **M3**: i18n `text_export.range.invalid` 에러 키(en/ko). 누락 0.
- **M4**: 테스트 — get_settings 3-scope 반환(다이얼로그 스모크), range spec 파싱→평탄화→export 통합(`"1-2, 4"` → 해당 페이지만), 잘못된 range → ValueError 처리.

### 권장 (Should)

- **S1**: 빈 range 입력 + range 선택 시 친절한 에러(빈 spec도 `parse_page_ranges`가 ValueError).

### 범위 외 (Won't)

- range 입력 자동완성/미리보기 — 단순 텍스트 입력 유지.
- export 순서를 입력 순서로(예: "5,3" → 5페이지 먼저) — `resolve_indices`가 정렬하므로 문서 순서 유지(텍스트 추출엔 문서 순서가 자연스러움). 의도된 동작.
- watermark 등 다른 기능의 범위 지정 — 별도.

## 3. 설계 (Design)

**text_export_dialog.py `get_settings`**:
```python
def get_settings(self) -> dict:
    if self.scope_all.isChecked():
        scope = "all"
    elif self.scope_range.isChecked():
        scope = "range"
    else:
        scope = "current"
    return {
        "scope": scope,
        "fmt": self.format_combo.currentData(),
        "range": self.range_edit.text(),
    }
```

**dialog_handlers.py `apply_text_export`** — fmt 결정 전, scope 분기:
```python
from app.page_split import parse_page_ranges
...
scope = settings.get("scope")
if scope == "current":
    page_indices = [self.viewer.current_page_index]
elif scope == "range":
    try:
        groups = parse_page_ranges(
            settings.get("range", ""), self.controller.session.doc.page_count
        )
    except ValueError as e:
        self.logger.warning(f"Invalid export range: {e}")
        QMessageBox.warning(self, tr("dialog.error"), tr("text_export.range.invalid"))
        return
    page_indices = [i for group in groups for i in group]
else:
    page_indices = None  # whole document
```
(이후 경로 불변: fmt/파일다이얼로그/`controller.export_text(output_path, page_indices, fmt)`.)

- 평탄화된 indices는 중복/순서 무관 — `resolve_indices`(controller→session→export_text)가 sorted+dedup.

## 4. 성공 기준 (Acceptance)

- [ ] 전체 테스트 281+ 통과.
- [ ] get_settings가 range 선택 시 `scope="range"` + range 문자열 반환.
- [ ] `"1-2, 4"` 범위 → 해당 페이지 텍스트만 내보내짐(다른 페이지 제외).
- [ ] 잘못된 범위 → 에러 표시, export 안 함(예외 0).
- [ ] i18n en/ko 동수.
- [ ] mypy strict(page_split·text_export 게이트) 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 5. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/text_export_dialog.py` | `get_settings` 3-scope + range |
| `app/handlers/dialog_handlers.py` | `apply_text_export` range 분기 |
| `app/i18n/en.json`, `ko.json` | `text_export.range.invalid` |
| `tests/test_text_export.py` | range 파싱→export 통합, 잘못된 범위 |
| `tests/test_save_busy.py`류 다이얼로그 스모크 또는 신규 | get_settings 3-scope |

## 6. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 신규 파서 중복 작성(DRY 위반) | `parse_page_ranges` 재사용 명시 |
| 평탄화 시 순서/중복 | `resolve_indices`가 정렬·중복제거(기존 검증된 동작) |
| range 입력 에러로 크래시 | `ValueError` catch → 사용자 메시지, 중단 |
| 1-based↔0-based 혼동 | `parse_page_ranges`가 1-based→0-based 변환(검증된 함수) |

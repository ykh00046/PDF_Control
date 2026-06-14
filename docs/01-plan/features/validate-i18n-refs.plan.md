# Validate i18n Refs - Plan + Report (small infra cycle)

> **Summary**: i18n 검증에 "tr() 참조 키 존재" 검사를 추가해, en/ko **양쪽에 없는** 키를 못 잡던 공백을 폐쇄. 측정 중 실재 누락 5개(remove_section_dialog) + 죽은 fallback 관용구 발견·수정. 매치율 100%, **295 passed**
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-15
> **Status**: ✅ Completed (2026-06-15, 매치율 100%)
> **Cycle**: validate-i18n-refs

---

## 1. 배경 (Why)

text-export-range에서 발견: `validate_i18n`이 en/ko **키 동수**만 검사해, `tr()`로 참조하지만 **양쪽 다 없는** 키를 못 잡았다. `i18n.py tr()`는 `_translations.get(key, key)` — 키 없으면 키 문자열을 반환하므로, 누락 시 UI에 raw 키가 그대로 노출된다.

### 측정으로 드러난 실재 버그 (probe)

app/에서 static `tr("literal")` 키 299개를 추출해 en/ko 대조 → **5개가 양쪽 모두 누락**: `remove.precision.title`, `remove.info.y0`, `remove.info.y1`, `remove.snap.top`, `remove.snap.bottom` (전부 `remove_section_dialog.py`). 게다가 그 사용처가 `tr("X") if "X" in tr("X") else "fallback"`라는 **깨진 관용구** — tr이 키를 반환하니 `"X" in "X"`는 항상 True → fallback은 죽은 코드, **UI에 "remove.precision.title" 같은 키 문자열이 그대로 표시**되고 있었다.

## 2. 한 일 (What)

- **검증 도구**: `validate_i18n.py`에 `extract_tr_keys(source_dir)`(정규식 `tr\(\s*["']([^"'{}]+)["']` — 정적 리터럴만, f-string/`{}` 동적 키는 false positive 방지 위해 제외) + `validate_tr_references(...)`(추출 키가 en/ko에 없으면 에러). `validate()` 본 경로 + `test_all_tr_keys_exist` 테스트 양쪽 통합.
- **버그 수정**: 5개 깨진 관용구를 평이한 `tr("X")`로 단순화, 5개 키를 en/ko에 추가(en: Precision Adjustment / Top (Y0) / Bottom (Y1) / To Top / To Bottom, ko: 정밀 조정 / 상단 (Y0) / 하단 (Y1) / 맨 위로 / 맨 아래로).

## 3. 검증 (Acceptance — 전부 충족)

- [x] 전체 테스트 **295 passed** (+1 신규 `test_all_tr_keys_exist`).
- [x] app/ static tr() 키 전부 en+ko 존재(누락 0).
- [x] `if X in tr(X)` 관용구 app/ 전역 0건.
- [x] ruff 0 위반, i18n 314/314 패리티.
- [x] Gap 분석 매치율 100% (5/5 체크).

## 4. 영향 범위

| 파일 | 변경 |
|---|---|
| `tests/validate_i18n.py` | `extract_tr_keys` + `validate_tr_references` + validate() 통합 |
| `tests/test_i18n_validation.py` | `test_all_tr_keys_exist` 신규 |
| `app/remove_section_dialog.py` | 5개 관용구 → `tr()` 단순화 |
| `app/i18n/en.json`, `ko.json` | 5개 키 추가 |

## 5. 한계 (의도)

- 동적 키(f-string/`{}` 보간)는 정적 검증 불가 — false positive로 빌드를 깨지 않는 lower-bound 선택. 향후 동적 키 도입 시 `{}` 제외절이 자동 보호.

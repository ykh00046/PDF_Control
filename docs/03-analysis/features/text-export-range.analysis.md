# Text Export Range - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (M1-M4 + S1), 5개 플래그 안전, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-14
> **Plan(design integrated)**: [text-export-range.plan.md](../../01-plan/features/text-export-range.plan.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 get_settings 3-scope + range | `text_export_dialog.py:94-104` | ✅ |
| M2 range 분기 + parse_page_ranges 재사용 + ValueError 중단 | `dialog_handlers.py:295-310` | ✅ |
| M2 current/whole-document 경로 불변 | `dialog_handlers.py:293-294, 311-312` | ✅ |
| M3 누락이던 scope.range/range.placeholder + 신규 range.invalid (en/ko) | `en/ko.json:286-288` | ✅ |
| M4 TestExportRange + TestExportDialogSettings | `test_text_export.py:112-188` | ✅ |
| S1 빈/잘못된 range 친절한 에러 | `dialog_handlers.py:303-308` | ✅ |

## 플래그 점검 (전부 안전)

- **(a) 기존 경로 불변** — current=[idx], else=None. range는 elif 삽입.
- **(b) parse_page_ranges 재사용** — 신규 파서 0, page_split 직접 호출.
- **(c) 잘못된 range 깨끗이 중단** — ValueError catch → 경고 메시지 + return, export 미수행.
- **(d) 누락 i18n 키 양쪽 복구** — scope.range/range.placeholder/range.invalid 모두 en+ko, 296/296.
- **(e) flatten + resolve_indices** — 평탄화 후 sorted+dedup, 비인접/중복 테스트로 검증.

## 검증

- 전체 **287 passed** (281 + 6), i18n 296/296.
- 차이: 누락 0, 무단 변경 0. 함수 내 지연 import는 모듈 기존 관례 일치.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.

# Replace Wrap Toggle - Gap Analysis

> **Design**: `docs/02-design/features/replace-wrap-toggle.design.md`
> **Analyzed**: 2026-06-08
> **Method**: 설계 항목 ↔ 구현 코드 1:1 대조 + 테스트 검증

---

## 1. 설계 항목 대조

| # | 설계 항목 | 구현 위치 | 상태 |
|---|---|---|---|
| 2.1 | `RedactReplace.wrap: Optional[bool]=None` 필드 | `redact.py:32,40` | ✅ |
| 2.1 | `to_dict`에 `wrap` 키 | `redact.py:57` | ✅ |
| 2.2a | op→wrap 해석(None=전역) | `applicator.py` `_insert_replacement_text` | ✅ |
| 2.2b | `_insert_text_with_autofit(wrap_enabled=...)` 시그니처 | `applicator.py` (기본값 `TEXT_WRAP_ENABLED`) | ✅ |
| 2.2c | 내부 분기 `if TEXT_WRAP_ENABLED` → `if wrap_enabled` | `applicator.py` | ✅ |
| 2.3 | `use_wrap_checkbox` (기본 체크) + 툴팁 | `batch_replace_dialog.py` `_setup_ui` | ✅ |
| 2.3 | emit dict에 `wrap` 포함 | `batch_replace_dialog.py` `_confirm_replacements` | ✅ |
| 2.4 | 핸들러 `wrap` 전달 | `dialog_handlers.py` `process_batch_replacements` | ✅ |
| 2.5 | i18n `batch.use_wrap`, `.tooltip` (en/ko) | `en.json:144-145`, `ko.json:144-145` | ✅ |

## 2. 테스트 대조

| 설계 테스트 | 구현 | 결과 |
|---|---|---|
| `test_wrap_false_forces_shrink` | ✅ | pass |
| `test_wrap_true_multiline` | ✅ | pass |
| `test_wrap_none_follows_global` | ✅ (global ON/OFF 양쪽) | pass |
| `test_redact_replace_wrap_to_dict` | ✅ (True/False/None) | pass |

## 3. 성공 기준 충족

- [x] 기존 전체 테스트 통과 유지 (191 → **195 passed**, 회귀 0)
- [x] wrap=False → 폰트 축소(`text.shrunk`)
- [x] wrap=True → 다중 라인(`text.wrapped`)
- [x] wrap=None → 전역 `TEXT_WRAP_ENABLED` 따름
- [x] i18n 검증 통과 (`test_i18n_validation` 전체 스위트 포함)
- [x] mypy strict 통과 (`test_mypy` 전체 스위트 포함)

## 4. 매치율

**구현 항목 9/9, 테스트 4/4, 성공 기준 6/6 → 매치율 100%**

미해결 Gap 없음. PDCA 규칙상 매치율 ≥ 90% → **iterate(Act) 단계 불필요(스킵)**, Report로 진행.

## 5. 정직성 노트

- 단일 선택 교체(`replace_selection`)는 설계상 **명시적 범위 외**(단순 입력 프롬프트라 옵션 UI 없음). `wrap=None` 기본값으로 전역 동작 유지 — 누락이 아닌 의도된 결정.
- `.pytest_cache` 쓰기 권한 경고는 환경(읽기전용 경로) 이슈로 기능과 무관.

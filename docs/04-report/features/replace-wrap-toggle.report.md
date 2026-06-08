# Replace Wrap Toggle - Completion Report

> **Cycle**: replace-wrap-toggle
> **Completed**: 2026-06-08
> **Status**: ✅ Completed (Match Rate 100%)
> **Result**: 195 passed (191 → 195, 회귀 0)

---

## 1. 요약

선행 사이클 `text-wrap-replace`가 "차기 사이클"로 미뤄둔 후속 기능을 구현했다. 긴 텍스트 교체 시 **줄바꿈(wrap) vs 폰트 축소(shrink)** 정책을 전역 상수(`TEXT_WRAP_ENABLED`)가 아닌 **교체 단위로 사용자가 선택**할 수 있도록 Replace(배치) 다이얼로그에 "긴 텍스트 줄바꿈" 토글을 추가했다.

핵심: 새 동작을 만들지 않고 **기존 줄바꿈 로직의 제어권을 UI로 이양**. 3-상태 의미론(`None`=전역 따름 / `True`=줄바꿈 / `False`=축소)으로 100% 하위 호환.

## 2. 변경 파일

| 파일 | 변경 |
|---|---|
| `app/operations/redact.py` | `RedactReplace.wrap: Optional[bool]=None` + `to_dict` 반영 |
| `app/operations/applicator.py` | op별 wrap 해석 → `_insert_text_with_autofit(wrap_enabled=...)` 스레딩, 내부 분기 `TEXT_WRAP_ENABLED`→`wrap_enabled` 치환 |
| `app/batch_replace_dialog.py` | `use_wrap_checkbox`(기본 체크) + emit dict `wrap` |
| `app/handlers/dialog_handlers.py` | `wrap` 읽어 `RedactReplace`에 전달 |
| `app/i18n/en.json`, `ko.json` | `batch.use_wrap`, `batch.use_wrap.tooltip` |
| `tests/test_text_wrap.py` | wrap True/False/None + to_dict 테스트 4건 |

## 3. PDCA 흐름

| 단계 | 산출물 |
|---|---|
| Plan | `docs/01-plan/features/replace-wrap-toggle.plan.md` |
| Design | `docs/02-design/features/replace-wrap-toggle.design.md` |
| Do | 6개 파일 구현 |
| Check | `docs/03-analysis/replace-wrap-toggle.analysis.md` (매치율 100%) |
| Act | 스킵 (≥90%) |
| Report | 본 문서 |

## 4. 검증 결과

- **전체 195 passed** (이전 191, 신규 4 순증, 회귀 0)
- 신규 테스트 4/4 통과
- i18n(en/ko 동수), mypy strict, claude_md_drift 게이트 통과

## 5. 설계 결정 & 정직성

- **3-상태 tri-state**: `None`을 기본값으로 둬 모든 기존 호출/직렬화 복원이 전역 동작을 그대로 따름. UI는 항상 명시적 bool 전달.
- **범위 한정**: 단일 선택 교체(`replace_selection`)는 단순 입력 프롬프트라 옵션 UI가 없어 의도적으로 제외(`wrap=None` 유지). 누락 아님.
- **과대포장 지양**: 백엔드 줄바꿈 로직은 선행 사이클에서 완성됨. 본 사이클은 제어권 이양에 집중.

## 6. 차기 후보

- `typing-legacy-core`: `document_session`/`model`/`pdf_engine` mypy strict 확대 (r2-quality-fixes에서 deferred).
- 단일 선택 교체 다이얼로그 고도화(폰트/줄바꿈 옵션 통합 UI) — 별도 사이클.

# Save Busy Indicator - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (M1/M2/S1 라인 단위 일치), 미승인 동작 변경 0, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-14
> **Plan(design integrated)**: [save-busy-indicator.plan.md](../../01-plan/features/save-busy-indicator.plan.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 import (Qt, QApplication) | `file_handlers.py:11, 13` | ✅ |
| M1 setOverrideCursor + status.saving + processEvents(저장 전 1회) | `file_handlers.py:163-165` | ✅ |
| M1 성공/에러 경로 불변 + `finally: restoreOverrideCursor` | `file_handlers.py:166-198` | ✅ |
| M1 취소 경로(set 진입 전, 복원 불필요) | `file_handlers.py:200-201` | ✅ |
| M2 i18n status.saving (en/ko, 281/281) | `en.json:51`, `ko.json:51` | ✅ |
| S1 커서 복원 테스트 (성공/실패/취소 + drain 헬퍼) | `tests/test_save_busy.py` | ✅ |

## 미승인 동작 변경 점검 (4항목 전부 안전)

- **(a) set/restore 1:1** — set은 단일 진입(L163), restore는 finally(L197-198)로 성공/에러/예외 모두 1회. 취소는 블록 밖이라 set 미호출.
- **(b) processEvents 1회** — 저장 전 단 1회, try/except/finally 어디에도 추가 호출 없음(재진입 0).
- **(c) 반환값·메시지 불변** — 성공/에러/취소 전부 기존과 동일(busy 래핑은 들여쓰기만).
- **(d) try 전 누수 위험** — set과 try 사이엔 showMessage/processEvents뿐(Qt 내부, 정상 환경 무예외). 실질 누수 없음.

## 검증

- 전체 **271 passed** (268 + 신규 3), i18n 281/281.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.

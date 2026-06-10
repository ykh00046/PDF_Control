# R4 Bugfix - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%**, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-10
> **Design**: [r4-bugfix.design.md](../../02-design/features/r4-bugfix.design.md)

---

## 종합 점수

| 카테고리 | 점수 | 상태 |
|----------|:----:|:----:|
| 설계 일치 (Must/Should) | 100% | ✅ |
| 설계 섹션 일치 (§1–§5) | 100% | ✅ |
| 컨벤션 준수 | 100% | ✅ |
| **종합 매치율** | **100%** | ✅ |

테스트: **221 passed** (기존 208 + 신규 13), mypy 게이트 2개 복구, mypy.ini 비ASCII 0바이트 — Python 3.13에서 전부 확인.

## 필수(Must) 항목

| 항목 | 구현 증거 | 일치 |
|------|----------|:--:|
| M1 (B1) mypy.ini ASCII-only | `mypy.ini:21` em-dash → `--`, 머리 주석 `mypy.ini:1-3` | ✅ |
| M2 (B2) `from_dict`에 `wrap` 전달 | `app/operations/base.py:61` `wrap=data.get("wrap", None)` | ✅ |
| M3 (B2) op 4종 round-trip 테스트 | `tests/test_op_serialization.py` (wrap T/F/None 파라미터화 + legacy 키부재) | ✅ |
| M4 (B3) 비번 stdin 채널 (job 파일 무기록) | `app/viewer.py:149-186`, `app/render_worker.py:30-56` | ✅ |
| M5 (B3) `render_password()` 접근자 + viewer 직접접근 제거 | `app/document_session.py:48-55`, viewer 내 `_password` 참조 0건 | ✅ |

## 권장(Should) 항목

| 항목 | 구현 증거 | 일치 |
|------|----------|:--:|
| S1 job 파일 무비번 가드 테스트 | `tests/test_render_password_channel.py::test_viewer_job_file_has_no_password` | ✅ |
| S2 mypy.ini ASCII-only 재발방지 주석 | `mypy.ini:1-3` | ✅ |

## 발견된 갭

- 🔴 미구현: **없음**
- 🟡 추가 구현(설계 강화 방향): viewer `errors="replace"`, 워커 reconfigure try-가드, `_read_password_from_stdin` 함수 추출 — 설계 문서에 반영 완료
- 🔵 변경: 테스트를 신규 파일(`test_render_password_channel.py`, `test_op_serialization.py`)로 분리 — plan의 "또는 신규" 허용 범위, 설계 문서에 반영 완료

## 결론

매치율 100% ≥ 90% → **Act(iterate) 생략, Report 단계 진행**.

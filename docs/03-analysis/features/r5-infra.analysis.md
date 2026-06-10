# R5 Infra - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (16/16 항목), Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-10
> **Design**: [r5-infra.design.md](../../02-design/features/r5-infra.design.md)

---

## 매치율: 100% (M1-M4 + S1 전 항목, Acceptance 6/6)

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 requirements `==` 핀 8종 (런타임 3 + 테스트 5) | `requirements.txt:7-17`, 로컬 설치 버전과 일치 | ✅ |
| M2 CI (windows-latest, py3.13, offscreen, push/PR) | `.github/workflows/ci.yml` — YAML 파스 검증 | ✅ |
| M3 `ui_handlers` 셰임 제거 + `app.handlers` 직수입 | `app/ui.py:15,37-42`, 셰임 부재, import 0건 | ✅ |
| M4 루트 정리 (문서 3종 archive, 스크립트 5종 scripts/) | `docs/archive/legacy-root/`, `scripts/` + 부트스트랩 3종 | ✅ |
| M4 CLAUDE.md 참조 갱신 | Current Status / Internal Documents / Added 절 | ✅ |
| S1 mypy 게이트 pytest 경유 동반 실행 | `ci.yml` 주석 명시, `test_mypy.py` 포함 | ✅ |

- 검증: 변경 후 전체 **221 passed**, `scripts/check_pymupdf_api.py`·`verify_style_inheritance.py` 신규 위치 실행 확인, requirements dry-run 해석 정상.
- 갭: 누락 0, 추가 0, 변경 0. pyproject/ruff는 Plan Won't에 명시된 의도적 보류.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.

# R7 History Policy - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (17/17 항목), 미승인 동작 변경 0, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-11
> **Design**: [r7-history-policy.design.md](../../02-design/features/r7-history-policy.design.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 `_remap_history_after_reorder` 헬퍼 (리매핑+redo 클리어+캐시 재구축) | `document_session.py:253-266` | ✅ |
| M1 move/duplicate/merge 리매핑 공식 (실측 시맨틱·bisect·insert_start) | `document_session.py:218-231, 309-315, 371-393` | ✅ |
| M1 `_rebuild_after_reorder` 삭제 (소스 0 참조) | grep 0건 | ✅ |
| M2 `reorder_pages` (순열 검증/항등 noop/select+리매핑) + page_manager 캡슐화 | `document_session.py:268-286`, `page_manager_dialog.py:440` | ✅ |
| M3 가짜 진행률 제거 + 미사용 import·i18n 6키(en/ko) 제거 | `dialog_handlers.py:157-202`, i18n grep 0건, 280/280 패리티 | ✅ |
| M4 테스트 갱신 1 + 신규 9 (물리 페이지 내용 추종 검증 3건 포함) | `test_page_management.py` | ✅ |
| S1 CLAUDE.md 동기 저장 한계(Risks) + Resolved 섹션 | `CLAUDE.md:210-213, 261` | ✅ |

## 미승인 동작 변경 점검

- 재배열 시 히스토리 폐기 경로 잔존: **없음** — 4개 작업 모두 단일 리매핑 헬퍼 경유.
- redo_stack 클리어는 설계 인가 사항(인덱스 무효화, delete 정책과 통일).
- RemoveSection: 제거된 것은 장식 UI뿐 — op 추가·워커 비동기 렌더·1페이지 1개 제약 불변.

## 검증

- 전체 **235 passed** (226 + 9), mypy strict(document_session) 0 에러, i18n 280/280.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.

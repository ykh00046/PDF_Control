# R7 History Policy - Completion Report

> **Summary**: 페이지 재배열(이동/복제/병합/드래그 정렬) 시 미저장 편집 히스토리가 **사라지지 않고 물리 페이지를 따라 보존**되도록 정책 통일. 부수: RemoveSection 가짜 진행률 제거, page_manager 캡슐화 해소. 매치율 100%, **235 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-11
> **Cycle**: r7-history-policy
> **Match Rate**: 100%

---

## 1. 무엇이 바뀌었나 (사용자 관점)

**전**: 텍스트 교체·삭제 편집을 쌓아둔 채 페이지를 이동/복제/병합/드래그 정렬하면 미저장 편집 전체가 소리 없이 사라짐 (delete/insert만 보존).
**후**: 모든 페이지 재배열에서 편집이 해당 물리 페이지를 따라간다. redo 스택만 무효화(기존 delete 정책과 동일).

## 2. 구현 요지

- **공통 헬퍼** `_remap_history_after_reorder(remap)`: 히스토리 op의 `page_index` 리매핑 + redo 클리어 + 페이지 캐시 재구축. move/duplicate/merge/reorder 4개 작업이 단일 경로 사용. 구 폐기 경로 `_rebuild_after_reorder` 삭제.
- **move 리매핑**: PyMuPDF `move_page` 시맨틱을 6케이스 실측으로 확정("원래 번호 기준 to 앞 삽입" → `frm<to`면 최종 `to-1`, `frm>to`면 `to`)하고 그대로 공식화. 문서가 변하지 않는 인접 이동은 자연 항등.
- **duplicate**: 복제본이 원본 바로 뒤 삽입 → op는 `p + |{복제 인덱스 < p}|`(bisect). 복제 페이지의 편집은 **원본에 잔류**(복제본은 무편집 시작).
- **merge**: 연속 블록 삽입 → `p >= 삽입 시작점`만 `+총 삽입 수`.
- **신규 `reorder_pages(new_order)`**: 드래그 정렬의 순열 재배열을 세션 public API로 — 순열 검증(ValueError)·항등 조기 반환 포함. `page_manager_dialog`의 `session.doc.select()` + private 호출(캡슐화 위반) 제거.
- **RemoveSection 정직화**: 검토 H3 재검증 결과 op 추가는 즉시 완료(무거운 렌더는 이미 워커 서브프로세스 비동기)였으므로, 실제 작업과 무관한 25/50/75 가짜 진행률 다이얼로그 제거. 미사용 i18n 키 6종(en/ko) 정리.

## 3. 검증

- 전체 테스트 **235 passed** (기존 226 + 신규 9: move 4, duplicate 1, merge 1, reorder 3). 물리 페이지 **내용 추종**을 직접 검증하는 테스트 3건 포함.
- 기존 `test_move_page_forward`의 "히스토리 폐기" 주장 제거 — **의도된 정책 변경**으로 plan에 명시.
- mypy strict(document_session 게이트) 0 에러 유지, i18n 280/280 패리티.
- Gap 분석 매치율 **100%**, 미승인 동작 변경 0.

## 4. 알려진 한계 (기록됨)

- 저장 시 op 적용은 UI 스레드 동기 — 고DPI RemoveSection 등 무거운 op가 쌓인 저장은 수 초 블록 가능. CLAUDE.md Risks에 기록, **비동기 저장**이 차기 후보.
- 페이지 재배열 자체는 여전히 비가역(undo 대상 아님) — 기존과 동일.

## 5. 다음 (로드맵)

- **후보**: async-save(저장 워커 분리 + 세션 재바인드), watermark, text-export-range, pyproject/ruff

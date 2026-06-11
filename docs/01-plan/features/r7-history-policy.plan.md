# R7 History Policy - Plan

> **Summary**: 페이지 재배열(이동/복제/병합/드래그 정렬) 시 편집 히스토리를 **폐기하지 않고 인덱스 리매핑으로 보존** — delete/insert와 정책 통일. 부수: RemoveSection 가짜 진행률 제거, page_manager의 세션 캡슐화 위반 해소
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-11, 매치율 100%, 235 passed)
> **Cycle**: r7-history-policy

---

## 1. 배경 (Why)

### 히스토리 정책 비대칭 (주 대상)

같은 "페이지 인덱스 변동" 상황인데 처리 정책이 갈린다:

| 작업 | 현재 히스토리 처리 |
|---|---|
| `delete_pages` | 삭제 페이지 op 제거 + 나머지 인덱스 **보정** |
| `insert_blank_page` | 인덱스 **보정** |
| `move_page` / `duplicate_pages` / `merge_pdfs` | `_rebuild_after_reorder()`로 **전부 폐기** |
| 드래그 정렬 (page_manager) | `session.doc.select()` 직접 호출 + `_rebuild_after_reorder()` **폐기** |

사용자 관점: 텍스트 교체를 쌓아둔 채 페이지 하나를 옮기면 **모든 미저장 편집이 소리 없이 사라진다**. 어떤 작업은 이력이 살고 어떤 작업은 죽는지 예측 불가.

### RemoveSection 가짜 진행률 (부 대상 — 2026-06-10 검토 H3 재검증 결과)

검증 결과 원 분석의 "동기 실행 프리징" 주장은 **부분적으로 부정확**: `apply_remove_section`은 op를 히스토리에 추가만 하고(즉시 완료), 무거운 렌더링은 미리보기 시 **이미 렌더 워커 서브프로세스**에서 비동기로 돈다. 실재하는 문제는 (a) 25/50/75 진행률이 아무 작업과도 대응하지 않는 **장식**이라는 점, (b) 사용자에게 무거운 작업이 그 자리에서 끝난 듯한 오해를 준다는 점. **저장 시 동기 적용**(전 op 공통)은 실재하나 별도 사이클 과제로 분리.

### 캡슐화 위반

`page_manager_dialog._on_rows_moved`가 `session.doc.select()` + private `_rebuild_after_reorder()`를 직접 호출 — 세션 불변식(히스토리/페이지 캐시 동기화)을 다이얼로그가 책임지는 구조.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `DocumentSession`에 `_remap_history_after_reorder(remap)` 공통 헬퍼 신설 — 히스토리 op의 `page_index`를 리매핑, `redo_stack` 클리어(인덱스 무효화 — delete와 동일 정책), 페이지 캐시 재구축, `modified`/`history_changed` 처리. `move_page`/`duplicate_pages`/`merge_pdfs`가 폐기 대신 이를 사용.
  - `move_page` 리매핑(PyMuPDF 시맨틱 실측 완료 — "원래 번호 기준 to 앞에 삽입"): `frm<to`: `p==frm→to-1`, `frm<p<to→p-1`; `frm>to`: `p==frm→to`, `to<=p<frm→p+1`.
  - `duplicate_pages`: `p → p + |{복제 인덱스 i : i < p}|` (복제 페이지의 op는 원본에 잔류).
  - `merge_pdfs`: `p >= 삽입 시작 커서 → p + 총 삽입 페이지 수`.
- **M2**: `DocumentSession.reorder_pages(new_order: List[int])` 신설 — `doc.select(new_order)` + 순열 리매핑(`p → new_order.index(p)`). `page_manager_dialog`가 `session.doc.select` 직접 호출 대신 이를 사용. 호출자 없어진 `_rebuild_after_reorder` 삭제.
- **M3**: `apply_remove_section`의 QProgressDialog(가짜 25/50/75) 제거 — op 추가는 즉시 완료되므로 상태바 메시지로 충분. 미사용 i18n 키 6종(`progress.remove.*` 5종 + `status.remove_processing`) en/ko 동시 제거.
- **M4**: 테스트 — 기존 `test_move_clears_history`(폐기 정책 고정)를 새 정책으로 갱신(**의도된 동작 변경**). 신규: move 양방향/인접 리매핑, duplicate 전/당/후 인덱스, merge 커서 전/후, reorder 순열, redo_stack 클리어 검증.

### 권장 (Should)

- **S1**: CLAUDE.md Known Issues에 "저장 시 op 적용은 동기(고DPI RemoveSection 포함 시 저장 수 초 소요 가능)" 한계 명시 — 비동기 저장은 후보 과제.

### 범위 외 (Won't)

- 비동기 저장(save 워커 분리) — 세션 재바인드 로직 연동이 커서 별도 사이클.
- 페이지 재배열의 undo(히스토리는 보존하지만 재배열 자체는 여전히 비가역) — 기존과 동일.
- watermark, text-export-range — 기능 사이클(R8+).

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 226+ 전부 통과 (갱신 1건 + 신규 포함).
- [ ] move/duplicate/merge/드래그 정렬 후 히스토리 op가 **물리 페이지를 따라간다**(저장 결과로 검증 가능한 리매핑) + `redo_stack`은 비워진다.
- [ ] `_rebuild_after_reorder` 부재, `page_manager_dialog`에서 `session.doc.select`/private 접근 0건.
- [ ] `apply_remove_section`에 QProgressDialog 부재, i18n 검증(en/ko 동수) 통과.
- [ ] mypy strict(document_session 게이트) 0 에러 유지.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/document_session.py` | `_remap_history_after_reorder` + `reorder_pages` 신설, move/duplicate/merge 리매핑 전환, `_rebuild_after_reorder` 삭제 |
| `app/page_manager_dialog.py` | `_on_rows_moved`가 `session.reorder_pages()` 사용 |
| `app/handlers/dialog_handlers.py` | 가짜 진행률 제거 |
| `app/i18n/en.json`, `ko.json` | 미사용 키 6종 제거 |
| `tests/test_page_management.py` | 정책 테스트 갱신 + 리매핑 테스트 신설 |
| `CLAUDE.md` | 정책 변경 + 저장 동기 한계 기록 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| move_page 리매핑이 PyMuPDF 시맨틱과 어긋남 | 2026-06-10 실측 프로브로 6개 케이스 확정(`frm<to→to-1`, `frm>to→to`), 테스트가 물리 페이지 추종을 직접 검증 |
| 보존된 op가 재배열 후 잘못된 페이지에 적용 | 저장 경로는 `op.page_index`만 사용 — 리매핑이 정확하면 적용 위치 보장. 페이지 내용 기반 검증 테스트 추가 |
| 히스토리 보존이 RemoveSection 1페이지 1개 제약과 충돌 | 제약은 `add_operation` 시점 검사라 리매핑과 무관(중복 생성 불가 유지) |
| i18n 키 제거 누락/불일치 | `validate_i18n`/`test_i18n_validation` 게이트 |

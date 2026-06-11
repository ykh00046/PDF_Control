# R7 History Policy - Design

> **Summary**: 재배열 시 히스토리 리매핑 보존의 구체 설계 (공통 헬퍼 + 작업별 리매핑 공식 + 캡슐화 + 가짜 진행률 제거)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-11, 매치율 100%)
> **Plan**: [r7-history-policy.plan.md](../../01-plan/features/r7-history-policy.plan.md)

---

## 1. 공통 헬퍼 (`app/document_session.py`)

```python
def _remap_history_after_reorder(self, remap: Callable[[int], int]) -> None:
    """Reindex pending operations after a page reorder/duplication/merge.

    Policy unified with delete_pages/insert_blank_page: history follows the
    physical page it was attached to; redo entries are invalidated because
    their indices no longer apply.
    """
    for op in self.history:
        op.page_index = remap(op.page_index)
    self.redo_stack.clear()
    self.pages = [PageModel(i) for i in range(self.doc.page_count)]
    self.modified = True
    self.history_changed.emit()
```

`typing.Callable` import 추가. `_rebuild_after_reorder`는 호출자 소멸 후 삭제.

## 2. 작업별 리매핑 공식

### move_page(from_index, to_index)

PyMuPDF `Document.move_page(frm, to)` 시맨틱 (2026-06-10 실측, 6케이스):
"frm 페이지를 제거한 뒤 **원래 번호 기준** to 페이지 앞에 삽입" → 최종 위치는
`frm < to`일 때 `to-1`, `frm > to`일 때 `to`.

```python
def remap(p: int) -> int:
    if from_index < to_index:
        if p == from_index:
            return to_index - 1
        if from_index < p < to_index:
            return p - 1
    else:
        if p == from_index:
            return to_index
        if to_index <= p < from_index:
            return p + 1
    return p
```

검증 예: `move(0,2)` → [P1,P0,P2,…]: p0→1, p1→0, p2→2. `move(4,1)` → [P0,P4,P1,P2,P3]: p4→1, p1→2, p3→4.
인접 이동 `move(i, i+1)`은 항등(실측상 문서도 불변) — 자연 처리.

### duplicate_pages(page_indices)

복제본은 원본 바로 뒤 삽입, op는 **원본에 잔류**:

```python
sorted_indices = sorted(page_indices)
def remap(p: int) -> int:
    return p + bisect.bisect_left(sorted_indices, p)   # |{i : i < p}|
```

`i == p`는 시프트에 불포함(복제본이 p 뒤에 삽입되므로 원본 위치 불변). 표준 라이브러리 `bisect` 사용.

### merge_pdfs(source_paths, after_index)

모든 삽입은 초기 커서(`after_index+1` 또는 끝)부터 연속:

```python
insert_start = page_count if after_index == -1 else after_index + 1
def remap(p: int) -> int:
    return p + total_added if p >= insert_start else p
```

### reorder_pages(new_order) — 신설 public 메서드

```python
def reorder_pages(self, new_order: List[int]) -> None:
    """Reorder pages to the given permutation of current indices.

    ``new_order[i]`` is the current index of the page that should end up at
    position ``i`` (same contract as ``Document.select``). Pending history
    follows each physical page; redo entries are invalidated.

    Raises ValueError when ``new_order`` is not a permutation of range(n).
    """
    if sorted(new_order) != list(range(self.doc.page_count)):
        raise ValueError("new_order must be a permutation of all page indices")
    if new_order == list(range(self.doc.page_count)):
        return
    self.doc.select(new_order)
    position_of = {old: new for new, old in enumerate(new_order)}
    self._remap_history_after_reorder(lambda p: position_of[p])
    get_logger().info(f"Reordered pages: {new_order}")
```

`page_manager_dialog._on_rows_moved`:

```python
session.reorder_pages(new_order)      # was: session.doc.select(...) + session._rebuild_after_reorder()
```

(항등 순열 조기 반환은 세션 쪽에서도 보장하므로 다이얼로그의 기존 조기 반환은 그대로 둬도 무해.)

## 3. M3 — RemoveSection 가짜 진행률 제거 (`handlers/dialog_handlers.py`)

`apply_remove_section`에서 QProgressDialog 전체 제거 — 본문은:

```python
operation = RemoveSectionAsImage(page_index, final_rect, dpi=dpi, format=fmt)
if not self.controller.add_operation(operation):
    return
self.last_selected_rect = None
self.viewer.clear_selection()
self.statusBar().showMessage(tr("status.remove_applied"))
self.logger.info(...)
```

- try/except(QMessageBox.critical) 유지 — add_operation은 False 반환 규약이므로 예외 경로는 사실상 RemoveSectionAsImage 생성뿐이지만 방어 유지.
- 실제 무거운 렌더는 미리보기 시 렌더 워커 서브프로세스에서 비동기 수행(기존 그대로) — 주석으로 명시.
- `QProgressDialog`/`QApplication` import는 파일 내 다른 사용처 확인 후 미사용 시 제거.
- i18n 제거 키(en/ko 동시): `status.remove_processing`, `progress.remove.title`, `progress.remove.rendering_top`, `progress.remove.rendering_bottom`, `progress.remove.merging`, `progress.remove.replacing`.

## 4. M4 — 테스트 (`tests/test_page_management.py`)

| 테스트 | 검증 |
|---|---|
| `test_move_remaps_history_forward` | op@0,1,2 + `move(0,2)` → 인덱스 {0→1, 1→0, 2→2}, redo 클리어 |
| `test_move_remaps_history_backward` | op@1,4 + `move(4,1)` → {4→1, 1→2} |
| `test_move_history_follows_physical_page` | 페이지별 고유 텍스트 PDF에서 op가 이동 후에도 같은 내용의 페이지를 가리킴 |
| `test_duplicate_remaps_history` | op@1, dup[0] → 2; op@0, dup[0] → 0 (원본 잔류) |
| `test_merge_remaps_history` | op@2, merge 1쪽 after_index=0 → 3; op@0 → 0 |
| `test_reorder_pages_remaps_history` | 순열 [2,0,1] → p0→1, p1→2, p2→0 |
| `test_reorder_pages_rejects_non_permutation` | ValueError |
| (갱신) `test_move_clears_history` → `test_move_preserves_history` | 폐기 → 보존으로 기대 변경 (의도된 정책 변경) |

## 5. 검증 절차

1. `pytest tests/test_page_management.py` → 신규/갱신 통과
2. `mypy app/document_session.py` strict 0 에러 유지
3. `validate_i18n` 게이트 + 전체 스위트

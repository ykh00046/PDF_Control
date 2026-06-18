# Page Undo/Redo - Design

> **Status**: Approved (Option C selected by delegated decision)
> **Created**: 2026-06-19

## Context Anchor

| Key | Value |
|---|---|
| WHY | 저장 전 페이지 편집 실수를 확실히 복구한다. |
| WHO | PDF 페이지를 회전·삭제·재배열·복제·병합하는 사용자 |
| RISK | 큰 PDF 스냅샷의 메모리 사용, pending operation의 페이지 인덱스 정합성 |
| SUCCESS | 모든 변형 작업 round-trip 복원, 새 작업 시 redo 무효화, 전체 테스트 통과 |
| SCOPE | 현재 세션·Page Manager 한정, 저장 후 히스토리 초기화, 최대 20단계 |

## 1. Overview

`DocumentSession`이 페이지 변경 직전의 문서 bytes, text operation history, text redo stack, modified 상태를 캡처한다. undo/redo는 현재 상태를 반대 스택에 넣고 스냅샷을 원자적으로 복원한다.

## 2. Architecture Options

| Option | Approach | Complexity | Maintainability | Risk | Decision |
|---|---|---:|---:|---:|---|
| A | 각 동작별 역연산 command | High | Medium | 삭제/병합 복원 오류 높음 | Reject |
| B | 별도 PageHistoryService + command hierarchy | High | High | 현재 규모 대비 과설계 | Reject |
| C | Session-owned bounded snapshots | Medium | High | 메모리 사용 제한 필요 | **Selected** |

Option C는 모든 PyMuPDF 변형에 동일한 복원 계약을 적용하고 pending operation 인덱스까지 함께 되돌릴 수 있어 가장 작은 안전한 변경이다.

## 3. Components

| Component | Responsibility |
|---|---|
| `_PageState` | PDF bytes와 operation/modified 상태 보존 |
| `DocumentSession._capture_page_state()` | 변경 전 스냅샷 생성 및 redo 무효화 |
| `undo_page_change()` / `redo_page_change()` | 양방향 상태 전환 |
| `page_change_group()` | 여러 내부 변경을 한 UI action으로 그룹화 |
| `PageManagerDialog` actions | Ctrl+Z/Ctrl+Shift+Z, 상태 동기화, thumbnail refresh |

## 4. State Flow

```text
page mutation -> capture current -> undo stack -> mutate
undo          -> capture current -> redo stack -> restore undo snapshot
redo          -> capture current -> undo stack -> restore redo snapshot
new mutation  -> capture current -> clear redo -> mutate
save          -> clear both page stacks
```

## 5. Data Model

`_PageState(document_bytes, history, redo_stack, modified)`를 private dataclass로 둔다. 스냅샷은 최대 `PAGE_HISTORY_LIMIT = 20`개이며 password나 file path는 복사하지 않는다.

## 6. API Contract

- `can_undo_page_change`, `can_redo_page_change`: bool property
- `undo_page_change()`, `redo_page_change()`: 성공 시 `True`, 빈 스택이면 `False`
- `page_change_group()`: context manager; 중첩 가능, 최초 진입에서만 스냅샷 캡처
- `page_history_changed`: UI action 상태 갱신 signal

## 7. Error Handling

스냅샷 복원 중 새 `fitz.Document`를 먼저 연 뒤 기존 문서와 교체한다. 복원 실패 시 기존 문서 핸들은 유지한다. 변경 validation은 스냅샷 생성 전에 수행한다.

## 8. Test Plan

- L1: rotate/delete/insert/move/reorder/duplicate/merge undo-redo round trip
- L1: pending operation page index 복원, redo invalidation, 20단계 제한, save reset
- L3/L4: Page Manager action enable/disable 및 다중 회전 단일 단계
- L5: UI -> controller/session -> document/history -> UI refresh

## 9. Security and Performance

임시 파일을 만들지 않아 암호 해제된 PDF가 디스크에 남지 않는다. 메모리 비용은 PDF 크기 × 최대 20이며 저장 시 해제한다.

## 10. Traceability

| Requirement | Implementation | Verification |
|---|---|---|
| FR-01~03,06 | `document_session.py` | `test_page_undo_redo.py` |
| FR-04~05 | `page_manager_dialog.py`, i18n | Qt action tests |

## 11. Implementation Guide

1. 세션 snapshot/restore와 bounded stack 구현
2. 각 mutating method에 변경 전 capture 연결
3. Page Manager actions와 grouping 연결
4. 단위·UI 회귀 테스트 실행

### 11.3 Session Guide

| Module | Files | Goal |
|---|---|---|
| module-1 | `document_session.py` | 상태 엔진과 mutation 통합 |
| module-2 | `page_manager_dialog.py`, i18n | 사용자 조작과 피드백 |
| module-3 | tests/docs | 계약 검증과 PDCA 산출물 |


# Page Undo/Redo - Plan

> **Status**: Approved (auto-approved by user delegation)
> **Created**: 2026-06-19
> **Feature**: `page-undo-redo`

## Executive Summary

| Perspective | Content |
|---|---|
| Problem | Page Manager의 삭제·이동·회전·병합은 문서를 즉시 변경하지만 복구 수단이 없어 실수 비용이 크다. |
| Solution | 문서와 pending operation 상태를 함께 보존하는 제한형 undo/redo 스냅샷을 제공한다. |
| Function/UX Effect | Page Manager에서 최대 20단계까지 실행 취소/다시 실행하고 버튼 상태를 즉시 반영한다. |
| Core Value | 파괴적 페이지 편집을 안전하게 탐색할 수 있어 사용자 신뢰와 작업 복구성을 높인다. |

## Context Anchor

| Key | Value |
|---|---|
| WHY | 저장 전 페이지 편집 실수를 확실히 복구한다. |
| WHO | PDF 페이지를 회전·삭제·재배열·복제·병합하는 사용자 |
| RISK | 큰 PDF 스냅샷의 메모리 사용, pending text operation의 페이지 인덱스 정합성 |
| SUCCESS | 모든 변형 작업 round-trip 복원, 새 작업 시 redo 무효화, 전체 테스트 통과 |
| SCOPE | 현재 세션·Page Manager 한정, 저장 후 히스토리 초기화, 최대 20단계 |

## 1. Background

`page-advanced-ops.report.md`가 다음 사이클 1순위로 `page-undo-redo`를 추천했다. 현재 일반 operation에는 undo/redo가 있지만 페이지 관리 메서드는 `fitz.Document`를 직접 바꾸므로 해당 히스토리로 복구되지 않는다.

## 2. Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | 회전, 삭제, 삽입, 이동, drag reorder, 복제, 병합을 undo/redo한다. | Must |
| FR-02 | 문서 내용과 pending operation/redo 인덱스를 함께 복원한다. | Must |
| FR-03 | 새 페이지 변경 후 page redo 스택을 비운다. | Must |
| FR-04 | Page Manager에 Undo/Redo action과 단축키를 제공한다. | Must |
| FR-05 | 여러 페이지 동시 회전은 한 단계로 취급한다. | Must |
| FR-06 | 저장 성공 시 page undo/redo를 초기화한다. | Must |

## 3. Non-functional Requirements

- 히스토리는 최근 20단계로 제한한다.
- 디스크에 평문 임시 PDF를 쓰지 않는다.
- 기존 text-operation undo/redo 계약을 변경하지 않는다.
- 기존 미커밋 watermark 변경과 충돌하지 않는다.

## 4. Success Criteria

| ID | Criterion |
|---|---|
| SC-01 | 각 페이지 변형이 undo 후 원상 복구되고 redo 후 재적용된다. |
| SC-02 | 삭제/재배열 전후 pending operation이 동일 물리 페이지를 가리킨다. |
| SC-03 | 새 변경이 page redo 스택을 무효화한다. |
| SC-04 | Page Manager action enabled 상태가 히스토리와 동기화된다. |
| SC-05 | 기능 테스트와 전체 회귀 테스트가 통과한다. |

## 5. Scope Exclusions

- 앱 재시작 후 히스토리 영속화
- 저장 완료 이후 undo
- text operation 히스토리와 하나의 시간축으로 통합
- extract/split 같은 원본 비변형 작업

## 6. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| 대용량 PDF 메모리 증가 | 20단계 상한, bytes 메모리 저장, 저장 시 즉시 초기화 |
| operation 객체 상태 손실 | 문서 bytes와 operation 목록을 deep copy하여 동일 시점 복원 |
| 다중 회전이 여러 단계가 됨 | `page_change_group()`으로 UI action 단위 그룹화 |


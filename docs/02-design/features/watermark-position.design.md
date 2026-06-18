# watermark-position Design Document

> **Summary**: 공통 위치 계산을 기존 워터마크 계층에 통합한다.
>
> **Project**: PDF Control | **Version**: 0.1.0 | **Author**: Codex | **Date**: 2026-06-19 | **Status**: Final
> **Planning Doc**: [watermark-position.plan.md](../../01-plan/features/watermark-position.plan.md)

## Context Anchor

| Key | Value |
|---|---|
| **WHY** | 중앙 고정 배치로 인한 본문 가림을 해소한다. |
| **WHO** | PDF에 로고, 초안, 승인 상태를 표시하는 사용자 |
| **RISK** | 회전 경계 및 구 payload 호환성 |
| **SUCCESS** | 5개 위치와 전체 전달/검증 경로 통과 |
| **SCOPE** | Operation부터 Dialog·i18n·테스트까지 |

## 1. Overview

### 1.1 Design Goals

하나의 위치 규칙을 텍스트와 이미지에 적용하고 기존 중앙·타일 동작을 보존한다.

### 1.2 Design Principles

- 렌더링 규칙은 Operation 계층에 둔다.
- 새 필드는 선택적 기본값으로 추가한다.
- 코드와 테스트를 같은 변경 단위로 완성한다.

## 2. Architecture Options

| Criteria | Option A: Minimal | Option B: Clean | Option C: Pragmatic |
|---|:-:|:-:|:-:|
| Approach | 각 클래스에 계산 중복 | 별도 positioning 모듈/값 객체 | watermark 모듈 공통 helper |
| New Files | 0 | 2 | 0 |
| Modified Files | 8 | 9 | 8 |
| Complexity | Low | High | Medium |
| Maintainability | Low | High | High |
| Effort | Low | High | Medium |
| Risk | Medium | Low | Low |

**Selected**: Option C — 작은 기능에 별도 계층을 만들지 않으면서 계산 중복을 제거한다.

### 2.1 Component Diagram

```text
Dialog(position) → DialogHandler → Controller → Watermark Operation
                                             ↘ to_dict/from_dict
Operation → _placement_center(rotated bounds, margin) → PyMuPDF page
```

### 2.2 Data Flow

선택 문자열 → settings dict → 생성자 → history 직렬화 → preview/save 공통 `apply()`.

### 2.3 Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| Position helper | math, fitz.Rect | 회전 bounding box 및 중심 계산 |
| Dialogs | QComboBox | 위치 선택 |
| Operation factory | payload | 이전 세션 복원 |

## 3. Data Model

```python
WatermarkPosition = Literal["center", "top-left", "top-right", "bottom-left", "bottom-right"]
position: WatermarkPosition = "center"
```

`tile=True`이면 position은 저장되지만 렌더링에서 타일이 우선한다.

## 4. API Specification

외부 API 없음. `EditorController.add_watermark`와 `add_image_watermark` 끝 인자에 `position="center"`를 추가한다.

## 5. UI/UX Design

### 5.1 Screen Layout

```text
[기존 워터마크 입력]
위치: [중앙 ▼]
[ ] 페이지 전체 반복(타일)
[적용] [취소]
```

### 5.2 User Flow

도구 메뉴 → 워터마크 설정 → 위치 선택 → 범위 선택 → 적용 → preview.

### 5.3 Component List

| Component | Location | Responsibility |
|---|---|---|
| WatermarkDialog | app/watermark_dialog.py | 텍스트 위치 입력 |
| ImageWatermarkDialog | app/image_watermark_dialog.py | 이미지 위치 입력 |

### 5.4 Page UI Checklist

- [ ] 위치 combobox: 중앙, 좌상, 우상, 좌하, 우하
- [ ] 타일 체크 시 위치 combobox disabled, 해제 시 enabled
- [ ] Apply payload에 `position` 포함

## 6. Error Handling

허용되지 않은 위치 문자열은 생성 시 `ValueError`. 구 payload 필드 부재는 `center`로 복원한다. 콘텐츠가 안전 영역보다 큰 축은 해당 축 중앙으로 배치한다.

## 7. Security Considerations

파일 접근·권한 변화 없음. 위치는 고정 allowlist로 검증하며 동적 코드/경로 생성이 없다.

## 8. Test Plan

| Level | Target | Tool | Phase |
|---|---|---|---|
| L1 | helper/Operation/serialization/controller | pytest | Do |
| L2 | 두 Dialog settings 및 tile interaction | pytest-qt | Do |
| L3 | preview/save 렌더 위치 회귀 | pytest + PyMuPDF | Do |
| L4 | 전체 테스트·ruff·mypy | CLI | QA |
| L5 | Dialog→Controller→history→save | 통합 테스트 | QA |

주요 시나리오: 5개 위치 사분면, 회전 텍스트, 이미지 배치, legacy payload, 위치 round-trip, UI 방출/비활성화, 기존 중앙·타일 회귀.

## 9. Implementation Details

- `_rotated_size(width, height, angle)`로 축 정렬 bounding box 크기를 구한다.
- `_placement_center(page_rect, width, height, position, margin=36)`는 페이지 좌표계에서 중심점을 반환한다.
- 텍스트는 `text_width × fontsize`, 이미지는 회전 후 target 크기를 입력한다.
- `POSITION_OPTIONS`는 UI가 공유 가능한 순서 있는 상수다.

## 10. Verification Criteria

| Plan SC | Evidence |
|---|---|
| SC-1 | 위치별 렌더 결과 bbox/사분면 테스트 |
| SC-2 | round-trip/legacy/controller 테스트 |
| SC-3 | pytest-qt payload/enabled 테스트 |
| SC-4 | 전체 quality gate |

## 11. Implementation Guide

### 11.1 Order

1. Operation 위치 모델·계산·직렬화
2. Factory/Controller/Handler 전달
3. Dialog/i18n
4. 단위·통합·UI 테스트
5. 전체 품질 게이트

### 11.2 Files

수정 10개 내외, 신규 테스트는 기존 `test_watermark.py`와 `test_op_serialization.py`에 추가한다.

### 11.3 Session Guide

| Module | Scope | Completion |
|---|---|---|
| module-1 | Operation + serialization | unit tests pass |
| module-2 | Controller + UI + i18n | UI tests pass |
| module-3 | full QA + documents | all gates pass |

단일 세션에서 module-1 → 3 순서로 수행한다.

## 12. Decision Record

| Decision | Rationale |
|---|---|
| Option C | 기능 규모에 맞는 재사용성과 변경량 균형 |
| 36pt fixed margin | UI 복잡도 없이 인쇄 안전 여백 제공 |
| tile precedence | 기존 타일 의미와 호환 |
| string Literal | JSON 및 Qt payload와 직접 호환 |

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0 | 2026-06-19 | Initial final design | Codex |

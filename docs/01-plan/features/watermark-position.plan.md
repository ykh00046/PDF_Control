# watermark-position Planning Document

> **Summary**: 텍스트·이미지 워터마크를 중앙 또는 네 모서리에 안전하게 배치한다.
>
> **Project**: PDF Control | **Version**: 0.1.0 | **Author**: Codex | **Date**: 2026-06-19 | **Status**: Final

## Executive Summary

| Perspective | Content |
|---|---|
| **Problem** | 단일 워터마크가 항상 중앙에 놓여 로고·승인 표시가 본문을 가린다. |
| **Solution** | 텍스트와 이미지에 중앙·좌상·우상·좌하·우하 위치 선택과 36pt 안전 여백을 제공한다. |
| **Function/UX Effect** | 두 워터마크 대화상자에서 위치를 직접 선택하며 타일 선택 시 위치 입력을 비활성화한다. |
| **Core Value** | 문서 내용을 보존하면서 브랜딩과 상태 표시를 유연하게 적용한다. |

## Context Anchor

| Key | Value |
|---|---|
| **WHY** | 중앙 고정 배치로 인한 본문 가림을 해소한다. |
| **WHO** | PDF에 로고, 초안, 승인 상태를 표시하는 사용자 |
| **RISK** | 회전된 콘텐츠가 페이지 경계를 벗어나거나 기존 저장 데이터가 깨질 수 있다. |
| **SUCCESS** | 5개 위치, 텍스트·이미지·직렬화·UI 경로 검증, 전체 테스트/ruff/mypy 통과 |
| **SCOPE** | 위치 모델, 렌더링, 직렬화, Controller/Handler, 두 대화상자, 영·한 번역, 테스트 |

## 1. Overview

### 1.1 Purpose

워터마크를 본문과 겹치지 않는 모서리에 배치할 수 있게 한다.

### 1.2 Background

기존 기능은 `tile=False`일 때 페이지 중앙만 사용한다. 프로젝트 로드맵의 다음 항목도 모서리 배치다.

### 1.3 Related Documents

- 기존 구현: `app/operations/watermark.py`
- 기존 보고서: `docs/04-report/features/watermark.report.md`

## 2. Scope

### 2.1 In Scope

- [x] 공통 위치 값 5종과 안전 여백 계산
- [x] 텍스트·이미지 Operation, 직렬화, Controller 전달
- [x] 두 대화상자와 영·한 번역
- [x] 회귀·단위·UI 테스트

### 2.2 Out of Scope

- 사용자 지정 좌표/여백
- 드래그 미리보기
- 타일 패턴 정렬 방식 변경

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-01 | `center`, `top-left`, `top-right`, `bottom-left`, `bottom-right` 지원 | High | Approved |
| FR-02 | 텍스트와 이미지에 동일한 위치 의미 적용 | High | Approved |
| FR-03 | 직렬화 왕복 및 구버전 payload의 중앙 기본값 유지 | High | Approved |
| FR-04 | UI 위치 선택 및 타일 선택 시 비활성화 | Medium | Approved |
| FR-05 | 콘텐츠가 페이지 안쪽 36pt 안전 여백에 배치 | High | Approved |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|---|---|---|
| Compatibility | 기존 호출·payload 동작 불변 | 기존 전체 pytest |
| Quality | ruff 0, strict operations mypy 0 | CI 명령 |
| Localization | 영어/한국어 키 완전성 | i18n 검증 테스트 |

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] SC-1: 5개 위치가 텍스트·이미지에서 의도한 사분면에 렌더링된다.
- [ ] SC-2: 위치가 모든 전달 계층과 직렬화 왕복에서 보존된다.
- [ ] SC-3: UI가 위치를 방출하고 타일 모드에서 위치 선택을 비활성화한다.
- [ ] SC-4: 전체 pytest, ruff check/format, mypy가 통과한다.

### 4.2 Quality Criteria

- [ ] 신규 핵심 경로 100% 테스트
- [ ] 기존 테스트 회귀 0건

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 회전 경계 계산 오차 | Medium | Medium | 회전 bounding box로 중심 좌표 계산 및 렌더 검증 |
| 큰 워터마크가 페이지보다 큼 | Medium | Low | 여백보다 콘텐츠가 큰 축은 페이지 중앙 fallback |
| 구 payload 필드 부재 | High | Medium | 역직렬화 기본값 `center` |

## 6. Impact Analysis

### 6.1 Changed Resources

| Resource | Type | Change Description |
|---|---|---|
| WatermarkText/WatermarkImage | Operation | `position` 필드 추가 |
| Controller/handlers | Application | 위치 전달 |
| dialogs/i18n | UI | 위치 선택 입력 추가 |

### 6.2 Current Consumers

| Resource | Operation | Code Path | Impact |
|---|---|---|---|
| Watermark operations | CREATE | dialogs → handlers → controller | Needs verification |
| Watermark operations | READ | preview/save applicator | Compatible |
| Serialized operation | RESTORE | `Operation.from_dict` | Needs default |

### 6.3 Verification

- [ ] 모든 소비 경로 테스트
- [x] 인증/권한 변경 없음
- [ ] 기존 payload 복원 확인

## 7. Architecture Considerations

### 7.1 Project Level Selection

Dynamic 데스크톱 애플리케이션의 기존 계층 구조를 유지한다.

### 7.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|---|---|---|---|
| 위치 표현 | enum / Literal 문자열 / 좌표 | Literal 문자열 | JSON·QComboBox·기존 생성자와 단순 연동 |
| 여백 | 사용자 입력 / 고정 | 36pt 고정 | 최소 UI와 예측 가능한 안전 영역 |
| 계산 위치 | UI / Controller / Operation | Operation 공통 함수 | preview/save 동일성과 재사용 |
| Testing | pytest/pytest-qt | 기존 도구 | CI와 일치 |

## 8. Convention Prerequisites

- Python 3.13, 120자, ruff format/check
- `app.operations.*` mypy strict
- UI 문자열은 `app/i18n/{en,ko}.json`
- 환경 변수 및 DB/API 변경 없음

## 9. Next Steps

1. [x] Design 문서 작성
2. [x] 권장 설계 자동 승인
3. [ ] 구현 및 검증

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0 | 2026-06-19 | Initial final plan | Codex |

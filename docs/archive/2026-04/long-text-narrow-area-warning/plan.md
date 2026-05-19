# Plan: long-text-narrow-area-warning

**Status**: Plan
**Date**: 2026-04-15
**Owner**: PDF Control
**Priority**: High (last open item in CLAUDE.md Known Issues)

## Problem

텍스트 교체(RedactReplace)가 좁은 영역에서 autofit 하한(8pt)에 도달해도 맞지 않을 때, 텍스트가 조용히 사라지거나 잘려 저장된다. 사용자는 Preview 단계에서 이 상황을 인지할 방법이 없다.

`app/operations_service.py`의 `ApplyResult`는 이미 경고를 수집하고 있으나 (`warnings`, `font_size_adjustments`, `text_shrink_count`), UI로 이어지는 연결이 없다.

## Goal

Preview 단계에서 autofit 경고/실패가 발생하면 **사용자 가시적 피드백**을 제공한다:

1. Replace 다이얼로그 또는 상태바에 경고 메시지
2. History 패널의 해당 작업에 warning badge/아이콘
3. 실패 케이스(hard failure)는 저장 차단 옵션 (소프트 경고 기본)

## Non-Goals

- autofit 알고리즘 자체 개선 (별도 feature)
- 텍스트 줄바꿈 자동화
- 다국어 글꼴 fallback 확장

## Acceptance Criteria

- [ ] Preview 시 `ApplyResult.warnings`가 수집되어 UI에 노출됨
- [ ] 상태바에 `N warnings` 인디케이터, 클릭 시 상세 표시
- [ ] History 패널 항목에 경고 아이콘 (shrink 발생 or 완전 실패)
- [ ] 완전 실패(4회 shrink 후 실패) 시 저장 전 확인 다이얼로그
- [ ] i18n 키 `en.json` / `ko.json` 양쪽 추가
- [ ] 단위 테스트: 경고 수집 경로, UI 상태 전이, i18n 키 완결성
- [ ] 전체 회귀 93/93 유지

## Affected Files

- `app/operations_service.py` — 경고 구조 유지 (이미 완료, 수정 최소)
- `app/ui.py` — 상태바 warning 인디케이터, 저장 전 확인
- `app/viewer.py` 또는 history 패널 모듈 — badge 렌더링
- `app/controller.py` — Preview 결과의 warnings를 UI로 중계
- `app/i18n/en.json`, `app/i18n/ko.json` — 새 키
- `tests/test_long_text_warning.py` (신규)

## Test Strategy

1. **Unit** — 좁은 rect + 긴 텍스트로 `OperationApplicator.apply_operations` 호출, `result.warnings` 비어있지 않음과 `text_shrink_count > 0` 확인
2. **Unit** — hard failure 시뮬레이션 (초미세 rect), warning 타입 구분 가능한지
3. **UI (pytest-qt)** — Preview 실행 후 상태바 텍스트/툴팁 검증
4. **i18n** — 새 키가 en/ko 양쪽 존재

## Risks

- **Preview 비용 증가**: 이미 apply는 실행되고 있어 추가 비용 없음
- **UI 과부하**: 다량의 경고 시 인디케이터 과용 → 요약 카운트 + 디테일 팝업 분리
- **False positive**: 8pt 이하 shrink가 실제로는 읽을 만한 경우 → info 레벨 vs warning 레벨 구분

## Open Questions

1. 완전 실패 시 **저장 차단**을 기본으로? → 초안: 기본 "경고만", 설정으로 "차단" 선택 가능
2. History 패널은 현재 warning badge 렌더 지원 여부 확인 필요 (Design 단계)

## Next Phase

`/pdca design long-text-narrow-area-warning` — History 패널 구조 및 상태바 위젯 분석 후 설계

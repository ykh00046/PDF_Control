# design-system Plan

> **Summary**: 디자인 시스템(토큰) 도입으로 UI 외관 통일 + 한국어 문구 다듬기
>
> **Author**: Claude (bkit)
> **Created**: 2026-09-09
> **Status**: ✅ Approved

## 1. Background

사용자가 공유한 영상 "클로드로 디자인할 때 프롬프트부터 넣지 마세요"(노디의 바이브코딩)의
요지: AI 결과물에서 'AI 냄새'가 나는 이유는 프롬프트가 아니라 **AI가 참고할 기준의 부재**.
제시된 3단계를 이 PySide6 데스크톱 앱에 맞게 적용한다.

| 영상 단계 | 이 프로젝트 적용 |
|---|---|
| Step 1. 내 상황에 맞는 좋은 디자인 레퍼런스 찾기 | 앱이 실제로 놓이는 환경 = Windows 11 → **Fluent Design**을 레퍼런스로 채택 (중성 레이어 표면, 단일 강조색, 4px 라운드, 8px 간격, 얇은 1px 테두리, 조용한 hover) |
| Step 2. 디자인 시스템 추출 → 적용 | 색/타이포/간격/라운드를 **토큰**으로 정의(`app/theme.py`)하고 QSS를 토큰에서 생성. 흩어진 인라인 `setStyleSheet` 제거 |
| Step 3. AI 티 나는 한글 문장·줄바꿈 다듬기 | `ko.json` 문구 검토: 이모지, em-dash, 번역투("로드되지 않음"), 상태바 장문 정리 |

## 2. Current-state Findings

- `ui._apply_styles`가 40여 줄 하드코딩 QSS(색상 12종 이상, 임의 값).
- 다이얼로그 5곳이 `color: red/blue/gray/orange/green` 등 **CSS 이름 색**을 직접 사용 → 표면마다 다른 톤.
- 뷰어 선택 상자는 `Qt.blue`, 검색 하이라이트는 임의 RGB.
- 상태바에 `🔤`/`⚠️` 이모지, `—` 대시, "문서가 로드되지 않음" 같은 번역투 문구.

## 3. Scope

- **In**: `app/theme.py`(Theme + build_stylesheet + label/callout/invalid 헬퍼), 메인 윈도우·상태바·뷰어·다이얼로그 적용, 회귀 가드 테스트, 한국어 문구 정리, 오프스크린 스크린샷 검증.
- **Out**: 다크 테마 변형(토큰 구조는 준비됨 — `Theme(...)` 인스턴스 하나 추가로 가능), 아이콘 세트 도입, 레이아웃 재구성.

## 4. Constraints

- 다크모드 계약 유지: 텍스트 `#1a1a1a` + 모든 팝업 표면에 밝은 배경 pin (`tests/test_ui_styles.py`).
- `QMenu::item { padding:` 규칙 형태 유지.
- 동작 변경 없음 — 스타일과 문구만.

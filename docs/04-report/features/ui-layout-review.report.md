# ui-layout-review Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-09-09
> **PDCA Cycle**: ui-layout-review

## 1. Executive Summary

사용자 요청("화면의 구성 및 버튼의 위치·명칭을 다시 검토")에 따라 메뉴 5개, 툴바 2개,
도크 2개, 다이얼로그 9개의 라벨·순서·단축키를 코드에서 덤프하고 오프스크린
스크린샷으로 실측했다. 검토 중 **페이지 자르기 다이얼로그가 열리자마자 크래시**하는
실제 버그를 발견해 수정했고, 구성 문제 8건과 명칭 불일치를 정리했다.
389 tests pass (신규 8), ruff 0.

## 2. Findings → Fixes

| # | 발견 | 조치 |
|---|---|---|
| 0 | `crop_dialog.py:55` `QPen.Antialiasing` → AttributeError (테스트 부재) | `QPainter.Antialiasing` + `test_crop_dialog_opens` |
| 1 | 편집 메뉴에 삭제/교체 항목 없음(툴바·단축키에만) | 메뉴에 "선택 영역 삭제/교체" 추가, 툴바는 같은 QAction 재사용 |
| 2 | "찾기"는 편집, "일괄 찾기/바꾸기"는 도구 메뉴 | 편집 메뉴 찾기 그룹으로 이동, Ctrl+H |
| 3 | 도움말에 F1 항목 없음(숨은 단축키) | "단축키 및 사용법" 항목(F1) |
| 4 | 툴바 라벨 "삭제/교체"가 대상 불명, 열기/저장/찾기 없음 | [열기][저장]│[실행 취소][다시 실행]│[선택 삭제][선택 교체]│[찾기]│[이전][페이지 N / 총수][다음] |
| 5 | 페이지 관리 툴바 오버플로(복제/추출/병합/분할 숨김) | 정렬/페이지 2줄 분리, "페이지 변경 실행 취소"→"실행 취소"(툴팁에 상세) |
| 6 | 영역 제거만 [취소][적용] 역순 | [영역 제거][취소] + 전 다이얼로그 순서 테스트 |
| 7 | 명칭 불일치: 폰트/글꼴, 워터마크/텍스트 워터마크, 도크 제목↔보기 메뉴, 색상 버튼 hex | 통일(글꼴, "텍스트 워터마크 추가...", "페이지 썸네일/작업 히스토리 패널", "선택...") |
| 8 | 썸네일 사이드바 아이콘 겹침(IconMode grid 미지정) | 단일 세로 열 `setGridSize` + `TopToBottom` |

## 3. Key Implementation Notes

- **메뉴 QAction 재사용 시 툴바 라벨**: 메뉴 텍스트에 니모닉(`저장(&S)`)이 있으면 툴바에
  "저장(S)"로 노출된다 → `QAction.setIconText`로 짧은 라벨(`toolbar.*` 키)을 별도 지정.
- **테스트에서 QMenu 참조**: `menuBar().actions()[i].menu()`로 얻은 래퍼는 GC로
  "Internal C++ object already deleted"가 난다 → 빌더가 `win.edit_menu` 등으로 보관.
- **주 버튼 순서 가드**: `test_dialog_button_rows_primary_first`가 9개 다이얼로그의
  마지막 버튼이 취소, 그 앞이 주 액션임을 고정.

## 4. Deferred

- 툴바 아이콘 세트(현재 텍스트 버튼). 아이콘이 들어오면 `setIconText` 라벨을 아이콘 밑 캡션으로 재사용 가능.
- 썸네일 사이드바 첫 항목 상단 여백(IconMode 레이아웃 특성) 미세 조정.

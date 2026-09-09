# modern-look Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-09-09
> **PDCA Cycle**: modern-look

## 1. Executive Summary

사용자 피드백 "왜 이리 촌스럽지"에 대한 응답. 색상 토큰(design-system 사이클)만으로는
부족했던 원인을 5가지로 진단하고 각각을 고쳤다: 텍스트 전용 툴바 → 라인 아이콘+캡션,
Qt 기본 도크 제목줄 → 플랫 커스텀 제목줄, 납작한 페이지 → 여백+그림자, 빈 회색 초기
화면 → 환영 카드, 테두리 없는 썸네일 → 카드 프레임. 434 tests pass (신규 45), ruff 0.

## 2. Deliverables

| Deliverable | Location | Status |
|---|---|:---:|
| 인라인 SVG 아이콘 세트 40종 | `app/icons.py` (신규) — `icon(name, color, size)`, `accent_icon`, HiDPI 2x, Disabled 모드 | Complete |
| 도크 제목줄 + 빈 상태 카드 | `app/ui_widgets.py` (신규) — `DockTitleBar`, `apply_dock_chrome`, `EmptyState` | Complete |
| 툴바 재구성 | `app/ui_toolbar.py` — 아이콘+캡션, 줌 우측 정렬, 페이지 상자 정리 | Complete |
| 메뉴 아이콘 | `app/ui_menu.py` `_apply_icons` | Complete |
| 뷰어 | `app/viewer.py` — 페이지 그림자·32px 여백 | Complete |
| 썸네일 프레임 | `app/thumbnails.py` `framed=True` | Complete |
| 페이지 관리·찾기 바 아이콘 | `page_manager_dialog.py`, `find_bar.py` | Complete |
| 테마 | `app/theme.py` — 본문 10pt, 툴바 흰 배경, 도크/빈 상태 셀렉터 | Complete |
| 번들 | `pdf_control.spec` hiddenimports `PySide6.QtSvg` | Complete |
| Tests | `tests/test_icons.py` — 전 아이콘 비공백 렌더, 빈 상태 스왑, 도크 크롬 | Complete |

## 3. Key Implementation Notes

- **자산 파일 없이 아이콘**: SVG 경로 문자열을 `QSvgRenderer`로 그리고 토큰 색으로
  틴트. 이미지 파일 배포·PyInstaller datas 관리가 없고 색 변경이 토큰 한 줄.
  `QtSvg`는 PySide6 휠에 포함되지만 spec hiddenimports에 명시해야 frozen에서 안전.
- **페이지 그림자와 좌표계**: 픽스맵 아이템은 원점에 그대로 두고 `setSceneRect`만
  여백만큼 확장 → 선택/하이라이트의 PDF↔scene 변환 코드 무변경.
- **오프스크린 한계**: `QGraphicsDropShadowEffect`는 offscreen grab에서 거의 보이지
  않는다(실행 화면에서 확인 필요).

## 4. Deferred

- 다크 테마(아이콘은 색 인자라 즉시 대응 가능).
- 툴바 캡션 숨김 옵션(아이콘만 모드).

# Dark-Mode UI Fix Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-07-21
> **PDCA Cycle**: dark-mode-ui-fix

## 1. Executive Summary

빌드 결과물에서 사용자가 보고한 두 UI 버그를 수정했다: (1) 메뉴 라벨과
단축키 텍스트가 겹침, (2) 팝업/알림에서 텍스트가 배경에 묻혀 안 보임.
둘 다 Windows 다크모드에서만 발생하는 스타일시트 누락이 원인이었다.

## 2. Root Cause

`app/ui.py::_apply_styles`는 라이트 테마를 강제한다 — 모든 표면에 어두운
텍스트(`#1a1a1a`)를 지정. 하지만 두 가지가 빠져 있었다:

- **QMenu::item padding 없음**: 스타일시트가 `QMenu`를 건드리는 순간 Qt는
  네이티브 메뉴 item 메트릭(라벨↔단축키 간격 포함)을 버린다. 우측 padding
  이 없으니 라벨과 shortcut이 충돌.
- **팝업 표면 배경 미지정**: QMessageBox/QDialog/QComboBox 드롭다운/
  QToolTip은 부모와 별개의 top-level 윈도우다. OS 다크모드의 어두운
  팔레트 배경을 유지한 채 우리의 `#1a1a1a` 텍스트가 얹혀 dark-on-dark로
  사라졌다.

dev/frozen 무관(스타일시트 동일). 라이트 모드 OS에서는 팔레트 배경이 이미
밝아 우연히 가려져 있던 잠복 버그다.

## 3. Fix

`_apply_styles` 스타일시트 보강:
- `QMenu::item { padding: 5px 28px 5px 24px }` + `:disabled` / `::separator`.
- 밝은 배경 pin: `QDialog`, `QMessageBox`(+`QMessageBox QLabel` 텍스트),
  `QComboBox QAbstractItemView`, `QToolTip`.
- 다이얼로그 내 위젯 라이트화: `QLineEdit/QTextEdit/QComboBox/QCheckBox/
  QRadioButton/QGroupBox/QPushButton`(hover/disabled 포함).

## 4. Verification

- offscreen 렌더 grab으로 before/after 실측: 메뉴는 라벨/단축키가 좌우
  분리, 메시지박스는 밝은 배경으로 텍스트 대비 확보.
- 회귀 방지 `tests/test_ui_styles.py` 3종 — 스타일시트에 `QMenu::item`
  padding, 팝업 표면 배경 셀렉터, 메시지박스 텍스트 색이 존재하는지 검증.
- 전체 334 tests pass + ruff check/format 0.

## 5. Notes / Follow-ups

- 근본적으로는 앱이 하드코딩 라이트 스타일시트로 다크모드를 억지 통일하고
  있어, 새 커스텀 위젯을 추가할 때 배경 pin을 계속 챙겨야 하는 구조적
  부채가 남는다. 정식 다크 테마 지원 또는 QPalette 기반 통일은 별도 사이클
  후보.

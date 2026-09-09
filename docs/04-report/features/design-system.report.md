# design-system Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-09-09
> **PDCA Cycle**: design-system

## 1. Executive Summary

영상의 "레퍼런스 → 디자인 시스템 → 문구" 3단계를 적용해 UI 외관을 한 벌의 토큰으로
통일했다. Windows 11 Fluent를 레퍼런스로 `app/theme.py`에 색·타이포·간격·라운드·
오버레이 색 토큰을 정의하고 QSS를 생성, 다이얼로그의 인라인 색상을 모두 헬퍼로
교체했다. 한국어 문구 23건을 정리했다. 381 tests pass (신규 10), ruff 0, mypy strict 0.

## 2. Deliverables

| Deliverable | Location | Status |
|---|---|:---:|
| 토큰 + QSS 빌더 | `app/theme.py` (신규, mypy strict) — `Theme`, `LIGHT_THEME`, `build_stylesheet`, `label_style`, `callout_style`, `invalid_field_style` | Complete |
| 메인 윈도우 적용 | `app/ui.py` — `_apply_styles` → `build_stylesheet`, 뷰어 배경/프레임 토큰화, 중앙 레이아웃 여백 0 | Complete |
| 상태바/뷰어 | `app/ui_statusbar.py` 글꼴 라벨, `app/viewer.py` 선택·하이라이트 색 토큰 | Complete |
| 다이얼로그 | `batch_replace_dialog`(5), `page_manager_dialog`(1), `remove_section_dialog`(4) 인라인 색 제거 | Complete |
| 한국어 문구 | `app/i18n/ko.json` 23건, `en.json` 4건(이모지 제거) | Complete |
| 가드 테스트 | `tests/test_theme.py` 10종 — 다크모드 계약, 토큰 전파, 플레이스홀더 누락, 헬퍼, **theme.py 밖 하드코딩 색상 grep 금지** | Complete |
| 실측 | `logs/review/theme_main.png`, `theme_batch.png`, `theme_remove2.png`, `theme_watermark.png` | Complete |

## 3. Key Implementation Notes

- **토큰이 단일 진실**: 위젯 코드는 hex를 모른다. `test_no_hardcoded_colors_outside_theme`가
  `setStyleSheet("…#hex…")`/이름 색을 grep으로 잡는다(사용자가 고른 RGB 스와치만 예외).
- **다크모드 계약 보존**: `text="#1a1a1a"` 토큰 + 팝업 표면 밝은 배경 규칙을 그대로
  생성하므로 기존 `test_ui_styles.py` 3종이 무변경 통과.
- **오프스크린 스크린샷**: `QT_QPA_FONTDIR=C:/Windows/Fonts` 없이는 offscreen 플랫폼에
  글꼴이 없어 모든 글자가 □로 찍힌다. 스핀박스 화살표 잘림은 변경 전에도 있던
  offscreen 스타일 특성(실제 Windows 스타일과 다름)이라 스타일 규칙을 최소로 되돌렸다.
- **QComboBox::drop-down을 스타일하면 화살표가 사라짐** → 규칙 제거(네이티브 화살표 유지).

## 4. Verification

- 381 passed, `ruff check`/`format --check` 0, `mypy --strict app/theme.py` 0.
- i18n tr() 참조 검증 통과(문구 값만 변경, 키 불변).

## 5. Deferred

- 다크 테마: `Theme(...)` 인스턴스 + 설정 토글만 추가하면 됨(구조 준비 완료).
- 툴바 아이콘 세트(현재 텍스트 버튼) — 아이콘 도입 시 토큰 색으로 SVG 틴트 권장.
- 썸네일 사이드바 IconMode 레이아웃(폭이 좁을 때 2열로 접히는 문제) 재검토.

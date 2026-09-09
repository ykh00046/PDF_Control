# r8-ux-expansion Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-09-09
> **PDCA Cycle**: r8-ux-expansion

## 1. Executive Summary

전체 검토 사이클. 문서 내 찾기(Ctrl+F, 라이브 하이라이트), 제자리 저장(Ctrl+S),
문서 닫기(Ctrl+W), 최근 파일 메뉴를 추가하고, 히스토리 패널 라벨/가짜 타임스탬프,
Save As 제안 경로, 중복 코드, 캐시 정책 등 6건의 품질 결함을 고쳤다.
371 tests pass (신규 37), ruff 0, mypy strict 2모듈 추가.

## 2. Deliverables

| Deliverable | Location | Status |
|---|---|:---:|
| 검색 헬퍼 | `app/text_search.py` (신규, mypy strict) — `find_text`, `SearchHit`, `next_hit_index` | Complete |
| 찾기 바 위젯 | `app/find_bar.py` (신규) — `FindBar`, 250ms 디바운스, Enter/Shift+Enter/Esc | Complete |
| 검색 핸들러 | `app/handlers/search_handlers.py` (신규) — `SearchHandlerMixin` | Complete |
| 뷰어 하이라이트 | `app/viewer.py` — `set_highlights`/`clear_highlights`/`_draw_highlights`, OrderedDict LRU | Complete |
| 세션 | `app/document_session.py` — `find_text`, `is_same_file`, 제자리 저장(temp+replace, 실패 복구) | Complete |
| 파일 액션 | `app/handlers/file_handlers.py` — `save_file`, `close_file`, `open_recent_file`, `_populate_recent_menu`, `_confirm_discard_changes`, `_remember_file` | Complete |
| 최근 파일 헬퍼 | `app/recent_files.py` (신규, mypy strict) | Complete |
| 메뉴 | `app/ui_menu.py` — File(Open Recent/Close/Save), Edit(Find/Find Next/Find Previous) | Complete |
| 품질 | `state_handlers.py` 워터마크 라벨·타임스탬프 제거·액션 상태 루프 | Complete |
| i18n | 23키 (en/ko) | Complete |
| Tests | `test_text_search.py`(7), `test_recent_files.py`(5), `test_find_ui.py`(11), `test_file_actions.py`(11)… 37 | Complete |

## 3. Key Implementation Notes

- **대소문자 구분 검색**: `Page.search_for`는 ASCII 대소문자를 무시하고 옵션이
  없다(Context7 문서 확인). `page.get_textbox(rect)`에 원문이 포함되는지로 후필터.
- **하이라이트 좌표**: 렌더 픽스맵이 scene 원점에 놓이므로 `pdf_rect × (zoom×150/72)`
  가 scene 좌표. `scene.clear()`가 C++ 아이템을 지우므로 stale 래퍼는
  `RuntimeError`로 무시하고 `_update_scene` 끝에서 재그리기.
- **오프스크린 테스트 함정**: 메인 윈도우가 `show()`되지 않으면 자식의
  `isVisible()`은 항상 False → 찾기 바 상태 판정은 `isHidden()`.
- **Qt 시그널 emit**: 테스트에서 `QMenu.aboutToShow.emit()`은 슬롯을 호출하지
  않았다 → 재구성 로직을 윈도우 메서드(`_populate_recent_menu`)로 두고 직접 호출.
- **제자리 저장 안전성**: Windows에서는 MuPDF가 연 파일을 `os.replace`할 수 없어
  old doc을 먼저 close. replace 실패 시 원본을 재오픈해 세션을 살리고
  tmp를 정리(테스트로 고정). `_bind_document`는 이미 닫힌 old doc을 건너뜀.

## 4. Verification

- 371 passed(기존 334 + 신규 37), `ruff check`/`ruff format --check` 0,
  `test_all_tr_keys_exist` 통과, mypy strict(`text_search`, `recent_files`) 0.
- `logs/review/find_bar_smoke.png`: 찾기 바 + 하이라이트(현재 주황/나머지 노랑) 실측.

## 5. Deferred

- 디자인/테마 개선 — 사용자 제공 영상 참고, 별도 사이클.
- 찾기 결과에 pending 교체 텍스트 반영(워커 렌더 비용 대비 수요 확인 후).
- 찾기 결과 → 선택 영역 연결(하이라이트를 클릭해 바로 삭제/교체).
- async save, 썸네일 컨텍스트 메뉴(이전 사이클 보류 유지).

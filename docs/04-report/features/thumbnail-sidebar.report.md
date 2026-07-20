# Page Thumbnail Sidebar Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-07-20
> **PDCA Cycle**: thumbnail-sidebar

## 1. Executive Summary

좌측 도크 페이지 썸네일 사이드바를 추가했다. 클릭 탐색, 뷰어와 양방향
하이라이트 동기화, 페이지 관리 변경 실시간 갱신(회전 각도 라벨 포함),
View 메뉴 토글 + config 영속. 331 tests pass (신규 9).

## 2. Deliverables

| Deliverable | Location | Status |
|---|---|:---:|
| 공유 렌더 헬퍼 | `app/thumbnails.py` (신규) — `render_page_thumbnail`, PageManagerDialog 위임으로 중복 제거 | Complete |
| 사이드바 위젯 | `app/thumbnail_panel.py` (신규) — `ThumbnailSidebar`, QTimer 배치 렌더 + 세대 가드 | Complete |
| MainWindow 배선 | `app/ui.py`(도크), `app/handlers/state_handlers.py`(`_go_to_page` 추출, 토글, 세션 바인딩), `app/handlers/dialog_handlers.py`(pages_changed 갱신), `app/ui_menu.py`(View 토글) | Complete |
| Config | `ui.thumbnail_panel_visible` 기본 True | Complete |
| i18n | `thumbnail_panel.title`, `menu.view.thumbnails_toggle` (en/ko) | Complete |
| Tests | `tests/test_thumbnail_panel.py` 9종 | Complete |

## 3. Key Implementation Notes

- **스레드 없는 비블로킹 렌더**: fitz는 스레드 안전하지 않아 QTimer(0)
  배치(8p/틱) + `flush_pending_renders()`(테스트/즉시 렌더용). 세대
  카운터가 문서 교체/닫기 이후 잔존 타이머를 무효화 — 닫힌 doc 접근 없음.
- **재진입 가드**: `set_current_page`(프로그램적)는 `_syncing` 플래그로
  `page_selected` 재발신을 막아 클릭↔하이라이트 순환을 차단(테스트로 고정).
- **`_go_to_page` 단일 경로**: 스핀박스 점프가 위임하도록 리팩터링,
  경계 밖 인덱스 가드 추가(기존 스핀박스 경로엔 없던 방어).
- **갱신 트리거**: PageManagerDialog의 모든 변경(다이얼로그 내 undo/redo
  포함)은 `pages_changed`를 경유하므로 `_on_pages_changed` 한 곳에
  refresh를 얹는 것으로 충분.

## 4. Verification

- 신규 9 테스트: 채움(아이콘 렌더 완료 검증)/닫기 비움/클릭 탐색/스핀박스
  동기화/경계 가드/삭제 갱신/회전 라벨/토글 config 왕복/재진입 가드.
- 전체 331 passed + ruff check/format 0 + i18n tr() 참조 검증 통과.

## 5. Deferred

- 썸네일에 pending 텍스트 op 미리보기 반영(페이지당 워커 렌더 비용 —
  수요 확인 후).
- 사이드바에서 직접 페이지 관리(컨텍스트 메뉴 회전/삭제) — 현재는
  PageManagerDialog 역할 유지.

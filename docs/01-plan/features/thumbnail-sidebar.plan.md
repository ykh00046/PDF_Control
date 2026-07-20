# Page Thumbnail Sidebar Plan

> **Status**: Complete
> **Project**: PDF Control
> **Date**: 2026-07-20
> **PDCA Cycle**: thumbnail-sidebar

## 1. Background

페이지 탐색·구조 파악 수단이 스핀박스와 PageManagerDialog(모달)에 갇혀
있었다. 썸네일 사이드바는 페이지 구조를 상시 노출하고 클릭 탐색을
제공한다 — page-undo-redo로 완성된 페이지 관리 기능의 가시성을 메인 UI로
끌어올리는 후속. (풀 async-save는 기존 실측(대부분 저장 <1s)으로 보류
유지가 타당해 이번 사이클로 선정하지 않음.)

## 2. Requirements

| # | Requirement |
|---|---|
| R1 | 도크형 썸네일 사이드바(좌측) — 문서 열기/닫기에 따라 채움/비움 |
| R2 | 썸네일 클릭 → 뷰어 해당 페이지 이동 |
| R3 | 뷰어 페이지 변경(스핀박스/PageUp·Down) → 사이드바 하이라이트 동기화(재진입 없음) |
| R4 | 페이지 관리 변경(회전/삭제/이동/undo/redo 등) → 사이드바 갱신, 회전 각도 라벨 표시 |
| R5 | View 메뉴 토글 + `ui.thumbnail_panel_visible` config 영속(히스토리 패널 패턴) |
| R6 | 대용량 문서에서 UI 블로킹 없는 렌더링 |

## 3. Design Decisions

- **청크 렌더링(스레드 없음)**: fitz Document는 스레드 안전하지 않으므로
  백그라운드 스레드 대신 QTimer(0) 배치(8페이지/틱)로 이벤트 루프에서
  렌더. 세대 카운터로 문서 교체/닫기 후 잔존 타이머가 닫힌 doc을 만지는
  것을 차단.
- **DRY**: fitz→QPixmap 변환이 PageManagerDialog와 2번째 사용이 되므로
  `app/thumbnails.py`로 추출, 다이얼로그는 위임(죽은 THUMB_DPI 제거).
  스핀박스 점프도 신설 `_go_to_page`로 통합(썸네일 클릭과 공유).
- **썸네일은 세션 doc 기준**: 페이지 관리 반영, pending 텍스트 op 미반영
  (미리보기 op 렌더는 페이지당 워커 비용 — 범위 외).
- 동기화 재진입 방지는 `_syncing` 가드(프로그램적 하이라이트는
  page_selected 미발신).

## 4. Success Criteria

- 신규 시나리오 테스트(채움/클릭 탐색/하이라이트 동기화/갱신/토글 영속/
  재진입 가드) + 기존 전 회귀 통과
- ruff check/format 0, i18n 검증 통과

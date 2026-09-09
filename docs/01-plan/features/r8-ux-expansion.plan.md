# r8-ux-expansion Plan

> **Summary**: 전체 프로젝트 검토 사이클 — 기능 확장(찾기, 저장/닫기/최근 파일)과 코드 품질 보완
>
> **Author**: Claude (bkit)
> **Created**: 2026-09-09
> **Status**: ✅ Approved

## 1. Background

사용자 요청: "프로젝트 전체적으로 검토해서 기능 확장 및 보완, 코드 개선 및 보완".
`app/`, `tests/`, `docs/` 전수 검토 결과 기능 공백과 품질 결함을 아래와 같이 식별했다.

### 1.1 기능 공백 (데스크톱 PDF 편집기 기준)

| # | 공백 | 근거 |
|---|---|---|
| F1 | 문서 내 텍스트 **찾기**가 없음 | 배치 교체 다이얼로그에만 검색이 있고, 뷰어에서 위치를 찾아갈 수 없음 |
| F2 | **Save(Ctrl+S)** 없음 — 항상 Save As | 매 저장마다 파일 선택 다이얼로그 |
| F3 | **Close(Ctrl+W)** 없음 | 문서를 닫으려면 다른 파일을 열거나 종료해야 함 |
| F4 | **최근 파일** 없음 | config에 `last_directory`만 있음 |

### 1.2 품질 결함

| # | 결함 | 위치 |
|---|---|---|
| Q1 | 히스토리 패널에 `WatermarkText`/`WatermarkImage` raw 클래스명 노출 | `state_handlers._get_operation_display_name` |
| Q2 | 히스토리 항목 타임스탬프가 op 생성 시각이 아니라 **패널 재구성 시각** | `time.strftime` at rebuild |
| Q3 | Save As 제안 경로 `str.replace(".pdf", …)` — `.PDF` 확장자면 **원본과 동일 경로 제안** | `file_handlers._commit_save` |
| Q4 | open/closeEvent에 동일한 "저장할까요?" 블록 중복 | `file_handlers` |
| Q5 | `_update_edit_action_states` 13줄×2 중복 리스트 | `state_handlers` |
| Q6 | 뷰어 캐시가 "LRU" 주석과 달리 FIFO | `viewer.image_cache` |

## 2. Scope

- **In**: F1–F4, Q1–Q6, i18n(en/ko), 테스트, 문서.
- **Out**: 디자인/테마 개선(별도 사이클, 사용자 제공 영상 참고), async save, 썸네일 컨텍스트 메뉴.

## 3. Design Decisions

- **찾기는 pending op 미반영** — `self.doc`(페이지 관리 반영본)에서 검색. 배치 교체와 동일 기준. 재렌더 워커를 검색마다 돌리는 비용 대비 이득 없음.
- **대소문자 구분**: PyMuPDF `search_for`는 case 옵션이 없어 `get_textbox(rect)` 후필터(공식 문서 권장 방식).
- **제자리 저장**: 세션이 동일 경로를 감지해 `.saving.tmp` → old doc close → `os.replace`. 암호화 문서는 Encrypt & Save As로 리다이렉트(평문 덮어쓰기로 보호가 사라지는 사고 방지).
- **최근 파일**: pure 헬퍼(`app/recent_files.py`) + `aboutToShow` 재구성. 핸들러(`_populate_recent_menu`)가 동작을 소유하고 빌더는 구성만.

## 4. Verification

- 신규 테스트: text_search(7), recent_files(5), find UI(11), file actions(11), mypy strict 2모듈 승격.
- 전체 pytest + ruff check/format + i18n tr() 참조 검증.
- 오프스크린 grab으로 찾기 바/하이라이트 외관 실측.

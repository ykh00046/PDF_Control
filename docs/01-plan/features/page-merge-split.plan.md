# Page Merge / Split - Plan

> **Summary**: 문서 전체를 여러 PDF로 쪼개는 분할(Split)과 여러 PDF를 한 번에 합치는 다중 병합(Batch Merge) 기능 추가 — 페이지 관리(PageManagerDialog)의 마지막 빠진 조각
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: ✅ Complete
> **Cycle**: page-merge-split

---

## 1. 배경 (Why)

`PageManagerDialog`는 회전·삭제·이동·복제·추출·병합(단일 파일)까지 갖췄으나, 문서 워크플로우의 핵심 두 축인 **분할(Split)**과 **다중 병합**이 비어 있다.

### 현재 상태 재검증 (코드 기준)

| 기능 | 현재 | 빠진 것 |
|------|------|---------|
| 병합 | `merge_pdf(source_path, after_index)` — 외부 PDF **1개** 삽입 | 여러 파일을 **한 번에 순서대로** 병합 |
| 추출 | `extract_pages(indices, out)` — 선택 페이지 → **1개** 파일 | — (추출은 충분) |
| **분할** | **없음** | 문서를 **여러 파일로** 분할(낱장 / 범위 / N장 단위) |

> **정직성 노트**: "병합"은 단일 파일 한정으로 부분 존재한다. 이번 사이클의 신규 가치는 **분할(Split)** 이 핵심이고, 병합은 다중 파일 지원으로 확장한다. 기존 `merge_pdf`는 하위호환 유지를 위해 신규 `merge_pdfs`로 위임 처리한다.

---

## 2. 목표 (What)

### 필수 (Must)
- **M1 — 분할 코어**: 문서를 여러 PDF로 분할하는 순수 로직 + `DocumentSession.split_document`. 3가지 모드:
  - `SINGLE`: 페이지마다 1개 파일
  - `EVERY_N`: N페이지씩 묶어 1개 파일
  - `RANGES`: 사용자 범위 스펙(예: `"1-3, 5, 7-9"`) → 그룹마다 1개 파일
- **M2 — 범위 파서**: `"1-3,5,7-9"` 형태를 1-based로 받아 0-based 인덱스 그룹으로 변환, 잘못된 입력(역순/범위초과/빈값) 거부.
- **M3 — 다중 병합**: `DocumentSession.merge_pdfs(source_paths, after_index)` — 선택 순서대로 연속 삽입. `merge_pdf`는 이를 위임.
- **M4 — 원본 불변**: 분할은 읽기 전용(원본 문서/히스토리/`modified` 미변경), `extract_pages`와 동일 계약.

### 권장 (Should)
- **S1 — UI**: `PageManagerDialog`에 "분할" 액션 + `SplitDialog`(모드 선택·파라미터·출력 폴더). 병합 액션은 다중 파일 선택(`getOpenFileNames`)으로 확장.
- **S2 — 안전장치**: 출력 디렉터리 미존재/원본 덮어쓰기/빈 그룹 방지, 충돌 없는 파일명 자동 번호.
- **S3 — i18n**: 신규 UI 문자열 en/ko 완비.

### 범위 외 (Won't)
- 북마크/목차 기반 자동 분할, 파일 크기 기준 분할
- 분할 결과 자동 열기, ZIP 묶음 출력
- 병합 시 페이지 범위 선택(전체 삽입만)

---

## 3. 성공 기준 (Acceptance)

- [x] 기존 146개 테스트 전부 통과 유지 (회귀 0) → 총 177 passed
- [x] **신규 단위 테스트**: 범위 파서(정상/역순/초과/공백/중복), 그룹 계산(3모드)
- [x] **신규 통합 테스트**: `split_document`가 모드별로 정확한 파일 수·페이지 구성 생성, 원본 불변 확인
- [x] **신규 통합 테스트**: `merge_pdfs` 다중 파일 순서 병합, `merge_pdf` 위임 동작
- [x] 출력 경로/덮어쓰기/빈입력 예외 처리 검증
- [x] mypy strict 게이트 회귀 없음 (신규 순수 모듈 `page_split` strict 무에러)
- [x] i18n 키 완전성 테스트 통과

---

## 4. 리스크

| 리스크 | 완화 |
|--------|------|
| 범위 스펙 파싱 엣지(역순·중복·공백·0) | 전용 파서 + 단위테스트로 정상/이상 모두 고정 |
| 분할 출력 파일명 충돌 | base명 + zero-pad 번호, 디렉터리 검증, 원본경로 충돌 거부 |
| 다중 병합 인덱스 시프트 | 삽입마다 `start_at` 누적 갱신, 순서 보존 검증 테스트 |
| 대량 분할 시 자원 | 파일마다 `new_doc` 생성→저장→`close`(finally) |
| mypy 레거시 모듈(document_session) strict 제외 유지 | 코어 순수 로직을 별도 `page_split.py`(strict-clean)로 분리 |

---

## 5. 작업 분해

1. **M2/M1 코어**: `app/page_split.py` (SplitMode, parse_page_ranges, compute_split_groups) — 순수·테스트 우선
2. **M1/M3/M4 세션**: `DocumentSession.split_document`, `merge_pdfs`(+`merge_pdf` 위임)
3. 컨트롤러 위임 메서드(`split_document`, `merge_pdfs`)
4. **S1/S3 UI**: `SplitDialog` + PageManagerDialog 액션/다중병합 + i18n
5. **Check**: 신규 + 전체 테스트, gap 분석
6. **Iterate**: 갭<90%면 자동 개선
7. **Report**: 완료 보고

# natural-replace Plan

> **Summary**: 텍스트 교체 결과가 원문과 구별되지 않도록 — 베이스라인·정렬·배경색·가용 폭·줄간격
>
> **Author**: Claude (bkit)
> **Created**: 2026-09-09
> **Status**: ✅ Approved

## 1. Background

사용자 요청 "글자 바꾸기를 더 자연스럽게". 다양한 조건(문장 속 단어, 표의 오른쪽 정렬 숫자,
색 배경 위 굵은 글씨, 한글, 문단)으로 교체를 실행해 before/after 렌더 시트로 비교했다
(`logs/review/replace/sheet.png`).

## 2. Findings (측정 근거)

| # | 증상 | 측정 | 원인 |
|---|---|---|---|
| 1 | 교체 글자가 위로 뜸 | 12pt 베이스라인 50.0 → 48.62 (−1.38pt) | `insert_textbox`의 첫 줄 위치가 페이지 기존 폰트 리소스 메트릭을 따름(깨끗한 페이지 0 오차, 실문서 0.96배). 예측 보정 불가 |
| 2 | 표 숫자가 왼쪽 정렬로 바뀜 | 1,234.00(우) → 99.00(좌) | `RedactReplace.align` 미사용(항상 0) |
| 3 | 색 배경 위 흰 패치 | CONFIDENTIAL 2026 | 리댁션 fill 흰색 고정 |
| 4 | 긴 교체가 축소되면서도 다음 단어와 겹침 | 1234567890 → 7.9pt + 겹침 | 가용 폭 = 원폭+14pt 상수, 이웃 무시 |
| 5 | 여러 줄 교체 줄간격 상이 | 18.9 → 13.2 | 줄높이 1.2배 상수 |

## 3. Design

- **삽입 방식 교체**: `insert_textbox` → 자체 줄바꿈 + 줄별 `insert_text(point)`. 첫 줄은 원문
  베이스라인, 이후 줄은 원문 줄간격(`baseline_pitch`) 또는 1.2×크기.
- **정렬**: `ALIGN_AUTO` 기본. 숫자/금액 & 뒤에 글리프 없음 → 오른쪽 끝 유지; 그 외 왼쪽.
  자동일 때 정한 쪽에 공간이 없으면 반대쪽으로. 사용자 명시(좌/중/우)는 그대로.
- **배경색**: `sample_background_color` — 72dpi 페이지 픽스맵 1회, rect 바깥 2pt 링 최빈색.
  흰색 근사(≥246)는 순백. `RedactDelete`/`RedactReplace.apply(page, fill=)`, 미리보기 동일.
- **가용 폭**: `line_free_space` — 같은 줄 다음/이전 글리프, 세로 괘선(`get_drawings`), 여백.
  한 줄 확장 한도 `max(원폭×1.5, 8×크기)`; 그다음 원폭(+14pt 톨러런스) 기준 줄바꿈; 축소 폭도
  이웃까지로 제한.
- **호환**: 경고 코드(`text.wrapped/shrunk/overflow`)와 상세 필드, wrap 토글 의미 불변.
  기존 wrap/warning 테스트 무수정 통과가 수용 기준.
- **UI**: `ReplaceTextDialog` — 텍스트(여러 줄), 정렬, 글자 크기, 줄바꿈.

## 4. Out of scope

- 같은 줄 나머지 단어를 밀어내는 리플로우(임베디드 서브셋 폰트 재삽입 시 충실도 위험).
- 문자 간격(트래킹) 조정으로 폭 맞추기.

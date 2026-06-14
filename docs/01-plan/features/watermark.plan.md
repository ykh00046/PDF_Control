# Watermark - Plan

> **Summary**: 페이지에 텍스트 워터마크(대각선/투명도 조절) 추가 기능. `TextWriter`+morph 기반 비파괴 오버레이 op로 operations 파이프라인에 통합 — preview=save 자동 보장
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%, 281 passed)
> **Cycle**: watermark

---

## 1. 배경 (Why)

PDF 제어 도구에 흔히 필요한 기능 — "CONFIDENTIAL", "DRAFT", 회사명 등을 페이지에 반투명 대각선으로 얹는 워터마크. 현재 없음.

### 실측 (probe — 설계 확정)

`fitz.TextWriter(page.rect, opacity=, color=)` + `append(point, text, font, fontsize)` + `write_text(page, morph=(pivot, Matrix(angle)))` 로 **임의 각도(45도) + 투명도** 워터마크가 렌더됨. 텍스트는 검색 가능, 비파괴(콘텐츠 추가만)라 SAVE/PREVIEW 동일 적용 → preview=save 자동. (`insert_textbox`의 `rotate`는 0/90/180/270만 지원 → 부적합, 확인됨.)

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `operations/watermark.py` 신설 — `WatermarkText(Operation)` (page_index, text, fontsize, color, opacity, angle). `apply(page)`가 `TextWriter`+morph로 페이지 중앙에 회전·반투명 텍스트 렌더. `to_dict`/`from_dict` 라운드트립.
- **M2**: `Operation.from_dict`에 `WatermarkText` 분기 추가. applicator에 watermark pass 추가(**마지막 pass** — crop→redaction→text→section removal→watermark, 다른 콘텐츠 위에 오버레이). SAVE/PREVIEW 동일 경로(비파괴).
- **M3**: `app/watermark_dialog.py` + `controller.add_watermark(...)` — 텍스트·폰트크기·색상·투명도·각도·적용범위(현재/전체) 입력. 전체 범위는 페이지마다 `WatermarkText` op 생성(batch-replace와 동일 패턴, `add_operation` 루프). Tools 메뉴 → "Add Watermark…".
- **M4**: i18n(en/ko) — 다이얼로그·메뉴·상태 문자열. 누락 0.
- **M5**: 테스트 — op round-trip(test_op_serialization 확장), apply 후 워터마크 텍스트가 저장 파일에 존재 + 검색 가능, 전체 범위 시 전 페이지 적용, preview=save 등가.

### 권장 (Should)

- **S1**: 다이얼로그에 투명도 슬라이더(0.1~1.0) + 각도 입력(기본 45). 빈 텍스트는 적용 거부.

### 범위 외 (Won't)

- **이미지 워터마크** — 파일 선택·스케일링·배치 복잡, 후속 사이클(`WatermarkImage` op로 확장 가능한 구조).
- 위치 옵션(중앙 외 모서리/타일링) — 중앙 고정. 후속.
- 페이지 범위 부분 지정(예: 3-7p) — 현재/전체만. text-export-range 사이클의 범위 파서를 나중에 공유 가능.
- 워터마크 일괄 제거(이미 적용된 것) — op는 history라 undo로 제거(저장 전). 저장 후 제거는 범위 외.

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 271+ 통과.
- [ ] `WatermarkText` to_dict→from_dict 전 필드 보존.
- [ ] apply 후 저장 파일에서 워터마크 텍스트 검색됨, 본문 콘텐츠 유지.
- [ ] 전체 범위 → 모든 페이지에 워터마크.
- [ ] preview(PREVIEW)=save(SAVE) 등가(applicator 단일 경로).
- [ ] i18n en/ko 동수.
- [ ] mypy strict(operations 게이트) 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/operations/watermark.py` | 신규 `WatermarkText` op |
| `app/operations/base.py` | `from_dict` 분기 |
| `app/operations/applicator.py` | watermark pass(마지막) |
| `app/operations/__init__.py`, `app/model.py` | export |
| `app/watermark_dialog.py` | 신규 다이얼로그 |
| `app/controller.py` | `add_watermark` (범위 루프) |
| `app/handlers/dialog_handlers.py` | 다이얼로그 연결 |
| `app/ui_menu.py` | Tools 메뉴 액션 |
| `app/i18n/en.json`, `ko.json` | 키 |
| `tests/test_watermark.py`, `tests/test_op_serialization.py` | 신규/확장 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| TextWriter morph 좌표/회전 부정확 | probe로 45도 중앙 배치 검증. 테스트가 저장 파일 텍스트 존재로 고정 |
| 전 페이지 N개 op로 history 비대 | batch-replace 동일 패턴(허용된 선례). 단일 op 전페이지 적용은 applicator 구조 변경이라 범위 외 |
| watermark pass 순서 오류(콘텐츠에 가림) | 마지막 pass로 배치(section removal 후) — 항상 최상단 |
| op 직렬화 하위호환 | 신규 op 타입 추가만, 기존 불변. round-trip 테스트 |
| opacity/color strict 타이핑 | operations 게이트(strict) — 명시 타입 |

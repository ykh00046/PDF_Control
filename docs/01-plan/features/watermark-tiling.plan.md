# Watermark Tiling - Plan

> **Summary**: 텍스트/이미지 워터마크를 페이지 중앙 1개 대신 **격자로 반복(타일링)** 배치하는 옵션 추가. 기존 `WatermarkText`/`WatermarkImage`에 `tile` 플래그 — 신규 op 없이 확장
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-15
> **Status**: ✅ Completed (2026-06-15, 매치율 100%, 298 passed)
> **Cycle**: watermark-tiling
>
> ## 결과 (Report)
> tile 미사용 시 동작 완전 불변(centered 1개, 직렬화 하위호환 — from_dict가
> `tile` 기본 False). 이미지 타일은 첫 insert xref 재사용으로 1회만 embed.
> preview=save·DRY(`_draw_at` 공유) 보존. 신규 테스트 +3(round-trip tile,
> tiled>centered, 이미지 tile 렌더). ruff check/format 0, mypy strict 0,
> i18n 316/316. 갭 분석 4플래그(tile=False 불변/xref 1회/preview=save/DRY) 전부 안전.

---

## 1. 배경 (Why)

watermark/image-watermark는 페이지 중앙에 워터마크 1개만 배치. "전면 반복" 워터마크(문서 전체에 옅게 깔리는 보안 패턴)는 흔한 니즈로 watermark 후속 Won't에 명시됐다.

### 실측 (probe)

- 텍스트 3×3 격자: 셀마다 별도 `TextWriter`+morph → 저장 후 9개 검색됨(누적 OK).
- 이미지 격자: 같은 pixmap을 격자 위치마다 `insert_image` → 배치됨. **첫 insert의 xref를 재사용**(`insert_image(rect, xref=...)`)하면 이미지는 1번만 embed(파일 크기 절약).

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `WatermarkText`/`WatermarkImage`에 `tile: bool = False` 추가. `apply`가 tile이면 페이지를 자동 격자로 나눠 각 셀에 배치, 아니면 기존 중앙 1개. 중앙/타일이 그리기 로직을 공유(헬퍼 추출, DRY). `to_dict`/`from_dict`에 `tile`(기본 False — 하위호환).
- **M2**: 격자 간격은 워터마크 크기 기반 자동 — `config.TILE_SPACING_FACTOR`(예 1.8)로 셀 크기 = max(워터마크폭, 크기)×factor, cols/rows = floor(page변/셀). 텍스트는 회전 후에도 안 겹치게 여유.
- **M3**: 이미지 타일은 첫 `insert_image` xref를 재사용해 1회만 embed.
- **M4**: 다이얼로그(`WatermarkDialog`/`ImageWatermarkDialog`)에 "바둑판식 반복(타일)" 체크박스 → settings `tile` → controller `add_watermark`/`add_image_watermark`에 전달.
- **M5**: 테스트 — op round-trip(tile 필드), tile=True 시 다중 배치(텍스트 검색 ≥ N, 이미지 placement ≥ N), tile=False 기존 중앙 1개 유지, preview=save.

### 권장 (Should)

- **S1**: i18n `watermark.tile`/`image_watermark.tile` 키(en/ko).

### 범위 외 (Won't)

- 타일 간격/밀도 UI 노출 — 자동(상수). 후속.
- 대각선 오프셋(벽돌식 엇갈림) — 단순 격자. 후속.
- 페이지별 다른 타일 — 범위별 op는 기존 패턴 그대로.

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 295+ 통과.
- [ ] `WatermarkText`/`WatermarkImage` round-trip에 `tile` 보존.
- [ ] tile=True → 저장 파일에 워터마크 다중 배치(텍스트 search ≥ 4, 이미지 다중).
- [ ] tile=False → 기존 중앙 1개(회귀 0).
- [ ] preview=save 등가.
- [ ] i18n en/ko 동수 + tr() 참조 검증 통과.
- [ ] ruff check/format 0, mypy strict(operations) 0.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/config.py` | `TILE_SPACING_FACTOR` 상수 |
| `app/operations/watermark.py` | `tile` 필드 + apply 격자 분기 + 헬퍼 |
| `app/operations/base.py` | from_dict `tile` |
| `app/controller.py` | add_watermark/add_image_watermark `tile` 파라미터 |
| `app/watermark_dialog.py`, `app/image_watermark_dialog.py` | tile 체크박스 |
| `app/handlers/dialog_handlers.py` | settings tile 전달 |
| `app/i18n/*.json` | tile 키 |
| `tests/test_watermark.py`, `tests/test_op_serialization.py` | tile 테스트 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 타일이 너무 빽빽/성김 | spacing factor 측정·조정, 셀당 1개 |
| 이미지 다중 embed로 파일 비대 | xref 재사용(probe 확인) |
| 회전 텍스트 타일 겹침 | 셀 크기에 회전 여유(factor) |
| op 직렬화 하위호환 | tile 기본 False, round-trip 테스트 |
| preview=save | applicator 단일 Pass 5 경로(기존) |

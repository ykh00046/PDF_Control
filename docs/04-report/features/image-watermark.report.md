# Image Watermark - Completion Report

> **Summary**: 이미지(로고/스탬프)를 페이지에 반투명 오버레이로 추가하는 기능. watermark(텍스트) 후속. insert_image 제약(opacity 없음, 90단위 회전)을 Pixmap 알파 우회로 해결. 매치율 100%, **294 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-14
> **Cycle**: image-watermark
> **Match Rate**: 100%

---

## 1. 무엇이 추가됐나

Tools → "Add Image Watermark…"(Ctrl+Shift+I)로 PNG/JPG 등 이미지를 페이지에 반투명으로 얹는다. 파일 선택·투명도·크기(페이지 폭 대비 %)·회전(0/90/180/270)·적용범위(현재/전체)를 조절한다. 텍스트 워터마크와 같은 비파괴 오버레이라 미리보기·저장에 동일하게 반영된다.

## 2. PyMuPDF 제약과 해결 (probe + Context7)

`insert_image`는 텍스트 워터마크의 `TextWriter`와 API가 다르고 제약이 컸다:
- **opacity 파라미터 없음**(alpha는 deprecated/ignored) → **Pixmap 알파 채널 우회**: `fitz.Pixmap(path)` → 알파 없으면 `fitz.Pixmap(pix, 1)` → `set_alpha(bytes([int(opacity*255)] * w*h))` → `insert_image(pixmap=)`.
- **회전 0/90/180/270만**(rotate=45 → bad rotate value) → 콤보로 90단위 제한. 텍스트 워터마크의 임의 각도(morph)와 **비대칭**이며 코드·UI·문서에 명시.

둘 다 probe로 실측 후 설계에 반영 — 잘못된 가정으로 구현했다면 런타임 실패했을 부분.

## 3. 구현 요지

- **`WatermarkImage` op** (watermark.py): Pixmap 알파 우회 + 페이지 중앙 scale 배치. **파일 부재/로드 실패는 no-op**(로그) — op 생성 후 이미지 파일이 이동/삭제돼도 렌더가 깨지지 않음.
- **applicator Pass 5**: `(WatermarkText, WatermarkImage)` 둘 다 — 마지막 pass, SAVE/PREVIEW 공유.
- **컨트롤러 Qt-free**: `add_image_watermark(page_indices, ...)` 범위별 op(watermark 패턴). 별도 `ImageWatermarkDialog`(파일 미선택 시 거부).

## 4. 검증

- 전체 **294 passed** (287 + 신규 7: op round-trip 2 + 이미지 렌더/본문보존·파일부재 no-op·preview=save·전페이지·다이얼로그 파일요구 5).
- 6개 가드레일(preview=save·마지막 pass·파일부재 no-op·opacity 알파 우회·rotate 90단위·직렬화 하위호환·Qt-free) 전부 갭 분석 코드 레벨 통과.
- mypy strict(operations) 0 에러, i18n 309/309.

## 5. 다음 (로드맵)

- pyproject/ruff, validate_i18n 강화(tr() 참조 키 검증). 풀 async-save는 보류.
- 워터마크 후속: 타일링/모서리 배치, 텍스트/이미지 다이얼로그 공통 베이스 추출(현재 별도) — 필요 시.

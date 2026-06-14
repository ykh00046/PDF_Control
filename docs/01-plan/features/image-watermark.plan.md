# Image Watermark - Plan

> **Summary**: 이미지(로고 등)를 페이지에 반투명 오버레이로 추가. watermark(텍스트) 사이클의 후속 — `WatermarkImage` op. opacity는 Pixmap 알파로 우회, 회전은 90단위만(insert_image 제약)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%, 294 passed)
> **Cycle**: image-watermark

---

## 1. 배경 (Why)

watermark 사이클에서 "이미지 워터마크는 `WatermarkImage` op로 확장 가능"으로 남긴 후속. 회사 로고, 스탬프 이미지 등을 페이지에 얹는 니즈.

### 실측 (probe + Context7 — 설계 확정 + 제약 발견)

`insert_image`는 텍스트 워터마크의 `TextWriter`와 **API가 다르고 제약이 크다**:
- **opacity 파라미터 없음** (`alpha`는 deprecated/ignored). → 반투명은 **Pixmap 알파 채널로 우회**: `fitz.Pixmap(path)` → `fitz.Pixmap(pix, 1)`(알파 추가) → `set_alpha(bytes([int(opacity*255)] * w*h))` → `insert_image(pixmap=)`. probe로 반투명 삽입 + 본문 보존 검증.
- **회전 0/90/180/270만** (`rotate=45` → `bad rotate value`). 텍스트 워터마크의 임의 각도(morph)와 **비대칭** — 이미지는 90단위만.
- 비파괴 오버레이 → 텍스트 워터마크와 같은 applicator Pass 5 공유, preview=save 자동.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `operations/watermark.py`에 `WatermarkImage(Operation)` 추가 — page_index, image_path, opacity(0-1), scale(페이지 폭 대비 0-1), rotate(0/90/180/270). `apply(page)`가 Pixmap 알파 우회로 반투명 적용 + 페이지 중앙 배치(scale로 크기, 비율 유지). 파일 부재/로드 실패 시 no-op(로그) — 렌더 안 깨짐. `to_dict`/`from_dict`.
- **M2**: `base.from_dict` 분기 + applicator Pass 5를 `(WatermarkText, WatermarkImage)` 둘 다 포함. SAVE/PREVIEW 공유.
- **M3**: `app/image_watermark_dialog.py` + `controller.add_image_watermark(page_indices, ...)` — 파일 선택·opacity·scale·rotate·적용범위(현재/전체). 범위별 op 생성(watermark 패턴, Qt-free 컨트롤러). Tools 메뉴 "Add Image Watermark…".
- **M4**: i18n(en/ko) 키. 누락 0.
- **M5**: 테스트 — op round-trip, apply 렌더(저장 후 이미지 존재 + 본문 유지), 파일 부재 no-op, opacity Pixmap 알파 적용, 컨트롤러 범위(현재/전체), preview=save.

### 권장 (Should)

- **S1**: 다이얼로그에서 이미지 파일 미선택 시 적용 거부. opacity 슬라이더 + scale 스핀 + rotate 콤보(0/90/180/270).

### 범위 외 (Won't)

- **임의 각도 회전** — insert_image가 90단위만(probe 확인). 텍스트 워터마크와 비대칭, 제약 명시.
- 타일링/모서리 배치 — 중앙 고정. 후속.
- 이미지 바이트 op 내장(직렬화 비대) — 경로 저장. 파일 이동/삭제 시 apply no-op.
- 텍스트/이미지 워터마크 다이얼로그 통합 — MVP는 별도 다이얼로그(단순). 공통 베이스 추출은 후속.

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 287+ 통과.
- [ ] `WatermarkImage` to_dict→from_dict 전 필드 보존.
- [ ] apply 후 저장 파일에 이미지 존재 + 본문 텍스트 유지.
- [ ] opacity 적용(Pixmap 알파, 반투명 삽입 성공).
- [ ] 파일 부재 → no-op(예외 0, 렌더 정상).
- [ ] 컨트롤러 전체 범위 → 모든 페이지.
- [ ] preview=save 등가.
- [ ] i18n en/ko 동수.
- [ ] mypy strict(operations 게이트) 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/operations/watermark.py` | `WatermarkImage` op 추가 |
| `app/operations/base.py` | `from_dict` 분기 |
| `app/operations/applicator.py` | Pass 5에 WatermarkImage 포함 |
| `app/model.py` | export |
| `app/image_watermark_dialog.py` | 신규 다이얼로그 |
| `app/controller.py` | `add_image_watermark` |
| `app/handlers/dialog_handlers.py` | 다이얼로그 연결 |
| `app/ui_menu.py` | Tools 메뉴 액션 |
| `app/i18n/en.json`, `ko.json` | 키 |
| `tests/test_watermark.py`, `tests/test_op_serialization.py` | 확장 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| insert_image opacity 미지원 | Pixmap 알파 우회(probe 검증) |
| 임의 회전 불가 | 90단위 콤보로 제한, plan/UI 명시 |
| 이미지 파일 이동/삭제로 apply 실패 | apply 내 try/except → 로그 + no-op(렌더 비파괴) |
| 큰 이미지 메모리/파일 크기 | keep_proportion + scale 축소, 저장 deflate. 극단 크기는 범위 외 |
| op 직렬화 하위호환 | 신규 op 타입만, 기존 불변. round-trip 테스트 |
| Pixmap 알파 strict 타이핑 | operations 게이트 — 명시 처리, fitz Any 허용 정책 |

# Image Watermark - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (M1-M5 + S1), 6개 가드레일 전부 통과, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-14
> **Design**: [image-watermark.design.md](../../02-design/features/image-watermark.design.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 WatermarkImage op (Pixmap 알파 우회, 중앙·scale 배치, 파일부재/로드실패 no-op, to_dict) | `watermark.py:74-124` | ✅ |
| M2 from_dict 분기 + applicator Pass 5 `(WatermarkText, WatermarkImage)` | `base.py:89-96`, `applicator.py:41,194` | ✅ |
| M1 export (model facade + controller) | `model.py:21,32`, `controller.py:3` | ✅ |
| M3 ImageWatermarkDialog (파일픽커/opacity/scale/rotate 콤보/scope, no-file reject) | `image_watermark_dialog.py` | ✅ |
| M3 controller.add_image_watermark (Qt-free 루프) + 핸들러 인덱스 계산 | `controller.py:233-251`, `dialog_handlers.py:247-284` | ✅ |
| M3 ui_menu Ctrl+Shift+I | `ui_menu.py:144-147` | ✅ |
| M4 i18n en/ko 13키 (309/309) | `en/ko.json:178-211` | ✅ |
| M5 op round-trip + watermark 테스트 5종 | `test_op_serialization.py`, `test_watermark.py` | ✅ |

## 가드레일 점검 (6개 전부 통과)

- **(a) preview=save + 마지막 Pass** — Pass 5 mode 무분기, section removal 이후. SAVE/PREVIEW 이미지 1개 테스트.
- **(b) 파일 부재 깨끗한 no-op** — exists 체크 + except 둘 다 warning+return, 예외 0.
- **(c) opacity Pixmap 알파 우회** — insert_image에 opacity/alpha 인자 없이 set_alpha로 우회(probe 일치).
- **(d) rotate 90단위 제한** — 콤보 0/90/180/270만, 주석에 insert_image 한계 명시(텍스트와 비대칭).
- **(e) 직렬화 하위호환** — 신규 op 타입만, 기존 분기 불변, legacy 기본값 복원.
- **(f) 컨트롤러 Qt-free** — add_image_watermark는 page_indices 인자만, 범위 계산은 핸들러.

## 검증

- 전체 **294 passed**, mypy strict(operations) 0 에러, i18n 309/309.
- 차이: 누락 0, 무단 변경 0.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.

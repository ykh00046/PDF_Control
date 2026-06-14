# Watermark - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (M1-M5 + S1), 5개 플래그 전부 안전, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-14
> **Design**: [watermark.design.md](../../02-design/features/watermark.design.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 WatermarkText op (TextWriter+morph, 중앙, 빈텍스트 no-op, to_dict) | `operations/watermark.py:15-61` | ✅ |
| M2 from_dict 분기 + applicator Pass 5(section removal 이후, 모드 무분기) | `base.py:79-88`, `applicator.py:41,190-195` | ✅ |
| M1 export (model facade) | `model.py` import + __all__ | ✅ |
| M3 WatermarkDialog (text/size/opacity/angle/color/scope, 빈텍스트 reject) | `watermark_dialog.py` | ✅ |
| M3 controller.add_watermark (Qt-free, 범위 루프) + handler 인덱스 계산 | `controller.py:210-231`, `dialog_handlers.py:218-244` | ✅ |
| M3 ui_menu Ctrl+Shift+W | `ui_menu.py:139-142` | ✅ |
| M4 i18n en/ko 12키 (293/293) | `en.json`, `ko.json` | ✅ |
| M5 op round-trip + watermark 7 + dialog smoke 2 | `test_op_serialization.py`, `test_watermark.py` | ✅ |
| S1 슬라이더+각도+빈텍스트 거부 | `watermark_dialog.py` | ✅ |

## 플래그 점검 (전부 안전)

- **(a) preview=save** — Pass 5는 mode 분기 없이 무조건 실행. 양 모드 검색 가능 테스트로 고정.
- **(b) 마지막 pass** — section removal 다음, return 직전. 다른 콘텐츠(래스터 포함) 위에 그려짐.
- **(c) controller Qt-free** — add_watermark는 page_indices 인자만, viewer/widget 미참조. 현재 페이지 계산은 핸들러.
- **(d) 직렬화 하위호환** — 신규 op 타입만 추가, 기존 4개 분기 불변. legacy payload 기본값 복원 테스트.
- **(e) 빈 텍스트 가드 양쪽** — op 레벨(`if not self.text: return`) + dialog 레벨(strip→reject), 둘 다 테스트.

## 검증

- 전체 **281 passed**, mypy strict(operations) 0 에러, i18n 293/293.
- 차이: 누락 0, 무단 변경 0. 사소한 UX 보강(실시간 % 라벨, hex 라벨)은 설계 의도 범위.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.

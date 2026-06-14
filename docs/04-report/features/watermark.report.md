# Watermark - Completion Report

> **Summary**: 페이지에 반투명·대각선 텍스트 워터마크를 얹는 신규 기능. `TextWriter`+morph 기반 비파괴 오버레이 op로 operations 파이프라인에 통합. 매치율 100%, **281 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-14
> **Cycle**: watermark
> **Match Rate**: 100%

---

## 1. 무엇이 추가됐나

Tools → "Add Watermark…"(Ctrl+Shift+W)로 "CONFIDENTIAL", "DRAFT" 같은 텍스트 워터마크를 페이지에 얹는다. 텍스트·글자크기·색상·투명도·각도(대각선)를 다이얼로그에서 조절하고, 현재 페이지 또는 전체 페이지에 적용한다. 미리보기에서도 동일하게 보이며 저장 결과에 반영된다.

## 2. 구현 요지

- **`WatermarkText` op** (`operations/watermark.py`): `fitz.TextWriter(opacity, color)` + 페이지 중앙 배치 + `write_text(morph=(pivot, Matrix(angle)))`로 임의 각도·반투명 렌더. `insert_textbox`의 rotate가 0/90/180/270만 지원하는 한계를 probe로 확인하고 TextWriter+morph를 채택. **비파괴**(콘텐츠 추가만)라 SAVE/PREVIEW가 같은 apply를 공유 → preview=save 자동.
- **applicator Pass 5**: section removal 다음, 가장 마지막 pass — 다른 모든 콘텐츠(섹션 제거 래스터 포함) 위에 그려진다. 모드 분기 없음.
- **컨트롤러 통합**: `add_watermark(page_indices, ...)`가 범위 페이지마다 op 생성(batch-replace 패턴). Qt 비의존 — 현재 페이지/전체 범위 계산은 핸들러가 담당.
- **다이얼로그**: 텍스트·폰트크기·투명도 슬라이더·각도·색상 피커·적용범위. 빈 텍스트는 op·dialog 양쪽에서 거부.

## 3. 검증

- 전체 **281 passed** (271 + 신규 10: op round-trip 2 + watermark 동작/컨트롤러 6 + 다이얼로그 스모크 2).
- preview=save 등가, 마지막 pass 보장, 컨트롤러 Qt-free, 직렬화 하위호환, 빈 텍스트 가드 양쪽 — 갭 분석 5개 플래그 전부 코드 레벨 안전.
- mypy strict(operations) 0 에러, i18n 293/293.

## 4. 확장 여지 (의도적 Won't)

- **이미지 워터마크** — `WatermarkImage` op로 확장 가능한 구조. 파일 선택·스케일링·배치 복잡, 후속.
- 위치 옵션(모서리/타일링) — 중앙 고정. 후속.
- 페이지 범위 부분 지정 — 현재/전체만. text-export-range의 범위 파서를 나중에 공유 가능.

## 5. 다음 (로드맵)

- text-export-range, pyproject/ruff, 이미지 워터마크. 풀 async-save는 보류.

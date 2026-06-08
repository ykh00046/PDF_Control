# Design: model-restructure

> **Status**: Active
> **Created**: 2026-06-02
> **Plan**: `docs/01-plan/features/model-restructure.plan.md`

## 1. 모듈 분해 설계

`app/model.py`(690줄) → 관심사별 모듈 + facade.

```
app/
├── model.py                       # ★ facade: 전 심볼 재노출 (하위호환)
├── document_model.py              # WordBox, PageModel  (값객체 + 페이지 캐시)
├── text_metadata.py               # _extract_text_metadata
├── document_session.py            # DocumentSession (QObject)
└── operations/
    ├── __init__.py                # (기존)
    ├── applicator.py              # (기존, 무수정)
    ├── base.py                    # Operation(ABC) + from_dict 팩토리
    ├── redact.py                  # RedactDelete, RedactReplace
    ├── crop.py                    # CropMargins
    └── remove_section.py          # RemoveSectionAsImage (apply 분해)
```

### 1.1 의존 방향 (순환 없음)

```
model.py (facade)
  ├─→ operations.base ──────────────┐
  ├─→ operations.redact ─→ base     │
  ├─→ operations.crop   ─→ base     │
  ├─→ operations.remove_section ─→ base, config, logger
  ├─→ text_metadata ─→ logger, config
  ├─→ document_model ─→ text_utils
  └─→ document_session ─→ operations.base, operations.remove_section,
                          pdf_engine, operations_service
```

- `operations.base.Operation.from_dict`는 하위클래스를 **메서드 내부 지연 import**로 참조 → base ↔ 하위 모듈 순환 회피(현행 동일 전략).
- `applicator.py`의 `from app.model import ...`(함수 내부 지연 import)는 facade를 통해 그대로 해소 → **applicator 무수정**.

### 1.2 facade(`model.py`) 재노출 심볼

```python
from app.operations.base import Operation
from app.operations.redact import RedactDelete, RedactReplace
from app.operations.crop import CropMargins
from app.operations.remove_section import RemoveSectionAsImage
from app.text_metadata import _extract_text_metadata
from app.document_model import WordBox, PageModel
from app.document_session import DocumentSession

__all__ = [
    "WordBox", "Operation", "RedactDelete", "RedactReplace",
    "CropMargins", "RemoveSectionAsImage", "PageModel",
    "DocumentSession", "_extract_text_metadata",
]
```

## 2. `RemoveSectionAsImage.apply()` 분해 설계

현행 1개 메서드(약 160줄, 7책임) → 오케스트레이터 + 헬퍼.

| 헬퍼 | 책임 | 입력 → 출력 |
|------|------|-------------|
| `_resolve_render_dpi(page_rect)` | 메모리 추정 + DPI 자동캡/경고 | page_rect → `(zoom, matrix)` |
| `_compute_clips(page_rect)` | 상/하단 클립 계산 + 빈페이지 검증 | page_rect → `[clip,…]` (비어있지 않은 것만) |
| `_render_clip(page, matrix, clip)` | 단일 클립 렌더 + 색공간/JPEG 변환 | → `PIL.Image` |
| `_merge_vertical(images)` | 수직 병합 + 병합 메모리 가드 | imgs → `(PIL.Image, pixel_width)` |
| `_encode(image)` | PNG/JPEG 바이트 인코딩 | image → `bytes` |
| `_rebuild_page(doc, idx, page_rect, combined, zoom)` | 새 페이지 생성·이미지 삽입·원본 삭제 | (부수효과) |
| `apply(page)` | 위 단계 오케스트레이션 + 최종 로그 | — |

### 2.1 동작 보존 핵심 불변식

- DPI 자동캡 공식·임계값(`remove_section_dpi_cap_mb`, `_large_warn_mb`, `merge_warn_mb`, `merge_abort_mb`) 그대로.
- 빈 결과 페이지 → `ValueError`, 병합 초과 → `MemoryError` 동일.
- 색공간 매핑(`n==1→L`, `alpha→RGBA`, else `RGB`) + JPEG시 `RGBA→RGB` 동일.
- 새 페이지 높이 `combined_height / zoom`, 원본 삭제 순서 동일.
- 최종 INFO 로그 포맷 동일.

## 3. 테스트 전략

- **안전망**: `test_remove_section.py`(5), `test_page_management.py`(34) — 리팩토링 전후 동일 통과.
- **import 스모크**: `from app.model import (전 심볼)` + `Operation.from_dict` 왕복(round-trip) 직렬화.
- **회귀 가드**: 전체 영향 테스트군 실패 수가 베이스라인(8) 이하 유지.

## 4. 롤백 전략

순수 구조 변경이므로, 문제 시 신규 모듈 삭제 + `model.py` 원복으로 즉시 롤백 가능(Git 미사용 환경이므로 원본 내용은 본 설계+Plan에 구조 기록).

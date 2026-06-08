# Plan: model-restructure

> **Status**: Active
> **Created**: 2026-06-02
> **Owner**: PDCA (auto)
> **Level**: Starter

## 1. 배경 / 문제 정의

`app/model.py`가 690줄로 비대해져 **단일 책임 원칙(SRP)**을 위반한다. 한 파일에 서로 다른 관심사가 혼재한다:

- 값 객체: `WordBox`
- 연산 도메인: `Operation`(ABC) + `RedactDelete` / `RedactReplace` / `CropMargins` / `RemoveSectionAsImage`
- 텍스트 메타데이터 추출: `_extract_text_metadata`
- 페이지 캐시: `PageModel`
- 문서 세션/히스토리/페이지관리: `DocumentSession`(QObject)

특히 `RemoveSectionAsImage.apply()`는 **약 160줄(L179–340)**의 단일 메서드로, 메모리 추정·DPI 자동캡·클립 계산·렌더링·병합·인코딩·페이지 재생성까지 7가지 책임을 한 메서드에 담아 가독성·테스트성이 매우 낮다.

## 2. 목표 (Goal)

1. `model.py`를 관심사별 모듈로 분해한다.
2. `RemoveSectionAsImage.apply()`를 단일 책임 헬퍼들로 분해한다.
3. **공개 API 100% 하위호환 유지** — `from app.model import ...`가 그대로 동작해야 한다.

## 3. 비목표 (Non-Goal)

- 동작/출력 변경 없음(순수 구조 리팩토링).
- 기존에 실패하던 텍스트 자동맞춤(`_insert_text_with_autofit`) 관련 8개 테스트 수정은 범위 밖(별도 이슈).
- 신규 기능 추가 없음.

## 4. 제약 조건 (Constraints)

`app.model`의 공개 심볼은 외부 8개 모듈 + 11개 테스트가 의존한다:

| 심볼 | 의존처 |
|------|--------|
| `DocumentSession` | controller, viewer, state_handlers, tests |
| `Operation` | controller, render_worker, tests |
| `RedactDelete`/`RedactReplace` | controller, edit_handlers, applicator, tests |
| `CropMargins` | controller, applicator |
| `RemoveSectionAsImage` | controller, applicator, tests |
| `_extract_text_metadata` | edit_handlers, applicator |
| `WordBox`, `PageModel` | 내부 |

→ **`model.py`를 facade(재노출) 모듈로 유지**하여 import 경로 변경을 0건으로 만든다.

## 5. 성공 기준 (Acceptance Criteria)

- [ ] `model.py` ≤ ~60줄(순수 facade), 각 신규 모듈 단일 책임.
- [ ] `RemoveSectionAsImage.apply()` ≤ ~40줄, 책임별 헬퍼로 분리.
- [ ] 안전망 테스트(`test_remove_section` 5 + `test_page_management` 34 = 39개) 전부 통과 유지.
- [ ] 베이스라인 대비 신규 실패 0건(기존 8 실패는 동일하게 유지).
- [ ] `from app.model import` 사용처 무수정.
- [ ] Gap 분석 Match Rate ≥ 90%.

## 6. 리스크

| 리스크 | 완화 |
|--------|------|
| 순환 import (`Operation.from_dict`가 하위클래스 참조) | `from_dict` 내부 지연 import 유지 |
| facade 누락 심볼로 ImportError | 분해 후 전 심볼 재노출 + import 스모크 |
| 동작 회귀 | 39개 안전망 테스트 전·후 비교 |

## 7. 베이스라인 (측정값, 2026-06-02)

- 환경: `py -3.13`, PyMuPDF 1.26.6
- 영향 테스트군: **58 passed / 8 failed**
- 8 실패는 전부 `_insert_text_with_autofit`(치환·저장·미리보기 동등성) — 사전 존재, 본 작업 범위 밖.

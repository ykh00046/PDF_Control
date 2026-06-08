# Completion Report: model-restructure

> **Status**: ✅ Completed
> **Date**: 2026-06-02
> **PDCA**: Plan → Design → Do → Check(100%) → Act(iterate ×1) → QA → Report
> **Match Rate**: 100% · **회귀**: 0건

## 1. 요약

690줄 단일 파일 `app/model.py`를 **7개 단일 책임 모듈 + 하위호환 facade**로 분해하고, 160줄짜리 `RemoveSectionAsImage.apply()`를 **17줄 오케스트레이터 + 6개 헬퍼**로 재구성했다. 공개 API는 100% 보존되어 import 사용처(8 모듈 + 11 테스트) 무수정. mypy strict 통과, 안전망 39개 테스트 전부 green.

## 2. 변경 내역

### 신규 모듈
| 파일 | 책임 | 라인 |
|------|------|------|
| `app/operations/base.py` | `Operation` ABC + `from_dict` 팩토리 | 76 |
| `app/operations/redact.py` | `RedactDelete`, `RedactReplace` | 57 |
| `app/operations/crop.py` | `CropMargins` | 39 |
| `app/operations/remove_section.py` | `RemoveSectionAsImage`(+6 헬퍼) | 201 |
| `app/text_metadata.py` | `_extract_text_metadata` | 61 |
| `app/document_model.py` | `WordBox`, `PageModel` | 50 |
| `app/document_session.py` | `DocumentSession` | 293 |
| `app/model.py` | facade(재노출 전용) | 690 → 33 |

### `apply()` 분해
`_resolve_render_dpi` → `_compute_clips` → `_render_clip` → `_merge_vertical` → `_encode` → `_rebuild_page` 의 6단계로 분리. 메모리 가드/DPI 자동캡/색공간 처리/페이지 재생성 불변식 보존.

## 3. PDCA 사이클 기록

| Phase | 내용 | 결과 |
|-------|------|------|
| **Plan** | 문제정의·제약(공개API 8모듈+11테스트 의존)·수용기준 | `01-plan/.../model-restructure.plan.md` |
| **Design** | 모듈 분해도·의존방향(순환無)·apply 분해표 | `02-design/.../model-restructure.design.md` |
| **Do** | 7모듈 생성 + facade 전환 + apply 분해 | 8 파일 |
| **Check** | 설계 13/13 구현, mypy 회귀 1건 발견 | Match 100% |
| **Act(iterate)** | strict 타입주석 보강(20 err→0) | mypy clean |
| **QA** | 안전망39 + 전체스위트 + 스모크 | 회귀 0 |
| **Report** | 본 문서 | — |

## 4. 검증 증거

```
mypy -p app.operations         → Success: no issues found in 8 source files
pytest test_remove_section + test_page_management  → 39 passed
import 스모크 + from_dict 왕복 4종 + 헬퍼 6종      → ALL PASSED
전체 스위트                    → 116 passed / 11 failed (= 베이스라인, 회귀 0)
```

## 5. 핵심 학습 (Learnings)

1. **모듈 이동 = 검사 정책 이동**: `model.py`(strict 면제)의 클래스를 `app.operations.*`(strict 적용)로 옮기는 순간 mypy strict 대상이 되어 20개 에러가 드러났다. 리팩토링 시 **대상 디렉터리의 린트/타입 정책**을 먼저 확인할 것.
2. **facade 패턴이 대규모 분해의 안전한 기본값**: 공개 API 재노출만으로 19개 의존처를 무수정 유지 → 블라스트 반경 0.
3. **안전망 우선 확보**: 분해 전 39개 그린 테스트를 기준선으로 잡아 회귀를 즉시 판별.

## 6. 🔴 후속 권고 (별도 PDCA 필요)

**[Critical] `applicator.py`의 `page.get_text_length` 호출이 현재 PyMuPDF에서 깨짐**
- 위치: `app/operations/applicator.py:434`
- 증상: `AttributeError: 'Page' object has no attribute 'get_text_length'`
- 영향: **텍스트 치환(Replace) 저장·미리보기 전체 기능 동작 불가** (11개 테스트 실패)
- 원인: `get_text_length`가 `fitz.Page` 메서드에서 모듈 함수 `fitz.get_text_length(text, fontname, fontsize)`로 이전됨(PyMuPDF 1.26+).
- 권고: `/pdca plan textlength-api-fix` 로 별도 사이클 — 호출부를 모듈 함수 또는 `page.get_textbox`/`Font.text_length`로 교체.

## 7. 산출물

- 신규/수정 소스 8개 (위 표)
- PDCA 문서 4종: plan / design / analysis / report

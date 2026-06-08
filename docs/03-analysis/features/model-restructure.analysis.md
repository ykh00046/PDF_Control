# Analysis (Check): model-restructure

> **Status**: Completed
> **Date**: 2026-06-02
> **Design**: `docs/02-design/features/model-restructure.design.md`
> **Match Rate**: **100%** (설계 항목 13/13 구현)

## 1. 설계 대비 구현 검증 (Gap)

| # | 설계 항목 | 구현 | 상태 |
|---|-----------|------|------|
| 1 | `model.py` → facade(재노출) | 33줄, 전 심볼 재노출 | ✅ |
| 2 | `document_model.py` (WordBox, PageModel) | 50줄 | ✅ |
| 3 | `text_metadata.py` (`_extract_text_metadata`) | 61줄 | ✅ |
| 4 | `document_session.py` (DocumentSession) | 293줄 | ✅ |
| 5 | `operations/base.py` (Operation+from_dict) | 76줄 | ✅ |
| 6 | `operations/redact.py` | 57줄 | ✅ |
| 7 | `operations/crop.py` | 39줄 | ✅ |
| 8 | `operations/remove_section.py` | 201줄 | ✅ |
| 9 | `apply()` 7책임 → 헬퍼 분해 | `apply()` 17줄 + 6 헬퍼 | ✅ |
| 10 | `from_dict` 지연 import(순환 회피) | 구현 | ✅ |
| 11 | 공개 API 재노출 + `__all__` | 9개 심볼 | ✅ |
| 12 | 동작 보존 | 안전망 39 green, 회귀 0 | ✅ |
| 13 | mypy strict 통과 | 8 files clean | ✅ |

**Match Rate = 13/13 = 100% (≥ 90% → Report 진행)**

## 2. 정량 효과

| 지표 | Before | After |
|------|--------|-------|
| `model.py` 라인 | 690 | 33 (-95%) |
| `RemoveSectionAsImage.apply()` 라인 | ~160 | 17 (-89%) |
| 단일 책임 모듈 수 | 1 | 7 + facade |
| `apply()` 책임 분리 | 1 메서드 7책임 | 6 헬퍼 + 오케스트레이터 |

## 3. 회귀 검증 (테스트 증거)

- 환경: `py -3.13`, PyMuPDF 1.26.6, `QT_QPA_PLATFORM=offscreen`
- **안전망 39개**(`test_remove_section` 5 + `test_page_management` 34): **전부 통과**
- **import 스모크**: 9개 심볼 import + `Operation.from_dict` 4종 왕복 직렬화 일치 + 헬퍼 6종 존재 → 통과
- **mypy strict**(`app.operations`): Success, no issues (8 files)
- **전체 스위트**: 116 passed / 11 failed

### Check 중 발견·해소한 회귀 (Iterate 1회)
- 연산 클래스를 `app.operations.*`(mypy strict 적용 패키지)로 이동 → strict 타입검사 대상 편입으로 **20개 타입 에러** 발생(원본 model.py는 strict 미적용).
- **조치**: base/redact/crop/remove_section에 반환·인자 타입 주석 추가, `_memory_limits` `cast`, PIL 타입은 `TYPE_CHECKING` 전방참조로 해결 → strict 통과.

## 4. 잔존 실패 11건 — 본 작업 범위 밖(사전 존재)

전부 동일 근원: `app/operations/applicator.py:434`의 `page.get_text_length(...)` 호출.

```
AttributeError: 'Page' object has no attribute 'get_text_length'
```

- `get_text_length`는 현재 PyMuPDF(1.26.6/1.27)에서 `fitz.Page`의 메서드가 아님(모듈 함수 `fitz.get_text_length`로 이전됨).
- 영향: 텍스트 **치환(Replace) 저장/미리보기** 경로 전체(test_smoke 3, test_regressions 3, test_preview_save 2, test_long_text_warning 3).
- **`applicator.py`는 본 PDCA에서 미수정** → 리팩토링과 무관한 사전 존재 결함.
- → 별도 이슈로 분리 권고(아래 Report 후속 제안 참조).

## 5. 결론

설계 100% 구현, 회귀 0건, 타입 안전성 확보. **Report 단계로 진행.**

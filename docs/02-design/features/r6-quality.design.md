# R6 Quality - Design

> **Summary**: controller 가드 헬퍼 / applicator 분해 / pdf_engine·document_session·model strict 전환의 구체 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-10, 매치율 100%)
> **Plan**: [r6-quality.plan.md](../../01-plan/features/r6-quality.plan.md)

---

## 1. M1 — controller 가드 헬퍼

### 헬퍼 시그니처

```python
def _run_session_action(
    self,
    action: str,                     # 로그용 동작명 ("rotate page" 등)
    func,                            # Callable[[DocumentSession], Any]
    *,
    applied: bool = True,            # 성공 시 operation_applied.emit()
    default=False,                   # 세션 없음/실패 시 반환값 (bool 계열 False, split은 [])
):
    if not self._session:
        return default
    try:
        result = func(self._session)
    except ValueError as e:          # 사용자 검증 오류 — 예상된 거부
        self.logger.warning(f"{action} rejected: {e}")
        self.error_occurred.emit(str(e))
        return default
    except Exception as e:           # 내부 오류 — 진짜 실패
        self.logger.error(f"Failed to {action}: {e}")
        self.error_occurred.emit(str(e))
        return default
    if applied:
        self.operation_applied.emit()
    return True if result is None else result
```

- 반환 규약: 세션 메서드가 `None` 반환(대부분의 mutate) → `True`. 값 반환(`split_document`의 list, `merge_pdfs`의 int) → 그 값. `merge_pdfs`는 controller 시그니처가 bool이므로 `bool(...)` 아님 — int는 truthy로 기존 `return True`와 호환되지만 **명시성 위해 controller 쪽은 기존대로 bool 반환 유지**: 위임식을 `return bool(self._run_session_action(...))`로 하면 split의 list가 깨지므로, split만 `default=[]`로 호출하고 나머지는 결과를 `is not default` 식 변환 없이 그대로 — 세션 mutate가 None→True라 자연 호환. `merge_pdfs`는 int 반환이 True로 평가되나 controller 시그니처상 bool이므로 `bool()` 래핑.

### 위임 대상 (10곳)

| controller 메서드 | applied | default | 비고 |
|---|---|---|---|
| `rotate_page` | True | False | |
| `delete_pages` | True | False | `ValueError("Cannot delete all pages")` → warning 경로 |
| `move_page` | True | False | |
| `insert_blank_page` | True | False | |
| `duplicate_pages` | True | False | |
| `merge_pdfs` | True | False | `bool()` 래핑 (세션은 int 반환) |
| `add_operation` | True | False | emit 메시지 `"Failed to add operation: {e}"` → `str(e)`로 통일 |
| `extract_pages` | False | False | 소스 불변 작업 |
| `split_document` | False | `[]` | list 반환 그대로 |
| `export_text` | False | False | |

- `load_document`(EncryptedPDFError 재던짐 + 세션 스왑), `close_document`(finally), `save_document`(재raise), `undo`/`redo`(예외 처리 없음) — **현행 유지**.
- import 정리: `fitz`, `RedactDelete`, `RedactReplace`, `CropMargins`, `RemoveSectionAsImage` 제거(파일 내 미사용, 외부 re-export 사용처 없음 — grep 확인 완료). `DocumentSession`/`Operation`은 타입힌트 사용으로 유지.

## 2. M2 — applicator 분해

### 상단 import 통합 (지연 import 6곳 제거)

```python
from app.operations.crop import CropMargins
from app.operations.redact import RedactDelete, RedactReplace
from app.operations.remove_section import RemoveSectionAsImage
from app.text_metadata import _extract_text_metadata
```

순환 안전 근거: 위 4개 모듈의 import 체인은 `fitz`/`app.config`/`app.logger`/`app.operations.base`에서 끝남(`app.model` 미참조 — 2026-06-10 확인). 기존 "avoiding circular import" 주석은 `app.model` 경유 시에만 해당.

### `_insert_text_with_autofit` 분해

```
_insert_text_with_autofit (오케스트레이터, ~55줄)
  ├─ _compute_text_layout(page, expanded_rect, text, fontname, fontfile,
  │                       initial_fontsize, wrap_enabled)
  │     -> (rect, final_fontsize, wrapped_lines, autofit_shrunk)
  │     # 기존 try 블록 본문: 한 줄 적합 검사 → wrap 시도(박스 확장) →
  │     # 폭 기준 이진탐색 축소 폴백. 실패 시 (rect, initial, 0, False) 반환
  │     # + warning 로그 (기존과 동일 메시지)
  │     └─ _shrink_fontsize_to_width(fit_font, text, initial, target) -> float
  │           # TEXT_AUTOFIT_ITERATIONS 이진탐색 (기존 코드 그대로)
  └─ insert_textbox → result<0 시 _insert_with_shrink (기존) →
     autofit_shrunk/wrapped 경고 append (기존 분기 그대로)
```

- 동작 불변 보증: 경고 코드·세버리티·detail 키, 폴백 순서, 이진탐색 반복수 모두 동일. `_wrap_line_count`는 변경 없음.
- `:608` 누락 빈 줄 수정.
- strict 유지: 분해 함수 전부 완전 어노테이션(`app.operations.*` 게이트 대상).

## 3. M3 — strict 확장

### mypy.ini

```ini
# r6-quality (2026-06-10): legacy-core strict promotion. warn_return_any is
# relaxed because fitz has no stubs (ignore_missing_imports) so fitz.Document
# returns surface as Any -- same policy as the app.operations gate.
[mypy-app.pdf_engine]
strict = True
warn_return_any = False

[mypy-app.document_session]
strict = True
warn_return_any = False

[mypy-app.document_model]
strict = True
warn_return_any = False

[mypy-app.model]
strict = True
```

(`document_model`은 document_session이 호출하는 `PageModel`/`WordBox`의
소유 모듈이라 함께 승격 — 어노테이션 5곳 보강으로 0 에러.)

(기존 `ignore_errors = True` 3블록 삭제)

### 코드 보강 요지

**`pdf_engine.py`**
- `Sequence` → `Sequence[Operation]` (`from app.operations.base import Operation`)
- `logger=None` → `logger: Optional[logging.Logger] = None`
- `encryption=None` → `encryption: Optional[EncryptionSettings] = None`
- `from app.operations_service import ...` → `from app.operations import ...` (셰임 우회)
- `apply_page_operations` 반환 `Optional[ApplyResult]`, `save_kwargs: Dict[str, Any]`

**`document_session.py`**
- 전 메서드 반환 어노테이션(`-> None` 등), `__init__ -> None`
- `save_document(encryption: Optional[EncryptionSettings] = None)`
- `_bind_document(... ) -> None`, `close() -> None`
- `from app.operations_service import ApplyMode` → `from app.operations import ApplyMode`
- `self.doc`은 fitz 무스텁로 Any — `close()`의 `self.doc = None` 패턴은 그대로(Any 허용)

**`model.py`** — 재-export만이라 추가 작업 없음 예상(측정 후 0 에러 확인).

### tests/test_mypy.py

`STRICT_LEAF_MODULES`에 `app/pdf_engine.py`, `app/document_session.py`, `app/model.py` 추가 + docstring에 r6 확장 기록.

## 4. S1 — controller 가드 테스트 (신규 `tests/test_controller_guard.py`)

| 테스트 | 검증 |
|---|---|
| `test_no_session_returns_default` | 세션 없이 `rotate_page` → False, `split_document` → [], emit 없음 |
| `test_value_error_emits_and_returns_default` | `delete_pages`(전체 삭제) → False + `error_occurred` 1회(str(e)) + 세션 유지 |
| `test_internal_error_emits` | 세션 메서드 monkeypatch로 RuntimeError → False + emit |
| `test_success_emits_applied` | `rotate_page` 성공 → True + `operation_applied` 1회 |
| `test_split_returns_paths` | 성공 시 list 그대로 반환, `operation_applied` 미발생 |

## 5. 검증 절차

1. M2 분해 후: `mypy -p app.operations` 0 에러 + wrap/warning 테스트.
2. M3: `mypy app/pdf_engine.py app/document_session.py app/model.py` 0 에러.
3. 전체 스위트 (Python 3.13) — 221+ 통과.

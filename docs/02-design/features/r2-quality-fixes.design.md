# R2 Quality Fixes - Design

> **Summary**: get_text_length API 교체 + mypy strict 게이트 확대의 구현 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: 🔄 In Progress
> **Plan**: [r2-quality-fixes.plan.md](../../01-plan/features/r2-quality-fixes.plan.md)

---

## 1. M1 — get_text_length API 교체

### 1.1 문제

`app/operations/applicator.py:432-441` 자동 폰트 맞춤(autofit) 바이너리서치 루프:

```python
for _ in range(TEXT_AUTOFIT_ITERATIONS):
    mid = (low + high) / 2
    text_width = page.get_text_length(            # ← AttributeError (PyMuPDF 1.26+)
        text, fontname=fontname, fontsize=mid, fontfile=fontfile
    )
```

PyMuPDF 1.26부터 `Page.get_text_length`가 제거됨. 대안:
- `fitz.get_text_length(text, fontname, fontsize)` — 모듈 함수. **단, base14 폰트만 지원, fontfile 미지원.**
- `fitz.Font(fontname=..., fontfile=...).text_length(text, fontsize=...)` — **base14·커스텀 폰트 모두 지원.** ← 채택

### 1.2 설계 결정

`fitz.Font`를 **루프 밖에서 1회 생성**하여 재사용(성능). fontfile이 있으면 우선, 없으면 base14 alias(fontname) 사용. Font 생성 실패 시 기존 `except` 경로가 그대로 받아 initial_fontsize로 폴백 → 안전.

```python
try:
    fit_font = fitz.Font(fontname=fontname, fontfile=fontfile) if fontfile \
        else fitz.Font(fontname=fontname)
    target_width = expanded_rect.width * TEXT_AUTOFIT_WIDTH_RATIO
    low, high = TEXT_AUTOFIT_MIN_FONT_SIZE, float(initial_fontsize)
    for _ in range(TEXT_AUTOFIT_ITERATIONS):
        mid = (low + high) / 2
        text_width = fit_font.text_length(text, fontsize=mid)
        if text_width > target_width:
            high = mid
        else:
            low = mid
    final_fontsize = low
except (RuntimeError, ValueError, TypeError, FileNotFoundError) as exc:
    self.logger.warning(...)
```

> `FileNotFoundError`를 except에 추가: 잘못된 fontfile 경로로 `fitz.Font`가 던질 수 있으므로 폴백 경로로 흡수.

### 1.3 영향 범위

- 호출부: `_insert_text_with_autofit` 내부 1곳. 외부 시그니처 불변 → 호출자 영향 없음.
- 복구 대상 테스트: test_smoke(3), test_regressions(3), test_preview_save_equivalence(2), test_long_text_warning(3) = 11개.

---

## 2. M3/S1 — mypy strict 게이트 확대

### 2.1 현재 상태 (mypy.ini)

`[mypy-app.operations.*] strict = True` (2026-05-27 확대 완료). 레거시 모듈은 `ignore_errors = True`로 제외 중: config, logger, model, path_helper, pdf_engine.

### 2.2 실측 결과 (strict 시 에러 수)

| 모듈 | strict 에러 | 조치 |
|------|-------------|------|
| text_utils | 0 | 게이트 추가 (현재 미명시) |
| path_helper | 0 | ignore_errors 제거 → strict |
| config | 0 | ignore_errors 제거 → strict |
| logger | 0 | ignore_errors 제거 → strict |
| text_metadata | 1 (`dict` type-arg) | 타입 보강 후 추가 |
| fonts | 3 (return annot·untyped-call·union-attr) | 타입 보강 후 추가 |
| document_session | 16 | **차기 사이클** |
| model / pdf_engine | (대량) | **차기 사이클** |

### 2.3 코드 수정 (S1)

- **text_metadata.py:12**: `dict` → `Dict[str, Any]` (또는 구체 타입)
- **fonts.py**: 
  - `_populate_font_cache` 반환 타입 `-> None` 추가
  - 호출부 untyped-call 해소(어노테이션 추가로 자동 해결)
  - `union-attr`: 캐시 `dict | None` → None 가드 또는 지역 변수로 좁히기

### 2.4 mypy.ini 최종 게이트

```ini
[mypy-app.operations.*]
strict = True
[mypy-app.config]
strict = True
[mypy-app.logger]
strict = True
[mypy-app.path_helper]
strict = True
[mypy-app.text_utils]
strict = True
[mypy-app.text_metadata]
strict = True
[mypy-app.fonts]
strict = True
# 차기 사이클(typing-legacy-core): model, pdf_engine, document_session
[mypy-app.model]
ignore_errors = True
[mypy-app.pdf_engine]
ignore_errors = True
[mypy-app.document_session]
ignore_errors = True
```

---

## 3. #3 Preview/Save DRY — 회귀 검증 설계

재구현 없음. `tests/test_preview_save_equivalence.py`(M1 수정 후 통과)가 단일 경로 보존을 보장. 추가 작업 불필요.

---

## 4. 검증 계획

1. `QT_QPA_PLATFORM=offscreen py -3.13 -m pytest -q` → 127 passed 목표
2. `py -3.13 -m pytest tests/test_mypy.py -q` → 게이트 통과
3. 확대 모듈 직접 strict: `py -3.13 -m mypy --strict app/config.py app/logger.py ...` → 0 에러

# Text Fidelity - Design

> **Summary**: 폰트 자동 매칭 체인 / 베이스라인 정렬 / 크기 신뢰의 구체 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-11
> **Status**: ✅ Completed (2026-06-11, 매치율 100%)
> **Plan**: [text-fidelity.plan.md](../../01-plan/features/text-fidelity.plan.md)

---

## 1. M1 — 폰트 자동 매칭

### `app/fonts.py` 신설 함수 (strict 유지)

```python
def _font_name_candidates(pdf_fontname: str, font_flags: int = 0) -> List[str]:
    """PDF 폰트명 → 레지스트리 조회 후보(소문자) 목록, 구체적→일반 순.

    1. 서브셋 접두어 제거: ^[A-Z]{6}\\+ (예: "ABCDEF+Calibri-Bold")
    2. 원형 그대로
    3. 하이픈/쉼표 → 공백 ("Calibri-Bold" → "calibri bold")
    4. camelCase 분리 ("MalgunGothic" → "malgun gothic")
    5. 플래그 기반 스타일 부가 (FONT_FLAG_BOLD/ITALIC → "{family} bold" 등)
    6. 패밀리만 (스타일 접미어 제거: bold/italic/regular/light/medium 등)
    중복 제거, 순서 유지.
    """

def resolve_pdf_fontname(pdf_fontname: str, font_flags: int = 0) -> Optional[str]:
    """추출된 PDF 폰트명을 설치된 시스템 폰트 파일 경로로 매칭 (실패 시 None)."""
    for candidate in _font_name_candidates(pdf_fontname, font_flags):
        path = get_font_path_by_name(candidate)
        if path and os.path.exists(path):
            return path
    return None
```

- `FONT_FLAG_BOLD`/`FONT_FLAG_ITALIC`는 `app.config`에 기존 정의 — fonts.py에서 import (config는 strict, 순환 없음).
- 비Windows/캐시 빈 환경: `get_font_path_by_name`이 None → 자연 폴백.

### applicator — 메타 인지형 폰트 해석 체인

기존 2단계(`_prepare_fonts` → 별칭, `_calculate_font_sizes` → 메타)의 순서를 뒤집어
메타 추출 후 폰트를 해석한다. `_prepare_fonts(page, operations, metadata_map)`로 시그니처 변경
(내부 메서드 — 외부 호출자 없음, 테스트 grep 확인):

```
op별 해석 (우선순위):
1. op.fontfile 존재+파일 존재  → 그대로 (사용자 명시 — 현행)
2. resolve_pdf_fontname(meta.fontname, meta.font_flags) 매칭 성공
   AND _font_covers_text(fontfile, op.new_text)        → 매칭 파일 사용
3. _base14_font_alias(meta.fontname, meta.font_flags)  → Base-14
   (현행은 op.fontname 기준 — 배치 op는 "helv" 고정이라 추출 메타 기준으로 교정)
```

- 결과는 `Dict[int, Tuple[str, Optional[str]]]`(alias, fontfile)로 반환,
  `_insert_replacement_text`가 op.fontfile 대신 **해석된 fontfile**을 측정·삽입에 사용.
- 임베딩: 파일 경로가 정해진 경우 기존 custom-font 분기(파일 stem 별칭 + `insert_font`) 재사용.
- `_font_covers_text(fontfile, text) -> bool`: `fitz.Font(fontfile=...)` 구성 후
  공백 제외 각 문자 `font.has_glyph(ord(ch))` 전수 검사(교체 텍스트는 짧음).
  구성/검사 실패 → False (안전 폴백). 글리프 누락 리스크(plan §5) 방어.

### S1 — 단일 교체 한글 폴백 우선순위 (`edit_handlers._resolve_replacement_font`)

```
1. self.current_replacement_font_path (사용자 수동 선택)
2. resolve_pdf_fontname(meta.fontname, meta.font_flags)  ← 신설 (원본 폰트 우선)
3. 한글 포함 시 get_default_korean_font_path()
4. None (applicator 체인이 다시 시도)
```

시그니처: `_resolve_replacement_font(replacement_text, source_fontname="", source_flags=0)` —
`replace_selection`이 meta 추출 후 호출하도록 순서 조정.

## 2. M2 — 베이스라인 정렬

### 추출 (`text_metadata.py`)

```python
origins: List[float] = []          # span["origin"][1] (베이스라인 y)
# 교차 span 수집 루프에서 origins.append(span["origin"][1])
metadata["baseline"] = min(origins) if origins else None   # 첫 줄 베이스라인
```

`TextMetadata`(operations/types.py)에 `baseline: Optional[float]` 추가.
`_calculate_font_sizes`가 `baseline=raw_meta.get("baseline")` 전달.
span 부재 폴백 분기는 `baseline=None`.

### 적용 (`applicator._compute_text_layout`)

`_insert_text_with_autofit`/`_compute_text_layout`에 `baseline: Optional[float] = None` 파라미터 추가.
레이아웃 결정(wrap/shrink로 `final_fontsize` 확정) **후**, fit_font 구성에 성공했고 baseline이 있으면:

```python
anchored_y0 = baseline - fit_font.ascender * final_fontsize
if 0.0 <= anchored_y0 < expanded_rect.y1:
    dy = anchored_y0 - expanded_rect.y0
    expanded_rect = fitz.Rect(x0, anchored_y0, x1, expanded_rect.y1 + dy)  # 박스 평행이동
```

- `insert_textbox`의 첫 줄 베이스라인 ≈ `y0 + ascender × fontsize` 이므로 위 보정으로 원본 베이스라인과 일치.
- 측정 실패(except 경로)·baseline 부재 → 보정 생략(현행 배치).
- wrap 박스 성장 계산은 보정 **전** y0 기준 그대로(성장량은 줄 수×줄높이라 평행이동 불변).
  보정 후 박스가 페이지 하단(`page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN`)을 넘으면 보정 생략(드묾 — 안전 우선).

## 3. M3 — 크기 신뢰 (`text_metadata.py`)

```python
if sizes:
    metadata["fontsize"] = sum(sizes) / len(sizes)        # rect 하한 제거
else:
    metadata["fontsize"] = rect_based_fontsize            # 폴백만 유지 (0.6, 8..72)
```

모듈 docstring의 "Behavior is preserved exactly..." 역사 주석을 갱신(M3로 의도 변경).

## 4. 테스트

### `tests/test_font_matching.py` (신규 — 순수 단위)

| 테스트 | 검증 |
|---|---|
| 서브셋 접두어 | `"ABCDEF+Calibri-Bold"` 후보에 `calibri bold`, `calibri` 포함 |
| camelCase | `"MalgunGothic"` → `malgun gothic` |
| 플래그 스타일 | `("Arial", BOLD)` → `arial bold` 우선 |
| 패밀리 폴백 | `"Calibri-BoldItalic"` → 마지막 후보 `calibri` |
| resolve 캐시 주입 | `_font_cache` monkeypatch로 매칭/실패/파일부재 경로 |

### `tests/test_text_fidelity.py` (신규 — 통합, Arial 부재 시 skip)

| 테스트 | 검증 |
|---|---|
| `test_replace_uses_matched_system_font` | Arial PDF → 폰트 미지정 교체 → 저장 span 폰트명에 "Arial" (helv 아님) |
| `test_batch_style_op_gets_matched_font` | `fontname="helv"` 기본 op(배치 경로 모사)도 추출 메타로 Arial 매칭 |
| `test_replace_preserves_baseline` | 교체 후 span `origin.y` 원본 ±1.0pt |
| `test_extracted_fontsize_not_inflated_by_large_rect` | 10pt 텍스트 + 큰 선택 박스 → 교체 span size ≈ 10pt (M3) |
| `test_rect_fallback_when_no_text` | 빈 영역 메타 → rect 기반 크기 + baseline None |
| `test_match_rejected_without_glyph_coverage` | `resolve_pdf_fontname("Arial", must_cover=한글)` → None (단위) |
| `test_uncovered_match_is_not_embedded_end_to_end` | 한글 교체 + Arial 원본 → applicator가 Arial을 임베딩하지 않음 (e2e 폴백) |

## 5. 검증 절차

1. `mypy` strict: fonts / text_metadata / operations 게이트 0 에러
2. 신규 테스트 → 전체 스위트 (235+)
3. CI(windows-latest — Arial 존재) green

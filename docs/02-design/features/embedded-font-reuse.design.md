# Embedded Font Reuse - Design

> **Summary**: 임베디드 폰트 추출·재사용의 구체 설계 (probe 실측 기반)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-11
> **Status**: ✅ Completed (2026-06-13, 매치율 100%)
> **Plan**: [embedded-font-reuse.plan.md](../../01-plan/features/embedded-font-reuse.plan.md)

---

## 1. M1 — `fonts.extract_embedded_font` (strict 유지)

```python
def _font_covers(font: fitz.Font, text: str) -> bool:
    """구성된 Font가 text의 비공백 문자 전부에 글리프를 갖는가."""
    return all(font.has_glyph(ord(ch)) for ch in text if not ch.isspace())
    # 기존 _font_file_covers는 이 헬퍼를 감싸는 파일 변형으로 리팩터

def extract_embedded_font(
    page: fitz.Page, source_fontname: str, must_cover: str = ""
) -> Optional[bytes]:
    """페이지에 임베딩된 source_fontname 계열 폰트 프로그램을 추출.

    매칭: 추출 span 폰트명과 각 엔트리의 basefont 양쪽을
    _font_name_candidates로 정규화한 뒤 교집합. 여러 엔트리가 매칭되면
    source 후보 목록에서 가장 구체적(인덱스 최소) 후보를 공유하는 엔트리 우선.
    (probe: span "ArialMT" vs basefont "Arial Regular" → 패밀리 "arial" 교집합)

    검증: 버퍼 비어있지 않음 + fitz.Font(fontbuffer=) 구성 성공 +
    must_cover 글리프 전수 커버. 서브셋 폰트는 cmap 제거(Identity-H)로
    has_glyph가 전부 0이라 자연 거부된다(2026-06-11 실측) — 오탐 없음.

    Returns: 폰트 프로그램 bytes 또는 None.
    """
```

구현 골격:

```python
src_candidates = _font_name_candidates(source_fontname)
if not src_candidates:
    return None
best: Tuple[int, bytes] | None = None         # (specificity index, buffer)
doc = page.parent
for entry in page.get_fonts(full=True):       # (xref, ext, type, basefont, name, enc, ...)
    base_candidates = set(_font_name_candidates(str(entry[3])))
    shared = [i for i, c in enumerate(src_candidates) if c in base_candidates]
    if not shared:
        continue
    specificity = shared[0]
    if best is not None and specificity >= best[0]:
        continue
    extracted = doc.extract_font(entry[0])    # (name, ext, type, buffer)
    buffer = bytes(extracted[3]) if extracted[3] else b""   # strict: 명시 bytes
    if not buffer:
        continue                              # Base-14/Type3 등 비추출
    try:
        font = fitz.Font(fontbuffer=buffer)
    except Exception:                         # FzError* 계열 — 구성 실패 = 미채택
        continue
    if not _font_covers(font, must_cover):
        continue
    best = (specificity, buffer)              # S1: debug 로그 (xref, basefont)
if best: return best[1]
return None
```

## 2. M2 — applicator 체인 확장

### resolved 튜플 3원소화

`_prepare_fonts` 반환: `Dict[int, Tuple[str, Optional[str], Optional[bytes]]]` = (alias, fontfile, fontbuffer). 결정 로직:

```
1. op.fontfile 존재          → (파일 stem 별칭, fontfile, None)
2. resolve_pdf_fontname(...) → (파일 stem 별칭, matched, None)
3. extract_embedded_font(page, source_fontname, op.new_text)
                             → (f"emb{crc32(buffer):08x}" 별칭, None, buffer)
4. Base-14                   → (base14 별칭, None, None)
```

> 임베디드 별칭은 **버퍼 내용 기반(crc32)** — 동일 프로그램은 같은 별칭으로
> 한 번만 등록·재사용되고, 서로 다른 프로그램은 절대 충돌하지 않는다.
> (초안의 `"emb"+정규화명[:20]`은 한 배치에서 다른 폰트 두 개를 교체할 때
> 절단 충돌로 두 번째 op가 첫 버퍼를 잘못 참조할 수 있어 보강 — 갭 분석 관찰 반영.)

### 등록 시점 — Pass 2.5 (구현 중 실측 발견)

`apply_redactions()`는 **남은 텍스트가 참조하지 않는 폰트 리소스를 제거**한다.
redaction 전에 `insert_font`로 등록하면(아직 사용 텍스트 없음) 별칭이 소거되어
버퍼 기반 `insert_textbox`가 "need font file or buffer"로 실패한다. 따라서:

- **추출**(`extract_embedded_font`)은 redaction **전** (`_prepare_fonts`) —
  원본 텍스트 제거와 함께 소스 폰트 리소스가 사라질 수 있으므로.
- **등록**(`insert_font` 파일/버퍼)은 redaction **후** 신설 `_register_fonts`
  (Pass 2.5, 삽입 직전). "already registered" 검사는
  `entry[3](basefont) == alias or entry[4](page alias) == alias`.
  등록 실패(`OSError/IOError/RuntimeError`) → 해당 op만 Base-14 강등.

### 측정·삽입 플러밍

`_insert_text_with_autofit`/`_compute_text_layout`/`_insert_with_shrink`에
`fontbuffer: Optional[bytes] = None` 파라미터 추가:

- 측정: `fitz.Font(fontbuffer=fontbuffer)` 우선, 그 다음 fontfile, 그 다음 fontname.
- 삽입: 버퍼 기반이면 `insert_textbox(fontname=alias)`만 — `_prepare_fonts`가
  같은 페이지에 이미 `insert_font(fontbuffer=)`로 등록했으므로 별칭 해석됨
  (probe 실측 검증). fontfile 인자는 None.

## 3. M3 — 테스트 (`tests/test_text_fidelity.py` 확장)

| 테스트 | 검증 |
|---|---|
| `test_embedded_font_extracted` | 전체 임베딩 Arial PDF → `extract_embedded_font(page, "ArialMT", "Replaced")` → 버퍼 반환 |
| `test_embedded_font_rejects_uncovered` | 같은 페이지, must_cover=한글 → None |
| `test_embedded_font_rejects_unknown_name` | source_fontname="NoSuchFont" → None |
| `test_embedded_font_subset_rejected` | `subset_fonts()` 적용 문서 → None (cmap 제거 실측 동작 고정) |
| `test_replace_reuses_embedded_when_not_installed` | `resolve_pdf_fontname` monkeypatch→None(미설치 모사) → 교체 span 폰트 Arial 계열 + 베이스라인 ±1pt + 크기 유지 |
| `test_subset_source_falls_back_safely` | 서브셋 소스 + 미설치 모사 → 예외 0, 교체 span 폰트는 Base-14(Helvetica) 계열 |

## 4. 검증 절차

1. mypy strict: fonts + operations 게이트 0 에러 (fonts는 warn_return_any 완화 없음 — `bytes()` 명시 변환)
2. 신규 테스트 → 전체 스위트(254+) → CI

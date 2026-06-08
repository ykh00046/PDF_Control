# Text Wrap Replace - Design

> **Summary**: 긴 텍스트 교체 시 폰트 축소 대신 박스 높이를 아래로 확장해 자동 줄바꿈으로 수용하는 구현 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: 🔄 In Progress
> **Plan**: [text-wrap-replace.plan.md](../../01-plan/features/text-wrap-replace.plan.md)

---

## 1. 핵심 아이디어

`OperationApplicator._insert_text_with_autofit`의 의사결정 순서를 다음과 같이 재배치한다.

```
1) 텍스트가 1줄 폭에 들어가면        → 그대로 삽입 (변경 없음)
2) 안 들어가면:
   a) 가장 긴 단어가 폭 안에 들어가고, 줄바꿈에 필요한 높이가
      페이지 경계 안이면  → 박스 높이를 아래로 확장 + 줄바꿈 (text.wrapped, info)
   b) 그 외 (긴 단어가 폭 초과 / 세로 공간 부족) → 기존 폰트 축소 폴백 (text.shrunk)
3) 폰트 축소로도 안 들어가면          → 기존 overflow (text.overflow, error)
```

**왜 줄바꿈 우선인가**: 폰트 축소는 가독성을 희생한다(6~8pt). 세로 여백이 있으면 원래 크기로 줄바꿈하는 편이 정보 보존·가독성 모두 우수하다. 줄바꿈이 불가능한 경우(긴 단어가 폭 초과)에만 축소로 폴백한다.

---

## 2. 변경 파일

| 파일 | 변경 |
|------|------|
| `app/config.py` | 워드랩 제어 상수 3개 추가 |
| `app/operations/applicator.py` | `_insert_text_with_autofit` 재구성 + 헬퍼 2개 추가 |
| `app/ui_statusbar.py` | `text.wrapped` 코드 표시 분기 추가 |
| `app/i18n/en.json`, `ko.json` | `warn.code.text.wrapped`, `warn.history.badge_wrapped` 키 추가 |
| `tests/test_text_wrap.py` | 신규 테스트 (wrap 발생 / 폭초과 폴백 / 페이지경계) |
| `tests/test_long_text_warning.py` | i18n required 키 집합에 wrapped 키 추가 |

> 외부 시그니처(`apply_operations`, `RedactReplace`)는 불변 → 호출부(preview/save) 영향 없음. preview·save 모두 동일 `apply_operations` 경로이므로 동등성 자동 보존.

---

## 3. config.py 신규 상수

```python
# --- Text word-wrap (multiline replacement) ---
TEXT_WRAP_ENABLED = True            # 줄바꿈 우선 정책 on/off
TEXT_WRAP_LINE_HEIGHT_FACTOR = 1.2  # 줄 높이 = fontsize * factor
TEXT_WRAP_BOTTOM_MARGIN = 4.0       # 페이지 하단에서 최소한 띄울 여백(pt)
```

---

## 4. applicator.py 설계

### 4.1 신규 헬퍼 — 줄바꿈 라인 수 계산

`insert_textbox`의 내부 줄바꿈을 사전 시뮬레이션해 라인 수를 추정한다(공백 기준 greedy wrap, `insert_textbox`와 동일한 정책).

```python
def _wrap_line_count(
    self, fit_font: "fitz.Font", text: str, fontsize: float, max_width: float
) -> Tuple[int, float]:
    """공백 기준 greedy 줄바꿈 시 라인 수와 '가장 긴 단어 폭'을 반환.

    Returns:
        (line_count, longest_token_width)
        line_count: 줄바꿈 후 줄 수 (>=1)
        longest_token_width: 단일 토큰의 최대 폭 — 이게 max_width를 넘으면
            줄바꿈으로는 폭 문제를 해결할 수 없음(축소 폴백 필요).
    """
    words = text.split()
    if not words:
        return 1, 0.0
    space_w = fit_font.text_length(" ", fontsize=fontsize)
    longest = 0.0
    lines = 1
    cur = 0.0
    for word in words:
        w = fit_font.text_length(word, fontsize=fontsize)
        longest = max(longest, w)
        if cur <= 0.0:
            cur = w                       # 줄 첫 단어
        elif cur + space_w + w <= max_width:
            cur += space_w + w            # 같은 줄에 이어붙임
        else:
            lines += 1                    # 새 줄로
            cur = w
    return lines, longest
```

### 4.2 `_insert_text_with_autofit` 재구성

기존 try 블록(폭 기반 바이너리서치)을 다음으로 대체한다. **바이너리서치 로직은 보존**하되, 그 앞에 줄바꿈 분기를 둔다.

```python
final_fontsize = initial_fontsize
autofit_shrunk = False
wrapped_lines = 0
try:
    fit_font = (
        fitz.Font(fontname=fontname, fontfile=fontfile) if fontfile
        else fitz.Font(fontname=fontname)
    )
    target_width = expanded_rect.width * TEXT_AUTOFIT_WIDTH_RATIO
    one_line_width = fit_font.text_length(text, fontsize=initial_fontsize)

    if one_line_width > target_width:
        # 1줄에 안 들어감 → 줄바꿈 우선 시도
        handled = False
        if TEXT_WRAP_ENABLED:
            lines, longest_token = self._wrap_line_count(
                fit_font, text, initial_fontsize, target_width
            )
            if lines > 1 and longest_token <= target_width:
                line_h = initial_fontsize * TEXT_WRAP_LINE_HEIGHT_FACTOR
                needed_h = lines * line_h + TEXT_BOX_Y_PADDING
                avail_h = (page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN) - expanded_rect.y0
                if needed_h <= avail_h:
                    expanded_rect = fitz.Rect(
                        expanded_rect.x0, expanded_rect.y0,
                        expanded_rect.x1, expanded_rect.y0 + needed_h,
                    )
                    wrapped_lines = lines      # 폰트 유지, 높이만 확장
                    handled = True
        if not handled:
            # 줄바꿈 불가(긴 단어 폭 초과 / 세로 공간 부족) → 폰트 축소 폴백
            low, high = TEXT_AUTOFIT_MIN_FONT_SIZE, float(initial_fontsize)
            for _ in range(TEXT_AUTOFIT_ITERATIONS):
                mid = (low + high) / 2
                if fit_font.text_length(text, fontsize=mid) > target_width:
                    high = mid
                else:
                    low = mid
            final_fontsize = low
            autofit_shrunk = True
except (RuntimeError, ValueError, TypeError, FileNotFoundError) as exc:
    self.logger.warning(
        "Text autofit calculation failed; using initial fontsize "
        f"{initial_fontsize:.2f}pt: {exc}"
    )
```

이후 `page.insert_textbox(expanded_rect, ...)` 호출은 **그대로 1회**. 확장된 높이 덕분에 줄바꿈된 텍스트가 `result >= 0`으로 정상 삽입된다.

### 4.3 경고 방출

기존 `result < 0` 폴백(`_insert_with_shrink`) 및 `autofit_shrunk` 경고는 유지. 추가로:

```python
elif wrapped_lines > 1 and warnings is not None:
    warnings.append(OpWarning(
        op_index=op_index,
        severity="info",
        code="text.wrapped",
        detail={
            "lines": wrapped_lines,
            "fontsize": round(final_fontsize, 2),
            "text_len": len(text),
            "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
        },
    ))
```

> `severity="info"` — 줄바꿈은 정보 보존에 성공한 **정상 동작**이므로 비차단. `has_blocking_warnings()`(error만 차단)에 영향 없음.

---

## 5. 경계·엣지 케이스

| 케이스 | 처리 |
|--------|------|
| 1줄에 이미 맞음 | 분기 안 탐, 기존 동작 그대로 |
| 긴 단어 1개가 폭 초과 (예: "replacement" 99pt > 89pt) | `longest_token > target_width` → 축소 폴백 (`text.shrunk`) — **기존 테스트 보존** |
| 세로 공간 부족 (박스가 페이지 하단 근처) | `needed_h > avail_h` → 축소 폴백 |
| 1x1 극단 박스 | 폭 바인딩 → 축소 → overflow (`text.overflow`) — **기존 테스트 보존** |
| 빈 텍스트 | `_wrap_line_count`가 (1,0) 반환, 분기 안 탐 |
| 추정 라인수 < 실제 (insert_textbox가 -1 반환) | 기존 `_insert_with_shrink` 폴백이 흡수 (안전망) |

---

## 6. 테스트 설계 (`tests/test_text_wrap.py`)

1. `test_long_text_wraps_instead_of_shrinking`: 폭 200·tall 페이지, 짧은 단어들로 구성된 긴 텍스트 → `text.wrapped` 방출, `text.shrunk` 없음, 폰트 유지(초기≈최종).
2. `test_long_word_falls_back_to_shrink`: "replacement"류 긴 단어 포함 좁은 박스 → `text.shrunk` 방출(폴백 정상).
3. `test_wrap_respects_page_bottom`: 박스를 페이지 하단 근처에 두면 확장이 페이지 경계를 넘지 않음 → 축소 폴백 또는 경계 내 확장.
4. `test_wrap_disabled_falls_back`: `TEXT_WRAP_ENABLED=False`(monkeypatch) 시 기존 축소 동작.

---

## 7. 영향 범위 / 회귀

- 호출부 시그니처 불변 → preview/save/batch 영향 없음.
- 기존 128 테스트: narrow-rect(긴 단어)·1x1 케이스 모두 폭 바인딩으로 축소 경로 유지 → 그대로 통과 예상.
- i18n: `warn.code.text.wrapped` 키 추가, statusbar 분기 추가(미정의 코드 fallback도 이미 존재).

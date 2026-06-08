# Replace Wrap Toggle - Design

> **Plan**: `docs/01-plan/features/replace-wrap-toggle.plan.md`
> **Author**: Claude (bkit)
> **Created**: 2026-06-08
> **Status**: 🔄 In Progress

---

## 1. 아키텍처 개요

기존 "옵션 전달 파이프라인"(이미 `fixed_font`로 검증됨)에 `wrap` 플래그 하나를 추가로 얹는다. **새 경로를 만들지 않는다.**

```
BatchReplaceDialog (UI)
  └─ [✓] 자동 줄바꿈 체크박스
        │ emit replacements_confirmed([{..., "wrap": bool}])
        ▼
DialogHandlerMixin.process_batch_replacements
        │ wrap = r_data.get("wrap")   # True/False (다이얼로그는 항상 명시)
        ▼
RedactReplace(..., wrap: Optional[bool])
        │ None=전역 따름, True/False=override
        ▼
OperationApplicator._insert_replacement_text
        │ wrap_enabled = op.wrap if op.wrap is not None else TEXT_WRAP_ENABLED
        ▼
_insert_text_with_autofit(..., wrap_enabled: bool)
        │ if wrap_enabled and TEXT_WRAP_ENABLED-블록 진입조건  ← 기존 분기 재사용
```

핵심 설계 결정: **3-상태 의미론(tri-state)**
- `wrap=None` → 전역 `TEXT_WRAP_ENABLED` 따름 (단일 교체 경로/직렬화 복원/하위 호환 기본값)
- `wrap=True` → 줄바꿈 강제 시도
- `wrap=False` → 줄바꿈 건너뛰고 폰트 축소 폴백

---

## 2. 상세 설계

### 2.1 모델 (`app/operations/redact.py`)

```python
class RedactReplace(Operation):
    def __init__(self, page_index, rects, new_text,
                 fontname="helv", fontsize=0, align=0,
                 fontfile=None, color=None, font_flags=0,
                 wrap: Optional[bool] = None) -> None:   # ← 신규, 맨 끝(하위호환)
        ...
        self.wrap = wrap

    def to_dict(self):
        data = super().to_dict()
        data.update({..., "wrap": self.wrap})   # ← 신규 키
        return data
```

- 위치: 인자 목록 **맨 끝**, 기본값 `None` → 기존 positional/keyword 호출 전부 무영향.

### 2.2 Applicator (`app/operations/applicator.py`)

**(a) op→wrap 해석 + 스레딩** — `_insert_replacement_text` 루프 내에서:

```python
op_wrap = getattr(op, "wrap", None)
wrap_enabled = op_wrap if op_wrap is not None else TEXT_WRAP_ENABLED
...
self._insert_text_with_autofit(
    page, rect, op.new_text, font_alias, final_fontsize,
    op.fontfile, text_color, font_flags,
    op_index=i, warnings=warnings,
    wrap_enabled=wrap_enabled,      # ← 신규 키워드
)
```

**(b) `_insert_text_with_autofit` 시그니처**:

```python
def _insert_text_with_autofit(self, ..., warnings=None,
                              wrap_enabled: bool = TEXT_WRAP_ENABLED):  # ← 신규
```

- 기본값을 `TEXT_WRAP_ENABLED`로 두어 직접 호출(테스트 등)도 기존과 동일.

**(c) 내부 분기 수정** — 기존:
```python
if TEXT_WRAP_ENABLED:
```
변경:
```python
if wrap_enabled:
```
> 전역 상수 직접 참조를 파라미터로 치환. 동작 동일성: `wrap_enabled` 기본값이 `TEXT_WRAP_ENABLED`이므로 모든 기존 경로 불변.

### 2.3 다이얼로그 (`app/batch_replace_dialog.py`)

`_setup_ui`의 Font Size Options 레이아웃(`font_layout`)에 체크박스 추가:

```python
self.use_wrap_checkbox = QCheckBox(tr("batch.use_wrap"))
self.use_wrap_checkbox.setToolTip(tr("batch.use_wrap.tooltip"))
self.use_wrap_checkbox.setChecked(True)   # 기본 = 현 전역 동작
font_layout.addWidget(self.use_wrap_checkbox)
```

`_confirm_replacements`의 emit dict에 추가:
```python
wrap_enabled = self.use_wrap_checkbox.isChecked()
...
replacements_to_emit.append({..., "wrap": wrap_enabled})
```

### 2.4 핸들러 (`app/handlers/dialog_handlers.py`)

```python
wrap = r_data.get("wrap")          # 다이얼로그는 bool, 누락 시 None=전역
operation = RedactReplace(
    page_index, [rect], new_text,
    fontfile=self.current_replacement_font_path,
    fontsize=fontsize,
    wrap=wrap,                      # ← 신규
)
```

### 2.5 i18n (`app/i18n/en.json`, `ko.json`)

| 키 | en | ko |
|---|---|---|
| `batch.use_wrap` | `Wrap long text` | `긴 텍스트 줄바꿈` |
| `batch.use_wrap.tooltip` | `When the replacement is too long, wrap onto multiple lines instead of shrinking the font.` | `교체 텍스트가 길면 폰트를 줄이지 않고 여러 줄로 나눕니다.` |

---

## 3. 테스트 설계 (`tests/test_text_wrap.py` 확장)

기존 테스트가 applicator를 직접 구동하는 패턴을 재사용한다.

| 테스트 | 입력 | 기대 |
|---|---|---|
| `test_wrap_false_forces_shrink` | 좁은 박스 + 긴 텍스트, `RedactReplace(wrap=False)` | 줄바꿈 안 함 → `text.shrunk` 경고, fontsize < 원본 |
| `test_wrap_true_multiline` | 동일 입력, `wrap=True` | `text.wrapped` 경고(lines>1), fontsize 보존 |
| `test_wrap_none_follows_global` | `wrap=None` | 전역 `TEXT_WRAP_ENABLED=True`와 동일 결과(`text.wrapped`) |
| `test_redact_replace_wrap_to_dict` | `RedactReplace(wrap=False).to_dict()` | `dict["wrap"] is False` |

> 직렬화/복원 라운드트립이 있다면 `wrap` 보존도 확인. (없으면 to_dict 키 존재만 검증)

---

## 4. 동작 동일성 / 회귀 방지

- 모든 신규 인자 기본값 = 기존 전역 동작 → **회귀 0** 설계.
- `TEXT_WRAP_ENABLED` 상수 자체는 유지(전역 기본값 역할).
- Preview/Save 단일 경로(`ApplyMode`)이므로 두 경로 자동 일치.

---

## 5. 구현 순서

1. `redact.py`: `wrap` 필드 + `to_dict`.
2. `applicator.py`: `_insert_text_with_autofit(wrap_enabled=...)` + 내부 분기 치환 + `_insert_replacement_text` 해석/전달.
3. `batch_replace_dialog.py`: 체크박스 + emit.
4. `dialog_handlers.py`: wrap 전달.
5. i18n en/ko 키.
6. 테스트 4건 추가.
7. 전체 테스트 실행 → Gap 분석.

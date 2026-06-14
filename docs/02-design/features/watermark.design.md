# Watermark - Design

> **Summary**: `WatermarkText` op + applicator watermark pass + 다이얼로그/컨트롤러 통합의 구체 설계 (probe 기반)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%)
> **Plan**: [watermark.plan.md](../../01-plan/features/watermark.plan.md)

---

## 1. M1 — `operations/watermark.py`

```python
class WatermarkText(Operation):
    def __init__(self, page_index, text, fontsize=40.0,
                 color=(0.5, 0.5, 0.5), opacity=0.3, angle=45.0):
        super().__init__(page_index, [])   # no rects
        self.text = text
        self.fontsize = fontsize
        self.color = color        # RGB 0-1
        self.opacity = opacity    # 0-1
        self.angle = angle        # degrees, CCW

    def apply(self, page):
        if not self.text:
            return
        font = fitz.Font("helv")
        tw = fitz.TextWriter(page.rect, opacity=self.opacity, color=self.color)
        text_w = font.text_length(self.text, fontsize=self.fontsize)
        cx, cy = page.rect.width / 2, page.rect.height / 2
        tw.append((cx - text_w / 2, cy), self.text, font=font, fontsize=self.fontsize)
        tw.write_text(page, morph=(fitz.Point(cx, cy), fitz.Matrix(self.angle)))

    def to_dict(self):
        data = super().to_dict()
        data.update({"text": self.text, "fontsize": self.fontsize,
                     "color": list(self.color), "opacity": self.opacity,
                     "angle": self.angle})
        return data
```

- probe 검증: 중앙 pivot + `Matrix(angle)` morph로 회전, `opacity`로 반투명. 비파괴(콘텐츠 추가).
- `page.rect` 기준 중앙 — crop된 페이지도 현재 rect 중앙에 정확히.

## 2. M2 — base.from_dict + applicator pass

**base.py from_dict** 분기 추가:
```python
elif op_type == "WatermarkText":
    color = data.get("color")
    return WatermarkText(
        page_index, data["text"],
        data.get("fontsize", 40.0),
        tuple(color) if color else (0.5, 0.5, 0.5),
        data.get("opacity", 0.3),
        data.get("angle", 45.0),
    )
```
(lazy import에 `from app.operations.watermark import WatermarkText` 추가.)

**applicator.py**:
- 상단 import: `from app.operations.watermark import WatermarkText`.
- `apply_operations` 끝(section removal 다음, return 전)에 watermark pass:
```python
# Pass 5: Watermark overlay (last -- drawn on top of everything, incl. a
# section-removal raster). Non-destructive, so SAVE and PREVIEW share it.
for op in operations:
    if isinstance(op, WatermarkText):
        op.apply(page)
```
- 마지막 pass라 redaction/text/section removal 위에 그려짐.

## 3. M3 — 다이얼로그 + 컨트롤러

**`app/watermark_dialog.py`** `WatermarkDialog(QDialog)`:
- 입력: 텍스트(QLineEdit), 폰트크기(QSpinBox, 기본 40), 투명도(QSlider 10–100% → 0.1–1.0, 기본 30%), 각도(QSpinBox -180~180, 기본 45), 색상(QPushButton→QColorDialog, 기본 회색), 적용범위(QRadioButton 현재/전체, 기본 전체).
- `watermark_confirmed = Signal(dict)` — `{text, fontsize, color, opacity, angle, all_pages}`.
- 빈 텍스트 적용 거부(S1).

**`controller.add_watermark(text, fontsize, color, opacity, angle, all_pages)`**:
```python
def add_watermark(self, ...) -> bool:
    def run(s):
        indices = range(s.doc.page_count) if all_pages else [<current>]
        for i in indices:
            s.add_operation(WatermarkText(i, text, fontsize, color, opacity, angle))
    return bool(self._run_session_action("add watermark", run))
```
- 현재 페이지 인덱스는 컨트롤러가 모르므로, 핸들러가 `viewer.current_page_index`를 받아 `all_pages=False`일 때 단일 인덱스 리스트를 넘기는 형태로 전달. → 시그니처: `add_watermark(..., page_indices: list[int])` (핸들러가 범위 계산). 컨트롤러는 Qt 비의존 유지.
- batch-replace 패턴: op마다 `add_operation`(가드는 1회 래핑). `operation_applied`는 가드가 1회 emit → 미리보기 1회 갱신.

**dialog_handlers.py** `open_watermark_dialog`:
```python
dialog = WatermarkDialog(self)
dialog.watermark_confirmed.connect(self.apply_watermark)
dialog.exec()
# apply_watermark(settings):
#   indices = range(page_count) if settings["all_pages"] else [viewer.current_page_index]
#   controller.add_watermark(..., page_indices=list(indices))
```

**ui_menu.py**: Tools 메뉴에 "Add Watermark…" 액션 → `open_watermark_dialog`.

## 4. M4 — i18n 키 (en/ko)

`watermark.dialog.title`, `watermark.label.text`, `watermark.label.fontsize`, `watermark.label.opacity`, `watermark.label.angle`, `watermark.label.color`, `watermark.scope.current`, `watermark.scope.all`, `watermark.button.apply`, `watermark.button.cancel`, `menu.tools.watermark`, `status.watermark_applied`.

## 5. M5 — 테스트

### `tests/test_op_serialization.py` 확장
- `WatermarkText` round-trip(전 필드, color tuple 보존).

### `tests/test_watermark.py` (신규)
| 테스트 | 검증 |
|---|---|
| `test_watermark_apply_renders_text` | 빈 페이지에 op.apply → 저장/재오픈 → 텍스트 검색됨 |
| `test_watermark_preserves_body` | 본문 있는 페이지 → 워터마크 후 본문 텍스트 유지 |
| `test_watermark_empty_text_noop` | text="" → apply 무동작(예외 0, 텍스트 없음) |
| `test_watermark_all_pages_via_controller` | 컨트롤러 all_pages → 전 페이지 op 수 == page_count, 저장 후 각 페이지 워터마크 |
| `test_preview_save_equivalence_watermark` | PREVIEW/SAVE 모두 워터마크 그려짐(applicator 단일 경로) |

## 6. 검증 절차

1. mypy strict(operations) 0 에러
2. 신규 테스트 → 전체 스위트(271+)
3. gap-detector → CI green

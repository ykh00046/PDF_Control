# Image Watermark - Design

> **Summary**: `WatermarkImage` op (Pixmap 알파 우회 + 중앙 배치) + 다이얼로그/컨트롤러 통합
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-14, 매치율 100%)
> **Plan**: [image-watermark.plan.md](../../01-plan/features/image-watermark.plan.md)

---

## 1. `WatermarkImage` op (operations/watermark.py에 추가)

```python
class WatermarkImage(Operation):
    def __init__(self, page_index, image_path, opacity=0.3, scale=0.5, rotate=0):
        super().__init__(page_index, [])
        self.image_path = image_path
        self.opacity = opacity   # 0-1
        self.scale = scale       # fraction of page WIDTH
        self.rotate = rotate     # 0/90/180/270 only (insert_image limit)

    def apply(self, page):
        if not self.image_path or not os.path.exists(self.image_path):
            get_logger().warning(f"Watermark image missing: {self.image_path!r}")
            return  # no-op, render must not break
        try:
            pix = fitz.Pixmap(self.image_path)
            if not pix.alpha:
                pix = fitz.Pixmap(pix, 1)  # add alpha channel
            alpha = max(0, min(255, int(self.opacity * 255)))
            pix.set_alpha(bytes([alpha] * (pix.width * pix.height)))
        except Exception as e:
            get_logger().warning(f"Watermark image load failed: {e}")
            return
        target_w = page.rect.width * self.scale
        target_h = target_w * pix.height / pix.width
        cx, cy = page.rect.width / 2, page.rect.height / 2
        rect = fitz.Rect(cx - target_w/2, cy - target_h/2,
                         cx + target_w/2, cy + target_h/2)
        page.insert_image(rect, pixmap=pix, keep_proportion=True, rotate=self.rotate)

    def to_dict(self):
        data = super().to_dict()
        data.update({"image_path": self.image_path, "opacity": self.opacity,
                     "scale": self.scale, "rotate": self.rotate})
        return data
```

- `os` import 추가(watermark.py). probe 검증된 Pixmap 알파 우회.
- rect는 apply 시점 page.rect 기준(scale 상대값) — 직렬화에 절대 좌표 없음, crop된 페이지에도 정확.

## 2. base.from_dict + applicator

**base.py**: lazy import `WatermarkImage` 추가 + 분기:
```python
elif op_type == "WatermarkImage":
    return WatermarkImage(
        page_index, data["image_path"],
        data.get("opacity", 0.3), data.get("scale", 0.5), data.get("rotate", 0),
    )
```

**applicator.py**: Pass 5 isinstance를 튜플로:
```python
for op in operations:
    if isinstance(op, (WatermarkText, WatermarkImage)):
        op.apply(page)
```
(상단 import에 WatermarkImage 추가.)

**model.py**: WatermarkImage export(import + __all__).

## 3. 다이얼로그 + 컨트롤러

**`app/image_watermark_dialog.py`** `ImageWatermarkDialog(QDialog)`:
- 파일 선택 버튼(QFileDialog 이미지 필터, 선택 경로 라벨), opacity 슬라이더(10-100%), scale 스핀(10-100% → 0.1-1.0), rotate 콤보(0/90/180/270), 적용범위 라디오(현재/전체, 기본 전체).
- `image_watermark_confirmed = Signal(dict)` — `{image_path, opacity, scale, rotate, all_pages}`.
- 파일 미선택 시 Apply 거부(reject).

**controller.add_image_watermark(page_indices, image_path, opacity, scale, rotate)**:
- watermark 패턴 — `_run_session_action` 가드 루프, 범위별 `WatermarkImage` op. Qt-free.

**dialog_handlers.open_image_watermark_dialog / apply_image_watermark**: watermark 핸들러 패턴(all_pages→range, else→[current_page_index]).

**ui_menu**: Tools "Add Image Watermark…" (Ctrl+Shift+I).

## 4. i18n (en/ko)

`menu.tools.image_watermark`, `image_watermark.dialog.title`, `image_watermark.label.file`, `image_watermark.button.browse`, `image_watermark.label.opacity`, `image_watermark.label.scale`, `image_watermark.label.angle`, `image_watermark.scope.current`, `image_watermark.scope.all`, `image_watermark.button.apply`, `image_watermark.button.cancel`, `image_watermark.no_file`, `status.image_watermark_applied`.

## 5. 테스트

### test_op_serialization.py
- WatermarkImage round-trip + legacy-defaults.

### test_watermark.py 확장
| 테스트 | 검증 |
|---|---|
| `test_image_watermark_renders` | 임시 PNG → op.apply → 저장 후 이미지 존재 + 본문 유지 |
| `test_image_watermark_missing_file_noop` | 존재하지 않는 경로 → apply 예외 0, 이미지 없음 |
| `test_image_watermark_opacity_alpha` | apply 후 페이지 이미지 1개(반투명 삽입 성공) |
| `test_image_watermark_all_pages_controller` | 컨트롤러 전체 → 전 페이지 op + 저장 후 각 페이지 이미지 |
| `test_image_watermark_preview_save_equiv` | PREVIEW/SAVE 모두 이미지 삽입 |

## 6. 검증 절차

1. mypy strict(operations) 0 에러
2. 신규 테스트 → 전체 스위트(287+)
3. gap-detector → CI green

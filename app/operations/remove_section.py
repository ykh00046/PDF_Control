"""Mid-page section removal via image conversion.

Split out of the former monolithic ``app/model.py`` (model-restructure).
The previously ~160-line ``apply()`` is decomposed into single-responsibility
helpers; behavior (memory guards, DPI auto-cap, colorspace handling, page
rebuild) is preserved exactly.
"""
from io import BytesIO
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, cast

import fitz

from app.config import (
    BYTES_PER_MIB,
    DEFAULT_CONFIG,
    DEFAULT_REMOVE_SECTION_DPI,
    DEFAULT_REMOVE_SECTION_FORMAT,
    PDF_POINTS_PER_INCH,
    RGBA_BYTES_PER_PIXEL,
)
from app.logger import get_logger
from app.operations.base import Operation

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


def _memory_limits() -> Dict[str, int]:
    return cast(Dict[str, int], DEFAULT_CONFIG.get("memory", {}))


class RemoveSectionAsImage(Operation):
    """중간 영역 제거 (이미지 변환 방식)"""

    def __init__(
        self,
        page_index: int,
        remove_rect: fitz.Rect,
        dpi: int = DEFAULT_REMOVE_SECTION_DPI,
        format: str = DEFAULT_REMOVE_SECTION_FORMAT,
    ) -> None:
        super().__init__(page_index, [])
        self.remove_rect = remove_rect
        self.dpi = dpi
        self.format = format

    # ── 1. DPI / 메모리 ────────────────────────────────────────────
    def _resolve_render_dpi(self, page_rect: fitz.Rect) -> Tuple[float, fitz.Matrix]:
        """메모리 추정 후 DPI를 자동 캡(또는 경고)하고 (zoom, matrix)를 돌려준다."""
        logger = get_logger()
        effective_dpi = self.dpi
        zoom = effective_dpi / PDF_POINTS_PER_INCH

        expected_width_px = int(page_rect.width * zoom)
        expected_height_px = int((page_rect.height - self.remove_rect.height) * zoom)

        # RGBA(4 bytes/px) 기준으로 안전하게 추정
        estimated_memory_mb = (
            expected_width_px * expected_height_px * RGBA_BYTES_PER_PIXEL
        ) / BYTES_PER_MIB

        limits = _memory_limits()
        max_memory_mb = limits.get("remove_section_dpi_cap_mb", 500)
        large_warn_mb = limits.get("remove_section_large_warn_mb", 100)
        if estimated_memory_mb > max_memory_mb:
            safe_zoom = (
                max_memory_mb
                * BYTES_PER_MIB
                * PDF_POINTS_PER_INCH
                * PDF_POINTS_PER_INCH
            ) / (
                page_rect.width
                * (page_rect.height - self.remove_rect.height)
                * RGBA_BYTES_PER_PIXEL
            )
            safe_zoom = safe_zoom ** 0.5
            safe_dpi = int(safe_zoom * PDF_POINTS_PER_INCH)

            logger.warning(
                f"RemoveSectionAsImage: DPI auto-capped from {self.dpi} to {safe_dpi} "
                f"(estimated memory: {estimated_memory_mb:.1f}MB → {max_memory_mb}MB)"
            )
            effective_dpi = safe_dpi
            zoom = effective_dpi / PDF_POINTS_PER_INCH
        elif estimated_memory_mb > large_warn_mb:
            logger.warning(
                f"RemoveSectionAsImage: Large memory usage expected: {estimated_memory_mb:.1f}MB "
                f"(Page: {page_rect.width:.0f}x{page_rect.height:.0f}pt, DPI: {effective_dpi})"
            )

        return zoom, fitz.Matrix(zoom, zoom)

    # ── 2. 클립 계산 ───────────────────────────────────────────────
    def _compute_clips(self, page_rect: fitz.Rect) -> List[fitz.Rect]:
        """제거 영역 위/아래로 남는 클립(높이>0)만 위에서 아래 순서로 반환."""
        top_clip = fitz.Rect(0, 0, page_rect.width, self.remove_rect.y0)
        bottom_clip = fitz.Rect(0, self.remove_rect.y1, page_rect.width, page_rect.height)

        clips = [c for c in (top_clip, bottom_clip) if c.height > 0]
        if not clips:
            raise ValueError("Cannot remove section: result would be empty page")
        return clips

    # ── 3. 단일 클립 렌더 ──────────────────────────────────────────
    def _render_clip(self, page: fitz.Page, matrix: fitz.Matrix, clip: fitz.Rect) -> "PILImage":
        """클립 영역을 pixmap으로 렌더해 PIL.Image로 변환(색공간/JPEG 처리 포함)."""
        from PIL import Image

        pix = page.get_pixmap(matrix=matrix, clip=clip)
        if pix.n == 1:
            mode = "L"
        elif pix.alpha:
            mode = "RGBA"
        else:
            mode = "RGB"

        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        if self.format == "jpeg" and mode == "RGBA":
            img = img.convert("RGB")
        get_logger().debug(f"Rendered section: {pix.width}x{pix.height}px")
        return img

    # ── 4. 수직 병합 ───────────────────────────────────────────────
    def _merge_vertical(self, images: List["PILImage"]) -> Tuple["PILImage", int]:
        """이미지들을 수직 병합. 병합 메모리 가드 적용. (combined, pixel_width) 반환."""
        from PIL import Image

        pixel_width = images[0].width
        combined_height = sum(img.height for img in images)

        limits = _memory_limits()
        estimated_memory = pixel_width * combined_height * 3  # RGB 기준
        merge_warn_bytes = limits.get("merge_warn_mb", 50) * BYTES_PER_MIB
        merge_abort_bytes = limits.get("merge_abort_mb", 200) * BYTES_PER_MIB
        if estimated_memory > merge_warn_bytes:
            get_logger().warning(f"Large image merge: {estimated_memory / BYTES_PER_MIB:.1f}MB")
        if estimated_memory > merge_abort_bytes:
            raise MemoryError(
                "RemoveSectionAsImage aborted: estimated merge size "
                f"{estimated_memory / BYTES_PER_MIB:.1f}MB exceeds budget"
            )

        combined = Image.new("RGB", (pixel_width, combined_height))
        y_offset = 0
        for img in images:
            combined.paste(img, (0, y_offset))
            y_offset += img.height
        return combined, pixel_width

    # ── 5. 인코딩 ──────────────────────────────────────────────────
    def _encode(self, combined: "PILImage") -> bytes:
        """병합 이미지를 설정된 포맷(JPEG/PNG) 바이트로 인코딩."""
        buf = BytesIO()
        if self.format == "jpeg":
            combined.save(buf, format="JPEG", quality=90, optimize=True)
        else:
            combined.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    # ── 6. 페이지 재생성 ───────────────────────────────────────────
    def _rebuild_page(self, doc: fitz.Document, page_idx: int, page_rect: fitz.Rect,
                      combined: "PILImage", zoom: float) -> float:
        """원본 위치에 이미지 1장짜리 새 페이지를 만들고 원본을 삭제. 새 높이(pt) 반환."""
        new_height_pt = combined.height / zoom
        # new_page()가 자동으로 올바른 MediaBox 설정
        new_page = doc.new_page(page_idx, width=page_rect.width, height=new_height_pt)
        new_page.insert_image(
            fitz.Rect(0, 0, page_rect.width, new_height_pt),
            stream=self._encode(combined)
        )
        doc.delete_page(page_idx + 1)  # 한 칸 밀린 원본 삭제
        return new_height_pt

    # ── 오케스트레이션 ─────────────────────────────────────────────
    def apply(self, page: fitz.Page) -> None:
        """페이지를 이미지로 변환하여 중간 영역 제거."""
        doc = page.parent
        page_idx = page.number
        page_rect = page.rect

        zoom, matrix = self._resolve_render_dpi(page_rect)
        clips = self._compute_clips(page_rect)
        images = [self._render_clip(page, matrix, clip) for clip in clips]
        combined, _ = self._merge_vertical(images)
        new_height_pt = self._rebuild_page(doc, page_idx, page_rect, combined, zoom)

        get_logger().info(
            f"RemoveSectionAsImage applied: Page {page_idx}, "
            f"removed {self.remove_rect.height:.1f}pt, new height {new_height_pt:.1f}pt, "
            f"DPI={self.dpi}, format={self.format}"
        )

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "remove_rect": [self.remove_rect.x0, self.remove_rect.y0,
                            self.remove_rect.x1, self.remove_rect.y1],
            "dpi": self.dpi,
            "format": self.format
        })
        return data

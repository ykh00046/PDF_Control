import fitz
import os
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from PySide6.QtCore import QObject, Signal
from app.logger import get_logger, log_operation, log_file_operation
from app.pdf_engine import apply_page_operations, open_document, save_document_copy
from app.operations_service import ApplyMode
from app.text_utils import sanitize_unicode
from app.config import DEFAULT_CONFIG


def _memory_limits() -> Dict[str, int]:
    return DEFAULT_CONFIG.get("memory", {})

class WordBox:
    """Represents a word's bounding box and text content."""
    def __init__(self, rect: fitz.Rect, text: str, block: int, line: int, word_no: int):
        self.rect = rect
        self.text = text
        self.block = block
        self.line = line
        self.word_no = word_no

    def to_dict(self):
        return {"rect": list(self.rect), "text": self.text, "block": self.block, "line": self.line, "word_no": self.word_no}

    @staticmethod
    def from_dict(data: Dict[str, Any]):
        return WordBox(fitz.Rect(data["rect"]), data["text"], data["block"], data["line"], data["word_no"])

class Operation(ABC):
    """Abstract base class for document modification operations."""
    def __init__(self, page_index: int, rects: List[fitz.Rect]):
        self.page_index = page_index
        self.rects = rects

    @abstractmethod
    def apply(self, page: fitz.Page):
        pass

    @abstractmethod
    def to_dict(self):
        return {"page_index": self.page_index, "rects": [list(r) for r in self.rects], "type": self.__class__.__name__}

    @staticmethod
    def from_dict(data: Dict[str, Any]):
        op_type = data["type"]
        page_index = data["page_index"]
        rects = [fitz.Rect(r) for r in data["rects"]]
        if op_type == "RedactDelete":
            return RedactDelete(page_index, rects)
        elif op_type == "RedactReplace":
            color = data.get("color", None)
            return RedactReplace(
                page_index, rects, data["new_text"],
                data.get("fontname", "helv"), data.get("fontsize", 0),
                data.get("align", 0), data.get("fontfile", None),
                tuple(color) if color else None,
                data.get("font_flags", 0)
            )
        elif op_type == "CropMargins":
            return CropMargins(
                page_index,
                data.get("top", 0), data.get("bottom", 0),
                data.get("left", 0), data.get("right", 0)
            )
        elif op_type == "RemoveSectionAsImage":
            # RemoveSectionAsImage stores remove_rect separately
            remove_rect = fitz.Rect(data["remove_rect"]) if "remove_rect" in data else fitz.Rect()
            return RemoveSectionAsImage(
                page_index,
                remove_rect,
                data.get("dpi", 300),
                data.get("format", "jpeg")
            )
        else:
            raise ValueError(f"Unknown operation type: {op_type}")

class RedactDelete(Operation):
    """Represents a redaction operation to delete content."""
    def __init__(self, page_index: int, rects: List[fitz.Rect]):
        super().__init__(page_index, rects)

    def apply(self, page: fitz.Page):
        for rect in self.rects:
            page.add_redact_annot(rect, fill=(1, 1, 1))

    def to_dict(self):
        return super().to_dict()

class RedactReplace(Operation):
    """Represents a redaction operation to replace content with new text."""
    def __init__(self, page_index: int, rects: List[fitz.Rect], new_text: str,
                 fontname: str = "helv", fontsize: float = 0, align: int = 0,
                 fontfile: Optional[str] = None, color: Optional[Tuple[float, float, float]] = None,
                 font_flags: int = 0):
        super().__init__(page_index, rects)
        self.new_text = new_text
        self.fontname = fontname
        self.fontsize = fontsize
        self.align = align
        self.fontfile = fontfile
        self.color = color  # RGB tuple (0-1)
        self.font_flags = font_flags # PyMuPDF font flags

    def apply(self, page: fitz.Page):
        for rect in self.rects:
            page.add_redact_annot(rect, fill=(1, 1, 1))

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "new_text": self.new_text, 
            "fontname": self.fontname, 
            "fontsize": self.fontsize, 
            "align": self.align, 
            "fontfile": self.fontfile,
            "color": list(self.color) if self.color else None,
            "font_flags": self.font_flags
        })
        return data

class CropMargins(Operation):
    """Represents a page cropping operation to remove margins."""
    def __init__(self, page_index: int, top: float = 0, bottom: float = 0,
                 left: float = 0, right: float = 0):
        # CropMargins doesn't use rects, but we pass empty list to satisfy parent
        super().__init__(page_index, [])
        self.top = top      # Points to remove from top
        self.bottom = bottom  # Points to remove from bottom
        self.left = left    # Points to remove from left
        self.right = right  # Points to remove from right

    def apply(self, page: fitz.Page):
        """Apply cropping by adjusting the page's MediaBox."""
        current_rect = page.mediabox
        new_rect = fitz.Rect(
            current_rect.x0 + self.left,
            current_rect.y0 + self.top,
            current_rect.x1 - self.right,
            current_rect.y1 - self.bottom
        )
        page.set_mediabox(new_rect)
        page.set_cropbox(new_rect)  # Also set cropbox for consistency

    def to_dict(self):
        data = super().to_dict()
        data.update({"top": self.top, "bottom": self.bottom, "left": self.left, "right": self.right})
        return data

class RemoveSectionAsImage(Operation):
    """중간 영역 제거 (이미지 변환 방식)"""

    def __init__(self, page_index: int, remove_rect: fitz.Rect, dpi: int = 300, format: str = "jpeg"):
        super().__init__(page_index, [])
        self.remove_rect = remove_rect
        self.dpi = dpi
        self.format = format

    def apply(self, page: fitz.Page):
        """페이지를 이미지로 변환하여 중간 영역 제거"""
        from PIL import Image
        from io import BytesIO

        logger = get_logger()
        doc = page.parent
        page_idx = page.number
        page_rect = page.rect

        # 1. Early memory estimation and DPI auto-capping
        zoom = self.dpi / 72.0
        
        # Calculate expected pixel dimensions
        expected_width_px = int(page_rect.width * zoom)
        expected_height_px = int((page_rect.height - self.remove_rect.height) * zoom)
        
        # Estimate memory usage (RGBA = 4 bytes per pixel for safety)
        estimated_memory_mb = (expected_width_px * expected_height_px * 4) / (1024 * 1024)
        
        # Auto-cap DPI if memory would exceed configured budget
        limits = _memory_limits()
        max_memory_mb = limits.get("remove_section_dpi_cap_mb", 500)
        large_warn_mb = limits.get("remove_section_large_warn_mb", 100)
        if estimated_memory_mb > max_memory_mb:
            # Calculate safe DPI
            safe_zoom = (max_memory_mb * 1024 * 1024 * 72 * 72) / (page_rect.width * (page_rect.height - self.remove_rect.height) * 4)
            safe_zoom = safe_zoom ** 0.5
            safe_dpi = int(safe_zoom * 72)
            
            logger.warning(
                f"RemoveSectionAsImage: DPI auto-capped from {self.dpi} to {safe_dpi} "
                f"(estimated memory: {estimated_memory_mb:.1f}MB → {max_memory_mb}MB)"
            )
            self.dpi = safe_dpi
            zoom = self.dpi / 72.0
            
        elif estimated_memory_mb > large_warn_mb:
            # Warn but proceed if between warn and cap thresholds
            logger.warning(
                f"RemoveSectionAsImage: Large memory usage expected: {estimated_memory_mb:.1f}MB "
                f"(Page: {page_rect.width:.0f}x{page_rect.height:.0f}pt, DPI: {self.dpi})"
            )
        
        matrix = fitz.Matrix(zoom, zoom)

        # 2. 클립 영역 계산 및 검증
        top_clip = fitz.Rect(0, 0, page_rect.width, self.remove_rect.y0)
        bottom_clip = fitz.Rect(0, self.remove_rect.y1, page_rect.width, page_rect.height)

        top_height = top_clip.height
        bottom_height = bottom_clip.height

        # 빈 클립 체크
        if top_height <= 0 and bottom_height <= 0:
            raise ValueError("Cannot remove section: result would be empty page")

        images_to_merge = []
        pixel_width = 0

        # 3. 상단 영역 렌더링 (높이 > 0인 경우만)
        if top_height > 0:
            pix_top = page.get_pixmap(matrix=matrix, clip=top_clip)

            # 색공간 처리
            if pix_top.n == 1:
                mode = "L"
            elif pix_top.alpha:
                mode = "RGBA"
            else:
                mode = "RGB"

            img_top = Image.frombytes(mode, (pix_top.width, pix_top.height), pix_top.samples)

            # JPEG 저장 시 RGBA → RGB 변환
            if self.format == "jpeg" and mode == "RGBA":
                img_top = img_top.convert("RGB")

            images_to_merge.append(img_top)
            pixel_width = pix_top.width
            logger.debug(f"Rendered top section: {pix_top.width}x{pix_top.height}px")

        # 4. 하단 영역 렌더링 (높이 > 0인 경우만)
        if bottom_height > 0:
            pix_bot = page.get_pixmap(matrix=matrix, clip=bottom_clip)

            # 색공간 처리
            if pix_bot.n == 1:
                mode = "L"
            elif pix_bot.alpha:
                mode = "RGBA"
            else:
                mode = "RGB"

            img_bot = Image.frombytes(mode, (pix_bot.width, pix_bot.height), pix_bot.samples)

            # JPEG 저장 시 RGBA → RGB 변환
            if self.format == "jpeg" and mode == "RGBA":
                img_bot = img_bot.convert("RGB")

            images_to_merge.append(img_bot)
            if pixel_width == 0:
                pixel_width = pix_bot.width
            logger.debug(f"Rendered bottom section: {pix_bot.width}x{pix_bot.height}px")

        # 5. 수직 병합
        combined_height = sum(img.height for img in images_to_merge)

        # 메모리 경고 및 가드
        estimated_memory = pixel_width * combined_height * 3  # RGB 기준
        merge_warn_bytes = limits.get("merge_warn_mb", 50) * 1024 * 1024
        merge_abort_bytes = limits.get("merge_abort_mb", 200) * 1024 * 1024
        if estimated_memory > merge_warn_bytes:
            logger.warning(f"Large image merge: {estimated_memory / 1024 / 1024:.1f}MB")
        if estimated_memory > merge_abort_bytes:
            raise MemoryError(f"RemoveSectionAsImage aborted: estimated merge size {estimated_memory / 1024 / 1024:.1f}MB exceeds budget")

        combined = Image.new("RGB", (pixel_width, combined_height))
        y_offset = 0
        for img in images_to_merge:
            combined.paste(img, (0, y_offset))
            y_offset += img.height

        # 6. 이미지 저장
        buf = BytesIO()
        if self.format == "jpeg":
            combined.save(buf, format="JPEG", quality=90, optimize=True)
        else:
            combined.save(buf, format="PNG", optimize=True)
        buf.seek(0)

        # 7. 새 페이지 높이 계산
        new_height_pt = combined_height / zoom

        # 8. 새 페이지 생성 (new_page()가 자동으로 올바른 MediaBox 설정)
        new_page = doc.new_page(page_idx, width=page_rect.width, height=new_height_pt)

        # 9. 이미지 삽입
        new_page.insert_image(
            fitz.Rect(0, 0, page_rect.width, new_height_pt),
            stream=buf.getvalue()
        )

        # 10. 원본 페이지 삭제
        doc.delete_page(page_idx + 1)

        logger.info(f"RemoveSectionAsImage applied: Page {page_idx}, removed {self.remove_rect.height:.1f}pt, new height {new_height_pt:.1f}pt, DPI={self.dpi}, format={self.format}")

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "remove_rect": [self.remove_rect.x0, self.remove_rect.y0, self.remove_rect.x1, self.remove_rect.y1],
            "dpi": self.dpi,
            "format": self.format
        })
        return data

class PageModel:
    """Represents a single page in the document, caching its words."""
    def __init__(self, index: int):
        self.index = index
        self._words: Optional[List[WordBox]] = None

    def get_words(self, page: fitz.Page) -> List[WordBox]:
        if self._words is None:
            raw_words = page.get_text("words")
            self._words = [
                WordBox(fitz.Rect(w[0], w[1], w[2], w[3]), sanitize_unicode(w[4]), w[5], w[6], w[7])
                for w in raw_words
            ]
        return self._words
    
    def clear_cache(self):
        self._words = None

def _extract_text_metadata(page: fitz.Page, original_rect: fitz.Rect) -> dict:
    """Extracts font metadata (size, color, flags) based on original text intersecting the rect."""
    metadata = {
        "fontsize": 0.0,
        "color": (0, 0, 0),
        "font_flags": 0,
        "fontname": "helv"
    }
    
    sizes = []
    colors = []
    flags = []
    fontnames = []
    
    text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)
    for block in text_dict["blocks"]:
        if block["type"] != 0: continue # Only text blocks
        for line in block["lines"]:
            for span in line["spans"]:
                span_rect = fitz.Rect(span["bbox"])
                if span_rect.intersects(original_rect):
                    sizes.append(span["size"])
                    # Convert integer color to RGB tuple
                    c = span["color"]
                    colors.append(((c >> 16 & 255)/255, (c >> 8 & 255)/255, (c & 255)/255))
                    flags.append(span["flags"])
                    fontnames.append(span["font"])

    # Calculate rect-based fontsize as fallback
    rect_height = original_rect.height
    rect_based_fontsize = rect_height * 0.6
    rect_based_fontsize = max(8, min(rect_based_fontsize, 72))

    if sizes:
        metadata["fontsize"] = max(sum(sizes) / len(sizes), rect_based_fontsize)
        # Use most frequent color/flags/fontname if multiple exist
        metadata["color"] = max(set(colors), key=colors.count)
        metadata["font_flags"] = max(set(flags), key=flags.count)
        metadata["fontname"] = max(set(fontnames), key=fontnames.count)
        
        get_logger().debug(f"Extracted metadata: {metadata['fontsize']:.1f}pt, color={metadata['color']}, flags={metadata['font_flags']}, font={metadata['fontname']}")
    else:
        metadata["fontsize"] = rect_based_fontsize
        get_logger().debug(f"Fallback metadata: {metadata['fontsize']:.1f}pt from rect height")
        
    return metadata

class DocumentSession(QObject):
    history_changed = Signal()
    warnings_changed = Signal()

    def __init__(self, file_path: str):
        super().__init__()
        logger = get_logger()
        try:
            self.doc: fitz.Document = open_document(file_path)
            self.file_path = file_path
            self.pages: List[PageModel] = [PageModel(i) for i in range(self.doc.page_count)]
            self.history: List[Operation] = []
            self.redo_stack: List[Operation] = []
            self.modified = False
            # Cache of most-recent preview warnings keyed by page_index.
            # Values are lists of dicts shaped like OpWarning (see operations_service).
            self.last_preview_warnings: Dict[int, List[Dict[str, Any]]] = {}
            log_file_operation("open", file_path, success=True)
            logger.info(f"Document loaded: {self.doc.page_count} pages")
        except Exception as e:
            log_file_operation("open", file_path, success=False, error_msg=str(e))
            raise

    def _bind_document(self, doc: fitz.Document, file_path: str):
        """Swap the active document handle and rebuild per-page caches."""
        old_doc = getattr(self, "doc", None)
        self.doc = doc
        self.file_path = file_path
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]

        if old_doc is not None and old_doc is not doc:
            old_doc.close()

    def add_operation(self, operation: Operation):
        if isinstance(operation, RemoveSectionAsImage):
            already_exists = any(
                isinstance(existing, RemoveSectionAsImage)
                and existing.page_index == operation.page_index
                for existing in self.history
            )
            if already_exists:
                raise ValueError("Only one section removal operation is allowed per page.")

        self.history.append(operation)
        self.redo_stack.clear()
        self.modified = True
        self.history_changed.emit()
        log_operation(operation.__class__.__name__, operation.page_index, len(operation.rects))

    def update_warnings(self, page_index: int, warnings: List[Dict[str, Any]]) -> None:
        """Update the cached preview warnings for a page and notify observers.

        Passing an empty list clears warnings for that page. This is the
        single entry point UI code should use to reflect preview fit issues.
        """
        if warnings:
            self.last_preview_warnings[page_index] = list(warnings)
        else:
            self.last_preview_warnings.pop(page_index, None)
        self.warnings_changed.emit()

    def has_blocking_warnings(self) -> bool:
        """True if any cached warning has severity 'error' (hard overflow)."""
        for warnings in self.last_preview_warnings.values():
            for w in warnings:
                if w.get("severity") == "error":
                    return True
        return False

    def undo(self) -> Optional[Operation]:
        if self.history:
            op = self.history.pop()
            self.redo_stack.append(op)
            self.modified = bool(self.history)
            get_logger().info(f"Undo: {op.__class__.__name__} on page {op.page_index}")
            self.history_changed.emit()
            return op
        return None

    def redo(self) -> Optional[Operation]:
        if self.redo_stack:
            op = self.redo_stack.pop()
            self.history.append(op)
            self.modified = True
            get_logger().info(f"Redo: {op.__class__.__name__} on page {op.page_index}")
            self.history_changed.emit()
            return op
        return None

    def apply_operations_to_page(self, page: fitz.Page, page_index: int):
        """
        Applies all operations for a page using OperationApplicator service.
        
        This method now delegates to the unified OperationApplicator service,
        which handles all the multi-pass logic for applying operations.
        """
        # Filter operations for this page
        operations_for_page = [op for op in self.history if op.page_index == page_index]
        
        if not operations_for_page:
            return
        
        apply_page_operations(page, operations_for_page, mode=ApplyMode.SAVE, logger=get_logger())

    def save_document(self, output_path: str):
        logger = get_logger()
        try:
            logger.info(f"Saving document: {len(self.history)} operations to apply")
            save_document_copy(self.file_path, output_path, self.history, logger=logger)

            reloaded_doc = open_document(output_path)
            self._bind_document(reloaded_doc, output_path)

            self.history.clear()
            self.redo_stack.clear()
            self.modified = False
            self.history_changed.emit()
            log_file_operation("save", output_path, success=True)
        except Exception as e:
            log_file_operation("save", output_path, success=False, error_msg=str(e))
            raise
    
    # ── Page Management (direct document manipulation) ──────────────

    def rotate_page(self, page_index: int, angle: int):
        """Rotate a page by the given angle (must be multiple of 90)."""
        if angle % 90 != 0:
            raise ValueError(f"Rotation angle must be a multiple of 90, got {angle}")
        page = self.doc[page_index]
        page.set_rotation((page.rotation + angle) % 360)
        self.pages[page_index].clear_cache()
        self.modified = True
        get_logger().info(f"Rotated page {page_index} by {angle}° (now {page.rotation}°)")

    def delete_pages(self, page_indices: List[int]):
        """Delete pages by indices (0-based). Indices are sorted descending to avoid shifting."""
        if len(page_indices) >= self.doc.page_count:
            raise ValueError("Cannot delete all pages")
        # Delete from last to first to keep indices stable
        for idx in sorted(page_indices, reverse=True):
            self.doc.delete_page(idx)
            # Remove operations referencing deleted page, adjust indices
            self.history = [
                op for op in self.history if op.page_index != idx
            ]
            for op in self.history:
                if op.page_index > idx:
                    op.page_index -= 1
            self.redo_stack.clear()
        # Rebuild page models
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]
        self.modified = True
        self.history_changed.emit()
        get_logger().info(f"Deleted {len(page_indices)} page(s)")

    def move_page(self, from_index: int, to_index: int):
        """Move a page from one position to another."""
        if from_index == to_index:
            return
        self.doc.move_page(from_index, to_index)
        # Rebuild page models and adjust operation indices
        self._rebuild_after_reorder()
        get_logger().info(f"Moved page {from_index} → {to_index}")

    def insert_blank_page(self, after_index: int = -1, width: float = 595, height: float = 842):
        """Insert a blank page (default A4) after the specified index. -1 means at the end."""
        if after_index == -1:
            insert_at = self.doc.page_count
        else:
            insert_at = after_index + 1
        self.doc.new_page(insert_at, width=width, height=height)
        # Adjust operation indices
        for op in self.history:
            if op.page_index >= insert_at:
                op.page_index += 1
        self.redo_stack.clear()
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]
        self.modified = True
        self.history_changed.emit()
        get_logger().info(f"Inserted blank page at index {insert_at}")

    def _rebuild_after_reorder(self):
        """Rebuild page models after page reorder. Clears operation history as indices are invalidated."""
        self.history.clear()
        self.redo_stack.clear()
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]
        self.modified = True
        self.history_changed.emit()

    def duplicate_pages(self, page_indices: List[int]) -> int:
        """Duplicate the given pages, inserting each copy directly after the original.

        Indices are 0-based. Duplication is processed in descending order so
        that earlier indices remain valid while later ones expand.
        Pending edit history is invalidated because page indices shift.
        """
        if not page_indices:
            raise ValueError("page_indices must not be empty")
        if len(set(page_indices)) != len(page_indices):
            raise ValueError("page_indices must not contain duplicates")
        page_count = self.doc.page_count
        for idx in page_indices:
            if idx < 0 or idx >= page_count:
                raise IndexError(f"page index out of range: {idx}")
        for idx in sorted(page_indices, reverse=True):
            current_count = self.doc.page_count
            target = idx + 1 if idx + 1 < current_count else -1
            self.doc.copy_page(idx, target)
        self._rebuild_after_reorder()
        get_logger().info(f"Duplicated {len(page_indices)} page(s)")
        return len(page_indices)

    def extract_pages(self, page_indices: List[int], output_path: str) -> None:
        """Save the selected pages to a new PDF file. The source document is unchanged.

        Raises ValueError on empty input or destination conflict, IndexError on
        invalid page indices.
        """
        if not page_indices:
            raise ValueError("page_indices must not be empty")
        page_count = self.doc.page_count
        for idx in page_indices:
            if idx < 0 or idx >= page_count:
                raise IndexError(f"page index out of range: {idx}")
        if not output_path:
            raise ValueError("output_path must not be empty")
        parent_dir = os.path.dirname(os.path.abspath(output_path))
        if parent_dir and not os.path.isdir(parent_dir):
            raise ValueError(f"output directory does not exist: {parent_dir}")
        if self.file_path and os.path.abspath(output_path) == os.path.abspath(self.file_path):
            raise ValueError("Cannot overwrite source document")

        new_doc = fitz.open()
        try:
            for idx in page_indices:
                new_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
            new_doc.save(output_path)
        finally:
            new_doc.close()
        get_logger().info(
            f"Extracted {len(page_indices)} page(s) to {output_path}"
        )

    def merge_pdf(self, source_path: str, after_index: int = -1) -> int:
        """Insert every page from another PDF after the given index (-1 = end).

        Returns the number of pages inserted. Raises FileNotFoundError if the
        source file does not exist and ValueError on invalid PDF / index.
        """
        if not source_path or not os.path.isfile(source_path):
            raise FileNotFoundError(f"PDF not found: {source_path}")
        page_count = self.doc.page_count
        if after_index != -1 and (after_index < 0 or after_index >= page_count):
            raise ValueError(f"after_index out of range: {after_index}")
        try:
            src = fitz.open(source_path)
        except Exception as e:
            raise ValueError(f"Invalid PDF: {e}") from e
        try:
            added = src.page_count
            start_at = page_count if after_index == -1 else after_index + 1
            self.doc.insert_pdf(src, start_at=start_at)
        finally:
            src.close()
        self._rebuild_after_reorder()
        get_logger().info(
            f"Merged {added} page(s) from {source_path} starting at index {start_at}"
        )
        return added

    def close(self):
        if self.doc:
            log_file_operation("close", self.file_path, success=True)
            self.doc.close()
            self.doc = None

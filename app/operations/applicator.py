"""Operation Application Service — orchestrator.

Stateless, mode-aware multi-pass applicator for PDF operations. Unifies
preview and save paths to eliminate code duplication.

Design: Stateless service pattern for thread-safe operation application.
"""

import os
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import fitz

from app.config import (
    FONT_FLAG_BOLD,
    FONT_FLAG_ITALIC,
    FONT_FLAG_MONOSPACE,
    FONT_FLAG_SERIF,
    TEXT_AUTOFIT_ITERATIONS,
    TEXT_AUTOFIT_MIN_FONT_SIZE,
    TEXT_AUTOFIT_WIDTH_RATIO,
    TEXT_BOX_X_PADDING,
    TEXT_DEFAULT_COLOR,
    TEXT_DEFAULT_FONT_SIZE,
    TEXT_EXTEND_MAX_RATIO,
    TEXT_EXTEND_MIN_FONT_FACTOR,
    TEXT_PREVIEW_BLACK_COLOR,
    TEXT_WORD_GAP_FACTOR,
    TEXT_WRAP_BOTTOM_MARGIN,
    TEXT_WRAP_ENABLED,
    TEXT_WRAP_LINE_HEIGHT_FACTOR,
)
from app.fonts import extract_embedded_font, resolve_pdf_fontname
from app.logger import get_logger
from app.operations.crop import CropMargins
from app.operations.redact import ALIGN_AUTO, ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT, RedactDelete, RedactReplace
from app.operations.remove_section import RemoveSectionAsImage
from app.operations.types import ApplyMode, TextMetadata
from app.operations.warnings import ApplyResult, OpWarning
from app.operations.watermark import WatermarkImage, WatermarkText
from app.page_probe import is_numeric_text, sample_background_color
from app.text_metadata import _extract_text_metadata


@dataclass
class TextLayout:
    """Result of :meth:`OperationApplicator._compute_text_layout`."""

    lines: List[str]
    fontsize: float
    positions: List[Tuple[float, float]] = field(default_factory=list)  # (x, baseline y) per line
    wrapped: bool = False
    shrunk: bool = False
    overflow: bool = False
    width_limit: float = 0.0


class OperationApplicator:
    """
    Stateless service for applying PDF operations to pages.

    This service provides a unified implementation for both preview and save
    operations, eliminating code duplication and ensuring consistency.

    Key Features:
    - Thread-safe (stateless design)
    - Mode-aware (SAVE vs PREVIEW)
    - Deterministic (pure function)
    - Testable (no side effects)

    Usage:
        applicator = OperationApplicator()
        applicator.apply_operations(page, operations, ApplyMode.SAVE)
    """

    def __init__(self, logger: Optional[Any] = None) -> None:
        """
        Initialize the applicator with optional dependencies.

        Args:
            logger: Optional logger instance. If None, uses global logger.
        """
        self.logger = logger or get_logger()

    def _base14_font_alias(self, fontname: str, font_flags: int) -> str:
        """Choose a PyMuPDF Base-14 alias from extracted font metadata."""
        normalized = (fontname or "").lower()
        is_bold = bool(font_flags & FONT_FLAG_BOLD) or "bold" in normalized or "black" in normalized
        is_italic = bool(font_flags & FONT_FLAG_ITALIC) or "italic" in normalized or "oblique" in normalized
        is_mono = bool(font_flags & FONT_FLAG_MONOSPACE) or any(
            token in normalized for token in ("courier", "consolas", "mono")
        )
        is_serif = bool(font_flags & FONT_FLAG_SERIF) or any(
            token in normalized for token in ("times", "serif", "georgia", "roman")
        )

        if is_mono:
            if is_bold and is_italic:
                return "cobi"
            if is_bold:
                return "cobo"
            if is_italic:
                return "coit"
            return "cour"

        if is_serif:
            if is_bold and is_italic:
                return "tibi"
            if is_bold:
                return "tibo"
            if is_italic:
                return "tiit"
            return "tiro"

        if is_bold and is_italic:
            return "hebi"
        if is_bold:
            return "hebo"
        if is_italic:
            return "heit"
        return "helv"

    def apply_operations(
        self,
        page: fitz.Page,
        operations: List[Any],  # List[Operation], but avoiding circular import
        mode: ApplyMode = ApplyMode.SAVE,
    ) -> ApplyResult:
        """
        Apply operations to a page using multi-pass approach.

        This is the main entry point. It orchestrates the multi-pass
        operation application strategy:
        - Pass 0: Crop (changes page geometry)
        - Pass 1: Font preparation
        - Pass 2: Clear areas (mode-specific)
        - Pass 3: Insert replacement text
        - Pass 4: Section removal (preview/save on isolated page copies)

        Args:
            page: PyMuPDF page object to modify
            operations: List of Operation objects to apply
            mode: SAVE (destructive) or PREVIEW (non-destructive)

        Returns:
            ApplyResult with success status, warnings, and metrics

        Raises:
            Exception: If operation application fails critically
        """
        # Initialize result
        result = ApplyResult(success=True, operations_applied=len(operations))

        if not operations:
            return result

        self.logger.debug(f"Applying {len(operations)} operations in {mode.value} mode")

        warnings: List[OpWarning] = []

        # Pass 0: Crop operations (changes page geometry)
        self._apply_crop_operations(page, operations)

        # Filter redaction operations
        redactions = [op for op in operations if isinstance(op, (RedactDelete, RedactReplace))]

        if redactions:
            # Pre-Pass 1: Extract source text metadata (size/color/font/baseline).
            # Must run before fonts AND before the areas are cleared.
            font_sizes = self._calculate_font_sizes(page, redactions)

            # Pre-Pass 2: Resolve fonts (explicit file > system match >
            # embedded program > Base-14). Extraction of an embedded program
            # must happen BEFORE redactions remove the source text/resources.
            resolved_fonts = self._prepare_fonts(page, redactions, font_sizes)

            # Pass 2: Clear areas (mode-specific behavior)
            if mode == ApplyMode.SAVE:
                self._apply_redactions_destructive(page, redactions)
            else:
                self._apply_redactions_preview(page, redactions)

            # Pass 2.5: Register resolved fonts on the page. Must happen
            # AFTER apply_redactions, which strips font resources that no
            # remaining text references (a pre-registered, not-yet-used
            # alias would be dropped and the buffer-based insert would fail
            # with "need font file or buffer").
            resolved_fonts = self._register_fonts(page, resolved_fonts, font_sizes)

            # Pass 3: Insert replacement text
            self._insert_replacement_text(page, redactions, resolved_fonts, font_sizes, mode, warnings)

        # Pass 4: Section removal. In preview this is still safe because the
        # viewer renders against a detached temporary single-page document.
        if operations:
            self._apply_section_removal(page, operations)

        # Pass 5: Watermark overlay -- LAST, so it sits on top of everything
        # (including a section-removal raster). Non-destructive, so SAVE and
        # PREVIEW share this pass with no mode branch.
        for op in operations:
            if isinstance(op, (WatermarkText, WatermarkImage)):
                op.apply(page)

        # Collect warnings (counts are derived via properties)
        result.warnings = warnings

        return result

    def _apply_crop_operations(self, page: fitz.Page, operations: List[Any]) -> None:
        """
        Apply CropMargins operations to the page.

        Cropping must be done first as it changes page geometry.
        """
        for op in operations:
            if isinstance(op, CropMargins):
                op.apply(page)
                self.logger.debug(f"Applied crop: top={op.top}, bottom={op.bottom}, left={op.left}, right={op.right}")

    def _prepare_fonts(
        self,
        page: fitz.Page,
        operations: List[Any],
        text_metadata: Dict[int, TextMetadata],
    ) -> Dict[int, Tuple[str, Optional[str], Optional[bytes]]]:
        """
        Resolve each replacement's font and register it on the page.

        Priority chain (text-fidelity + embedded-font-reuse):
        1. ``op.fontfile`` -- an explicit user choice always wins.
        2. System font matched from the EXTRACTED source font name/flags
           (glyph coverage of the replacement text is verified).
        3. The font program EMBEDDED in the PDF itself (covers source fonts
           that are not installed on this machine; subset embeds are
           rejected by the coverage probe).
        4. Base-14 alias derived from the extracted name/flags. (Previously
           this used ``op.fontname``, which batch-created ops always left at
           the "helv" default -- the extracted name is the faithful source.)

        Returns:
            Dict mapping operation index to ``(alias, fontfile, fontbuffer)``
            -- at most one of ``fontfile``/``fontbuffer`` is set; both are
            None for the Base-14 case.
        """
        resolved: Dict[int, Tuple[str, Optional[str], Optional[bytes]]] = {}

        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            meta = text_metadata.get(i)
            source_fontname = meta["fontname"] if meta else op.fontname
            source_flags = meta["font_flags"] if meta else op.font_flags

            fontfile: Optional[str] = None
            fontbuffer: Optional[bytes] = None
            if op.fontfile and os.path.exists(op.fontfile):
                fontfile = op.fontfile
            else:
                fontfile = resolve_pdf_fontname(source_fontname, source_flags, must_cover=op.new_text)
                if fontfile is None:
                    fontbuffer = extract_embedded_font(page, source_fontname, must_cover=op.new_text)

            if fontfile:
                # Use base filename as alias (e.g., "arial" from "arial.ttf")
                alias = os.path.splitext(os.path.basename(fontfile))[0]
            elif fontbuffer:
                # Content-derived alias: identical programs share an alias
                # (registered once, reused), distinct programs never collide
                # -- which matters when one batch replaces text in several
                # different embedded fonts on the same page.
                alias = f"emb{zlib.crc32(fontbuffer) & 0xFFFFFFFF:08x}"
            else:
                alias = self._base14_font_alias(source_fontname, source_flags)

            resolved[i] = (alias, fontfile, fontbuffer)

        return resolved

    def _register_fonts(
        self,
        page: fitz.Page,
        resolved: Dict[int, Tuple[str, Optional[str], Optional[bytes]]],
        text_metadata: Dict[int, TextMetadata],
    ) -> Dict[int, Tuple[str, Optional[str], Optional[bytes]]]:
        """
        Register resolved file/buffer fonts on the page (post-redaction).

        Kept separate from resolution because ``apply_redactions`` strips
        font resources with no remaining text references -- registering
        before the clear pass would silently drop the alias. A registration
        failure downgrades that entry to its Base-14 alias.
        """
        registered = dict(resolved)
        for i, (alias, fontfile, fontbuffer) in resolved.items():
            if not fontfile and not fontbuffer:
                continue
            try:
                # Check if font is already registered on this page
                # (files surface as their basefont, buffers as the alias).
                is_embedded = any(entry[3] == alias or entry[4] == alias for entry in page.get_fonts(full=True))

                if not is_embedded:
                    if fontfile:
                        page.insert_font(fontname=alias, fontfile=fontfile)
                        self.logger.debug(f"Embedded font '{fontfile}' with alias '{alias}'")
                    else:
                        page.insert_font(fontname=alias, fontbuffer=fontbuffer)
                        self.logger.debug(f"Registered embedded source font as '{alias}'")
                else:
                    self.logger.debug(f"Font '{alias}' already present on page {page.number}")
            except (OSError, IOError, RuntimeError) as e:
                self.logger.error(f"Font embedding failed for alias '{alias}': {e}. Falling back to default.")
                meta = text_metadata.get(i)
                fallback_name = meta["fontname"] if meta else "helv"
                fallback_flags = meta["font_flags"] if meta else 0
                registered[i] = (
                    self._base14_font_alias(fallback_name, fallback_flags),
                    None,
                    None,
                )
        return registered

    def _calculate_font_sizes(self, page: fitz.Page, operations: List[Any]) -> Dict[int, TextMetadata]:
        """
        Build per-operation text metadata (size/color/flags/font/baseline +
        leading, free space on the line, and the source text).

        For operations with fontsize=0 (auto-fit), the fontsize is derived
        from the original text in the bounding box via _extract_text_metadata.
        For operations with an explicit fontsize, that value overrides the
        extracted one while everything else still comes from the source.
        The page's words and drawings are extracted once here and shared by
        every probe (a batch of replacements must not re-parse the page).
        """
        metadata_map: Dict[int, TextMetadata] = {}
        words: Optional[List[Any]] = None
        drawings: Optional[List[Dict[str, Any]]] = None
        if any(isinstance(op, RedactReplace) and op.rects for op in operations):
            try:
                words = page.get_text("words")
            except (RuntimeError, ValueError):
                words = []
            try:
                drawings = page.get_drawings()
            except (RuntimeError, ValueError):
                drawings = []

        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            raw_meta: Dict[str, Any]
            if op.rects:
                raw_meta = dict(_extract_text_metadata(page, op.rects[0], words=words, drawings=drawings))
            else:
                raw_meta = {
                    "fontsize": TEXT_DEFAULT_FONT_SIZE,
                    "color": TEXT_DEFAULT_COLOR,
                    "font_flags": 0,
                    "fontname": op.fontname,
                    "baseline": None,
                    "line_pitch": None,
                    "limit_left": None,
                    "limit_right": None,
                    "source_text": "",
                    "glyph_after": False,
                }

            if op.fontsize and op.fontsize > 0:
                raw_meta["fontsize"] = op.fontsize

            def _opt(key: str) -> Optional[float]:
                value = raw_meta.get(key)
                return float(value) if value is not None else None

            metadata_map[i] = TextMetadata(
                fontsize=float(raw_meta["fontsize"]),
                color=tuple(raw_meta["color"]),
                font_flags=int(raw_meta["font_flags"]),
                fontname=str(raw_meta["fontname"]),
                baseline=_opt("baseline"),
                line_pitch=_opt("line_pitch"),
                limit_left=_opt("limit_left"),
                limit_right=_opt("limit_right"),
                source_text=str(raw_meta.get("source_text") or ""),
                glyph_after=bool(raw_meta.get("glyph_after", False)),
            )

        return metadata_map

    def _background_fills(self, page: fitz.Page, operations: List[Any]) -> Dict[int, Tuple[float, float, float]]:
        """Sample the page background around each redaction (one 72-dpi render)."""
        fills: Dict[int, Tuple[float, float, float]] = {}
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        except (RuntimeError, ValueError) as exc:
            self.logger.debug(f"Background probe render failed: {exc}")
            return fills
        for i, op in enumerate(operations):
            if op.rects:
                fills[i] = sample_background_color(page, op.rects[0], pix)
        return fills

    def _apply_redactions_destructive(self, page: fitz.Page, operations: List[Any]) -> None:
        """
        Apply redactions destructively (for save mode).

        Uses PyMuPDF's redaction API to permanently remove content
        from the PDF. This modifies the document structure.

        Args:
            page: Page to apply redactions to
            operations: RedactDelete and RedactReplace operations
        """
        # Add redaction annotations for all operations, filled with the
        # sampled page background so the cleared area blends in.
        fills = self._background_fills(page, operations)
        for i, op in enumerate(operations):
            op.apply(page, fill=fills.get(i))  # Adds redaction annotations

        # Apply all redactions at once (permanent removal)
        page.apply_redactions()

        self.logger.debug(f"Applied {len(operations)} redactions (destructive)")

    def _apply_redactions_preview(self, page: fitz.Page, operations: List[Any]) -> None:
        """
        Apply redactions non-destructively (for preview mode).

        Uses white rectangles to simulate redaction without modifying
        the underlying document structure. This allows safe preview
        rendering without affecting the original document.

        Args:
            page: Page to draw white boxes on
            operations: RedactDelete and RedactReplace operations
        """
        fills = self._background_fills(page, operations)
        for i, op in enumerate(operations):
            fill = fills.get(i, (1, 1, 1))
            for rect in op.rects:
                # Cover existing content with the sampled background color
                page.draw_rect(rect, fill=fill, color=None)

        self.logger.debug(f"Applied {len(operations)} redactions (non-destructive preview)")

    def _insert_replacement_text(
        self,
        page: fitz.Page,
        operations: List[Any],
        resolved_fonts: Dict[int, Tuple[str, Optional[str], Optional[bytes]]],
        text_metadata: Dict[int, TextMetadata],
        mode: ApplyMode,
        warnings: List[OpWarning],
    ) -> None:
        """
        Insert replacement text for RedactReplace operations.

        Uses extracted metadata, the resolved (matched/explicit) font, the
        probed free space / leading, and the (auto) alignment so the new
        text sits where the old text was.
        """
        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            default_meta: TextMetadata = {
                "fontsize": TEXT_DEFAULT_FONT_SIZE,
                "color": TEXT_DEFAULT_COLOR,
                "font_flags": 0,
                "fontname": op.fontname,
                "baseline": None,
                "line_pitch": None,
                "limit_left": None,
                "limit_right": None,
                "source_text": "",
                "glyph_after": False,
            }
            meta = text_metadata.get(i, default_meta)
            final_fontsize = meta["fontsize"]
            text_color = meta["color"]
            font_flags = meta["font_flags"]
            font_alias, fontfile, fontbuffer = resolved_fonts.get(i, (meta["fontname"], op.fontfile, None))

            # In preview mode, use slightly gray color if black is selected
            if mode == ApplyMode.PREVIEW and text_color == TEXT_DEFAULT_COLOR:
                text_color = TEXT_PREVIEW_BLACK_COLOR

            # Resolve the per-operation wrap policy. None means "follow the
            # global default"; an explicit True/False overrides it.
            op_wrap = getattr(op, "wrap", None)
            wrap_enabled = op_wrap if op_wrap is not None else TEXT_WRAP_ENABLED

            align = getattr(op, "align", ALIGN_AUTO)
            align_is_auto = align not in (ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT)
            if align_is_auto:
                align = self._auto_align(meta.get("source_text", ""), meta.get("glyph_after", False))

            for rect in op.rects:
                self._insert_text_with_autofit(
                    page,
                    rect,
                    op.new_text,
                    font_alias,
                    final_fontsize,
                    fontfile,
                    text_color,
                    font_flags,
                    op_index=i,
                    warnings=warnings,
                    wrap_enabled=wrap_enabled,
                    baseline=meta["baseline"],
                    fontbuffer=fontbuffer,
                    align=align,
                    line_pitch=meta.get("line_pitch"),
                    limit_left=meta.get("limit_left"),
                    limit_right=meta.get("limit_right"),
                    align_is_auto=align_is_auto,
                )

    @staticmethod
    def _auto_align(source_text: str, glyph_after: bool = False) -> int:
        """Numbers / amounts keep their right edge (table figures); else left.

        A number that is followed by more text on the same line is prose
        ("Invoice 12345 due ..."), where left alignment reads naturally.
        """
        return ALIGN_RIGHT if is_numeric_text(source_text) and not glyph_after else ALIGN_LEFT

    @staticmethod
    def _build_font(fontname: str, fontfile: Optional[str], fontbuffer: Optional[bytes]) -> "fitz.Font":
        """Measurement font: embedded buffer > custom file > Base-14 alias."""
        if fontbuffer:
            return fitz.Font(fontbuffer=fontbuffer)
        if fontfile:
            return fitz.Font(fontname=fontname, fontfile=fontfile)
        return fitz.Font(fontname=fontname)

    def _wrap_lines(self, fit_font: "fitz.Font", text: str, fontsize: float, max_width: float) -> List[str]:
        """Greedy word wrap at ``max_width``; explicit newlines force breaks.

        A single word wider than ``max_width`` stays on its own line (the
        caller detects that overflow and falls back to shrinking).
        """
        space_w = fit_font.text_length(" ", fontsize=fontsize)
        lines: List[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            current_w = fit_font.text_length(current, fontsize=fontsize)
            for word in words[1:]:
                word_w = fit_font.text_length(word, fontsize=fontsize)
                if current_w + space_w + word_w <= max_width:
                    current += " " + word
                    current_w += space_w + word_w
                else:
                    lines.append(current)
                    current, current_w = word, word_w
            lines.append(current)
        return lines or [""]

    def _shrink_fontsize_to_width(
        self,
        fit_font: "fitz.Font",
        text: str,
        initial_fontsize: float,
        target_width: float,
    ) -> float:
        """Binary-search the largest font size whose one-line width fits."""
        low, high = TEXT_AUTOFIT_MIN_FONT_SIZE, float(initial_fontsize)
        for _ in range(TEXT_AUTOFIT_ITERATIONS):
            mid = (low + high) / 2
            if fit_font.text_length(text, fontsize=mid) > target_width:
                high = mid
            else:
                low = mid
        return low

    def _compute_text_layout(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        text: str,
        fontname: str,
        initial_fontsize: float,
        fontfile: Optional[str],
        wrap_enabled: bool,
        baseline: Optional[float] = None,
        fontbuffer: Optional[bytes] = None,
        align: int = ALIGN_LEFT,
        line_pitch: Optional[float] = None,
        limit_left: Optional[float] = None,
        limit_right: Optional[float] = None,
        align_is_auto: bool = False,
    ) -> TextLayout:
        """
        Decide lines, font size and per-line baseline positions.

        Policy (natural-replace):
        1. Fits inside the source rect at the source size -> unchanged.
        2. Slightly longer -> extend into measured free space on the same
           line (towards the next glyph / table rule), capped at
           ``TEXT_EXTEND_MAX_RATIO`` x the source width. Still one line, no
           warning.
        3. Longer still -> wrap inside the source width (font size kept),
           using the source leading when known; needs vertical room.
        4. Wrapping cannot help (unbreakable word / no room / disabled) ->
           shrink; if even the minimum size overflows, mark overflow.

        Every line is placed on an explicit baseline: the source baseline for
        the first line (exact, independent of the page's font metrics) and
        ``line_pitch`` steps below it.
        """
        rect = fitz.Rect(rect).normalize()
        try:
            fit_font = self._build_font(fontname, fontfile, fontbuffer)
        except (RuntimeError, ValueError, TypeError, FileNotFoundError) as exc:
            self.logger.warning(f"Text layout font unavailable ({exc}); using Base-14 fallback metrics")
            fit_font = fitz.Font(fontname="helv")

        size = float(initial_fontsize)
        rect_w = rect.width
        gap = TEXT_WORD_GAP_FACTOR * size
        cap = max(rect_w * TEXT_EXTEND_MAX_RATIO, TEXT_EXTEND_MIN_FONT_FACTOR * size)

        # Extension bounds (only used for the single-line case).
        ext_right = rect.x1 if limit_right is None else min(limit_right - gap, rect.x0 + cap)
        ext_left = rect.x0 if limit_left is None else max(limit_left + gap, rect.x1 - cap)
        ext_right = max(ext_right, rect.x1)
        ext_left = min(ext_left, rect.x0)

        single = "\n" not in text
        width = fit_font.text_length(text, fontsize=size) if single else float("inf")
        lines = [text]
        wrapped = shrunk = overflow = False
        line_width_limit = rect_w

        if width <= rect_w + 0.5:
            pass  # 1. fits as-is
        else:

            def avail_for(a: int) -> float:
                if a == ALIGN_RIGHT:
                    return rect.x1 - ext_left
                if a == ALIGN_CENTER:
                    center = (rect.x0 + rect.x1) / 2
                    return 2 * min(center - ext_left, ext_right - center)
                return ext_right - rect.x0

            avail = avail_for(align)
            if align_is_auto and single and width > avail:
                # The guessed side has no room (e.g. "Ref: 77" right-aligned
                # against its label) -- grow towards whichever side has it.
                for other in (ALIGN_LEFT, ALIGN_RIGHT):
                    if other != align and width <= avail_for(other):
                        align, avail = other, avail_for(other)
                        break
            if single and width <= avail:
                line_width_limit = avail  # 2. extend on one line
            else:
                # 3./4. wrap/shrink inside the padded source width (legacy
                # tolerance), but never past a neighbouring glyph or rule.
                padded = (rect_w + TEXT_BOX_X_PADDING) * TEXT_AUTOFIT_WIDTH_RATIO
                wrap_width = max(rect_w, min(padded, avail))
                line_width_limit = wrap_width
                candidate = self._wrap_lines(fit_font, text, size, wrap_width) if wrap_enabled else [text]
                widest = max(fit_font.text_length(ln, fontsize=size) for ln in candidate)
                pitch = line_pitch if line_pitch else size * TEXT_WRAP_LINE_HEIGHT_FACTOR
                first_base = baseline if baseline is not None else rect.y0 + fit_font.ascender * size
                last_bottom = first_base + pitch * (len(candidate) - 1) - fit_font.descender * size
                has_room = last_bottom <= page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN
                if wrap_enabled and len(candidate) > 1 and widest <= wrap_width and has_room:
                    lines, wrapped = candidate, True
                else:
                    joined = " ".join(text.split())
                    size = self._shrink_fontsize_to_width(fit_font, joined, size, wrap_width)
                    lines, shrunk = [joined], True
                    if fit_font.text_length(joined, fontsize=size) > wrap_width + 0.5:
                        overflow = True

        pitch = line_pitch if line_pitch else size * TEXT_WRAP_LINE_HEIGHT_FACTOR
        first_base = baseline if baseline is not None else rect.y0 + fit_font.ascender * size
        positions: List[Tuple[float, float]] = []
        for n, line in enumerate(lines):
            w = fit_font.text_length(line, fontsize=size)
            if align == ALIGN_RIGHT:
                x = rect.x1 - w
            elif align == ALIGN_CENTER:
                x = (rect.x0 + rect.x1) / 2 - w / 2
            else:
                x = rect.x0
            positions.append((x, first_base + n * pitch))

        return TextLayout(
            lines=lines,
            fontsize=size,
            positions=positions,
            wrapped=wrapped,
            shrunk=shrunk,
            overflow=overflow,
            width_limit=line_width_limit,
        )

    def _insert_text_with_autofit(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        text: str,
        fontname: str,
        initial_fontsize: float,
        fontfile: Optional[str],
        color: Tuple[float, float, float],
        font_flags: int = 0,
        op_index: int = -1,
        warnings: Optional[List[OpWarning]] = None,
        wrap_enabled: bool = TEXT_WRAP_ENABLED,
        baseline: Optional[float] = None,
        fontbuffer: Optional[bytes] = None,
        align: int = ALIGN_LEFT,
        line_pitch: Optional[float] = None,
        limit_left: Optional[float] = None,
        limit_right: Optional[float] = None,
        align_is_auto: bool = False,
    ) -> None:
        """
        Lay the replacement out (see :meth:`_compute_text_layout`) and draw
        each line with ``insert_text`` at its exact baseline.

        ``insert_text`` (a point) rather than ``insert_textbox`` (a box): the
        box variant seats its first line by the metrics of whatever font
        resource the page already holds, which drifted the replacement
        ~1.4pt above the source line on real documents (natural-replace).
        """
        layout = self._compute_text_layout(
            page,
            rect,
            text,
            fontname,
            initial_fontsize,
            fontfile,
            wrap_enabled,
            baseline,
            fontbuffer,
            align,
            line_pitch,
            limit_left,
            limit_right,
            align_is_auto,
        )

        for line, (x, y) in zip(layout.lines, layout.positions):
            if not line:
                continue
            page.insert_text(
                (x, y),
                line,
                fontname=fontname,
                fontsize=layout.fontsize,
                fontfile=fontfile,
                color=color,
            )

        if warnings is None:
            return
        rect_tuple = (rect.x0, rect.y0, rect.x1, rect.y1)
        if layout.overflow:
            self.logger.warning(
                f"Text does not fit even at {layout.fontsize:.2f}pt (orig {initial_fontsize:.2f}pt) "
                f"rect=({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}) text_len={len(text)}"
            )
            warnings.append(
                OpWarning(
                    op_index=op_index,
                    severity="error",
                    code="text.overflow",
                    detail={
                        "fontsize_from": round(initial_fontsize, 2),
                        "fontsize_to": round(layout.fontsize, 2),
                        "text_len": len(text),
                        "rect": rect_tuple,
                    },
                )
            )
        elif layout.shrunk:
            self.logger.warning(
                f"Text resized {initial_fontsize:.2f}pt -> {layout.fontsize:.2f}pt "
                f"rect=({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}) text_len={len(text)}"
            )
            warnings.append(
                OpWarning(
                    op_index=op_index,
                    severity="warn",
                    code="text.shrunk",
                    detail={
                        "fontsize_from": round(initial_fontsize, 2),
                        "fontsize_to": round(layout.fontsize, 2),
                        "text_len": len(text),
                        "rect": rect_tuple,
                    },
                )
            )
        elif layout.wrapped:
            warnings.append(
                OpWarning(
                    op_index=op_index,
                    severity="info",
                    code="text.wrapped",
                    detail={
                        "lines": len(layout.lines),
                        "fontsize": round(layout.fontsize, 2),
                        "text_len": len(text),
                        "rect": rect_tuple,
                    },
                )
            )

    def _apply_section_removal(self, page: fitz.Page, operations: List[Any]) -> None:
        """
        Apply RemoveSectionAsImage operations (save mode only).

        This is destructive and only applies in SAVE mode. It converts
        the page to an image with the middle section removed.

        Note: Only one RemoveSectionAsImage per page is supported.

        Args:
            page: Page to apply section removal to
            operations: List of all operations
        """
        for op in operations:
            if isinstance(op, RemoveSectionAsImage):
                try:
                    op.apply(page)
                    self.logger.info(f"Applied section removal on page {page.number}")
                    # Only one RemoveSectionAsImage per page supported
                    # (subsequent operations would fail due to page replacement)
                    break

                except Exception as e:
                    self.logger.error(f"Section removal failed: {e}")
                    raise  # Re-raise to allow caller to handle

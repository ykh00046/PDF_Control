"""Operation Application Service — orchestrator.

Stateless, mode-aware multi-pass applicator for PDF operations. Unifies
preview and save paths to eliminate code duplication.

Design: Stateless service pattern for thread-safe operation application.
"""

import os
import zlib
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
    TEXT_BOX_Y_PADDING,
    TEXT_DEFAULT_COLOR,
    TEXT_DEFAULT_FONT_SIZE,
    TEXT_PREVIEW_BLACK_COLOR,
    TEXT_SHRINK_FACTOR,
    TEXT_SHRINK_ITERATIONS,
    TEXT_SHRINK_MIN_FONT_SIZE,
    TEXT_WRAP_BOTTOM_MARGIN,
    TEXT_WRAP_ENABLED,
    TEXT_WRAP_LINE_HEIGHT_FACTOR,
)
from app.fonts import extract_embedded_font, resolve_pdf_fontname
from app.logger import get_logger
from app.operations.crop import CropMargins
from app.operations.redact import RedactDelete, RedactReplace
from app.operations.remove_section import RemoveSectionAsImage
from app.operations.types import ApplyMode, TextMetadata
from app.operations.warnings import ApplyResult, OpWarning
from app.operations.watermark import WatermarkImage, WatermarkText
from app.text_metadata import _extract_text_metadata


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
        mode: ApplyMode = ApplyMode.SAVE
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

        self.logger.debug(
            f"Applying {len(operations)} operations in {mode.value} mode"
        )

        warnings: List[OpWarning] = []

        # Pass 0: Crop operations (changes page geometry)
        self._apply_crop_operations(page, operations)

        # Filter redaction operations
        redactions = [op for op in operations
                      if isinstance(op, (RedactDelete, RedactReplace))]

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
            self._insert_replacement_text(
                page, redactions, resolved_fonts, font_sizes, mode, warnings
            )

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

    def _apply_crop_operations(
        self,
        page: fitz.Page,
        operations: List[Any]
    ) -> None:
        """
        Apply CropMargins operations to the page.

        Cropping must be done first as it changes page geometry.
        """
        for op in operations:
            if isinstance(op, CropMargins):
                op.apply(page)
                self.logger.debug(
                    f"Applied crop: top={op.top}, bottom={op.bottom}, "
                    f"left={op.left}, right={op.right}"
                )

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
                fontfile = resolve_pdf_fontname(
                    source_fontname, source_flags, must_cover=op.new_text
                )
                if fontfile is None:
                    fontbuffer = extract_embedded_font(
                        page, source_fontname, must_cover=op.new_text
                    )

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
                is_embedded = any(
                    entry[3] == alias or entry[4] == alias
                    for entry in page.get_fonts(full=True)
                )

                if not is_embedded:
                    if fontfile:
                        page.insert_font(fontname=alias, fontfile=fontfile)
                        self.logger.debug(
                            f"Embedded font '{fontfile}' with alias '{alias}'"
                        )
                    else:
                        page.insert_font(fontname=alias, fontbuffer=fontbuffer)
                        self.logger.debug(
                            f"Registered embedded source font as '{alias}'"
                        )
                else:
                    self.logger.debug(
                        f"Font '{alias}' already present on page {page.number}"
                    )
            except (OSError, IOError, RuntimeError) as e:
                self.logger.error(
                    f"Font embedding failed for alias '{alias}': {e}. "
                    f"Falling back to default."
                )
                meta = text_metadata.get(i)
                fallback_name = meta["fontname"] if meta else "helv"
                fallback_flags = meta["font_flags"] if meta else 0
                registered[i] = (
                    self._base14_font_alias(fallback_name, fallback_flags),
                    None,
                    None,
                )
        return registered

    def _calculate_font_sizes(
        self,
        page: fitz.Page,
        operations: List[Any]
    ) -> Dict[int, TextMetadata]:
        """
        Build per-operation text metadata (fontsize, color, flags, fontname).

        For operations with fontsize=0 (auto-fit), the fontsize is derived
        from the original text in the bounding box via _extract_text_metadata.
        For operations with an explicit fontsize, that value overrides the
        extracted one while color/flags/fontname still come from the source.

        Returns:
            Dict mapping operation index to a metadata dict with keys
            'fontsize', 'color', 'font_flags', 'fontname'.
        """
        metadata_map: Dict[int, TextMetadata] = {}

        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            raw_meta: Dict[str, Any]
            if op.rects:
                raw_meta = dict(_extract_text_metadata(page, op.rects[0]))
            else:
                raw_meta = {
                    "fontsize": TEXT_DEFAULT_FONT_SIZE,
                    "color": TEXT_DEFAULT_COLOR,
                    "font_flags": 0,
                    "fontname": op.fontname,
                    "baseline": None,
                }

            if op.fontsize and op.fontsize > 0:
                raw_meta["fontsize"] = op.fontsize

            raw_baseline = raw_meta.get("baseline")
            metadata_map[i] = TextMetadata(
                fontsize=float(raw_meta["fontsize"]),
                color=tuple(raw_meta["color"]),
                font_flags=int(raw_meta["font_flags"]),
                fontname=str(raw_meta["fontname"]),
                baseline=float(raw_baseline) if raw_baseline is not None else None,
            )

        return metadata_map

    def _apply_redactions_destructive(
        self,
        page: fitz.Page,
        operations: List[Any]
    ) -> None:
        """
        Apply redactions destructively (for save mode).

        Uses PyMuPDF's redaction API to permanently remove content
        from the PDF. This modifies the document structure.

        Args:
            page: Page to apply redactions to
            operations: RedactDelete and RedactReplace operations
        """
        # Add redaction annotations for all operations
        for op in operations:
            op.apply(page)  # Adds redaction annotations

        # Apply all redactions at once (permanent removal)
        page.apply_redactions()

        self.logger.debug(
            f"Applied {len(operations)} redactions (destructive)"
        )

    def _apply_redactions_preview(
        self,
        page: fitz.Page,
        operations: List[Any]
    ) -> None:
        """
        Apply redactions non-destructively (for preview mode).

        Uses white rectangles to simulate redaction without modifying
        the underlying document structure. This allows safe preview
        rendering without affecting the original document.

        Args:
            page: Page to draw white boxes on
            operations: RedactDelete and RedactReplace operations
        """
        for op in operations:
            for rect in op.rects:
                # Draw white rectangle to hide existing content
                page.draw_rect(rect, fill=(1, 1, 1), color=None)

        self.logger.debug(
            f"Applied {len(operations)} redactions (non-destructive preview)"
        )

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

        Uses extracted metadata, the resolved (matched/explicit) font, and
        fallback shrinking to ensure text fits within the rectangles.
        """
        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            # Get working values from metadata
            default_meta: TextMetadata = {
                "fontsize": TEXT_DEFAULT_FONT_SIZE,
                "color": TEXT_DEFAULT_COLOR,
                "font_flags": 0,
                "fontname": op.fontname,
                "baseline": None,
            }
            meta = text_metadata.get(i, default_meta)
            final_fontsize = meta["fontsize"]
            text_color = meta["color"]
            font_flags = meta["font_flags"]
            font_alias, fontfile, fontbuffer = resolved_fonts.get(
                i, (meta["fontname"], op.fontfile, None)
            )

            # In preview mode, use slightly gray color if black is selected
            if mode == ApplyMode.PREVIEW and text_color == TEXT_DEFAULT_COLOR:
                text_color = TEXT_PREVIEW_BLACK_COLOR

            # Resolve the per-operation wrap policy. None means "follow the
            # global default"; an explicit True/False overrides it.
            op_wrap = getattr(op, "wrap", None)
            wrap_enabled = op_wrap if op_wrap is not None else TEXT_WRAP_ENABLED

            # Insert text for each rectangle
            for rect in op.rects:
                self._insert_text_with_autofit(
                    page, rect, op.new_text,
                    font_alias, final_fontsize,
                    fontfile, text_color, font_flags,
                    op_index=i,
                    warnings=warnings,
                    wrap_enabled=wrap_enabled,
                    baseline=meta["baseline"],
                    fontbuffer=fontbuffer,
                )

    def _wrap_line_count(
        self,
        fit_font: "fitz.Font",
        text: str,
        fontsize: float,
        max_width: float,
    ) -> Tuple[int, float]:
        """
        Estimate how many lines ``text`` needs when wrapped at ``max_width``.

        Mirrors ``insert_textbox``'s whitespace-based greedy wrapping so we can
        decide the box height *before* the single insert call. Also returns the
        widest single token: if that exceeds ``max_width``, wrapping alone cannot
        make the text fit (the word itself overflows), so the caller should fall
        back to font shrinking instead.

        Args:
            fit_font: Pre-built ``fitz.Font`` used to measure widths.
            text: The replacement text.
            fontsize: Font size to measure at.
            max_width: Usable line width (already padding-/ratio-adjusted).

        Returns:
            ``(line_count, longest_token_width)`` where ``line_count >= 1``.
        """
        words = text.split()
        if not words:
            return 1, 0.0

        space_w = fit_font.text_length(" ", fontsize=fontsize)
        longest_token = 0.0
        lines = 1
        current = 0.0

        for word in words:
            word_w = fit_font.text_length(word, fontsize=fontsize)
            longest_token = max(longest_token, word_w)
            if current <= 0.0:
                current = word_w  # first word on a line always fits the line
            elif current + space_w + word_w <= max_width:
                current += space_w + word_w  # append to current line
            else:
                lines += 1  # wrap onto a new line
                current = word_w

        return lines, longest_token

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
    ) -> None:
        """
        Insert text, preferring word-wrap over font shrinking.

        Strategy (see text-wrap-replace design):
        1. Fits on one line at its intended size  -> insert unchanged.
        2. Does not fit -> try wrapping onto multiple lines by expanding the
           box downward (font size preserved). Used when every word fits the
           width and there is vertical room before the page edge.
        3. Wrapping cannot help (an unbreakable word wider than the box, or not
           enough vertical room) -> shrink the font (legacy behavior).

        Args:
            wrap_enabled: Per-call word-wrap policy. Defaults to the global
                ``TEXT_WRAP_ENABLED`` so direct callers keep legacy behavior;
                ``apply_operations`` passes the per-operation override here.
                When False, step 2 is skipped and the text shrinks to fit.
            baseline: First-line baseline y of the source text. When given,
                the insertion box is shifted so the replacement sits on the
                original baseline (text-fidelity); None keeps the legacy
                box-top placement.
            fontbuffer: Embedded font program reused from the source PDF
                (embedded-font-reuse). Used for measurement; insertion then
                references the alias that ``_prepare_fonts`` registered on
                this page via ``insert_font(fontbuffer=)``.
        """
        expanded_rect, final_fontsize, wrapped_lines, autofit_shrunk = (
            self._compute_text_layout(
                page, rect, text, fontname, initial_fontsize, fontfile,
                wrap_enabled, baseline, fontbuffer,
            )
        )

        # Try insert_textbox for better layout handling. A buffer-based font
        # is referenced purely by its page-registered alias (fontfile=None).
        result = page.insert_textbox(
            expanded_rect,
            text,
            fontname=fontname,
            fontsize=final_fontsize,
            fontfile=fontfile,
            align=0,
            color=color,
            # PyMuPDF doesn't directly support flags in insert_textbox,
            # but we can simulate it with fontname if needed (e.g. helv-bold)
            # For now we use the passed fontname which might already be aliased
        )

        # Fallback: shrink if didn't fit
        if result < 0:
            self._insert_with_shrink(
                page, expanded_rect, text,
                fontname, final_fontsize,
                fontfile, color, rect,
                op_index=op_index,
                warnings=warnings,
            )
        elif autofit_shrunk and warnings is not None:
            # autofit already brought the text inside the box by reducing the
            # font size; surface that as a non-blocking shrink warning so the
            # user knows the replacement was scaled down.
            warnings.append(OpWarning(
                op_index=op_index,
                severity="warn",
                code="text.shrunk",
                detail={
                    "fontsize_from": round(initial_fontsize, 2),
                    "fontsize_to": round(final_fontsize, 2),
                    "text_len": len(text),
                    "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
                },
            ))
        elif wrapped_lines > 1 and warnings is not None:
            # Text was preserved at its intended size by wrapping onto multiple
            # lines. This is a successful, non-blocking outcome (info severity).
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
    ) -> Tuple[fitz.Rect, float, int, bool]:
        """
        Decide box geometry and font size before the single insert call.

        Implements the wrap-first policy on top of the padded box:
        a one-line fit keeps everything unchanged; an overflow first tries
        wrapping (grow the box downward, preserve the font size) and only
        falls back to a width-based binary-search shrink when wrapping
        cannot help. Measurement failures fall back to the initial values
        (insert_textbox's own shrink fallback still applies downstream).

        When ``baseline`` is given, the final box is shifted vertically so
        the first inserted line sits on the source baseline
        (``insert_textbox``'s first baseline lands at
        ``y0 + ascender * fontsize``). Skipped when the shift would leave
        the page or measurement failed.

        Returns:
            ``(expanded_rect, final_fontsize, wrapped_lines, autofit_shrunk)``
            where ``wrapped_lines > 1`` only when the box was grown for
            wrapping and ``autofit_shrunk`` marks a binary-search shrink.
        """
        # Expand rect for better fit
        expanded_rect = fitz.Rect(
            rect.x0, rect.y0,
            rect.x1 + TEXT_BOX_X_PADDING,
            rect.y1 + TEXT_BOX_Y_PADDING,
        )

        final_fontsize = initial_fontsize
        autofit_shrunk = False
        wrapped_lines = 0
        try:
            # PyMuPDF >= 1.26 removed Page.get_text_length(); width is now
            # measured via fitz.Font.text_length(). Build the Font once and
            # reuse it for every probe. An embedded buffer or custom fontfile
            # takes precedence over the Base-14 alias name.
            if fontbuffer:
                fit_font = fitz.Font(fontbuffer=fontbuffer)
            elif fontfile:
                fit_font = fitz.Font(fontname=fontname, fontfile=fontfile)
            else:
                fit_font = fitz.Font(fontname=fontname)
            target_width = expanded_rect.width * TEXT_AUTOFIT_WIDTH_RATIO

            # Only act when the text does not already fit on one line at its
            # intended size. Keeping the original size when it fits preserves
            # visual parity and avoids spurious warnings.
            if fit_font.text_length(text, fontsize=initial_fontsize) > target_width:
                wrapped_rect = (
                    self._grow_rect_for_wrap(
                        page, fit_font, expanded_rect, text,
                        initial_fontsize, target_width,
                    )
                    if wrap_enabled
                    else None
                )
                if wrapped_rect is not None:
                    expanded_rect, wrapped_lines = wrapped_rect
                else:
                    # --- Fallback: width-based font shrink via binary search ---
                    final_fontsize = self._shrink_fontsize_to_width(
                        fit_font, text, initial_fontsize, target_width
                    )
                    autofit_shrunk = True

            # --- Baseline anchoring (text-fidelity) ---
            # insert_textbox puts the first baseline at y0 + ascender * size,
            # so shifting the whole box re-seats the replacement exactly on
            # the source baseline (uses the FINAL size in case of a shrink).
            if baseline is not None:
                anchored_y0 = baseline - fit_font.ascender * final_fontsize
                dy = anchored_y0 - expanded_rect.y0
                anchored_y1 = expanded_rect.y1 + dy
                if anchored_y0 >= 0.0 and anchored_y1 <= page.rect.y1:
                    expanded_rect = fitz.Rect(
                        expanded_rect.x0, anchored_y0,
                        expanded_rect.x1, anchored_y1,
                    )
        except (RuntimeError, ValueError, TypeError, FileNotFoundError) as exc:
            self.logger.warning(
                "Text autofit calculation failed; using initial fontsize "
                f"{initial_fontsize:.2f}pt: {exc}"
            )

        return expanded_rect, final_fontsize, wrapped_lines, autofit_shrunk

    def _grow_rect_for_wrap(
        self,
        page: fitz.Page,
        fit_font: "fitz.Font",
        expanded_rect: fitz.Rect,
        text: str,
        fontsize: float,
        target_width: float,
    ) -> Optional[Tuple[fitz.Rect, int]]:
        """
        Try the wrap-first strategy: grow the box downward to fit all lines.

        Wrapping only helps when the text actually breaks into more than one
        line, the widest single word fits the line width, and there is enough
        vertical room before the page edge. Returns the grown rect and line
        count, or None when wrapping cannot make the text fit.
        """
        lines, longest_token = self._wrap_line_count(
            fit_font, text, fontsize, target_width
        )
        if lines <= 1 or longest_token > target_width:
            return None

        line_h = fontsize * TEXT_WRAP_LINE_HEIGHT_FACTOR
        needed_h = lines * line_h + TEXT_BOX_Y_PADDING
        avail_h = (page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN) - expanded_rect.y0
        if needed_h > avail_h:
            return None

        # Grow the box downward; keep the original font size.
        grown = fitz.Rect(
            expanded_rect.x0, expanded_rect.y0,
            expanded_rect.x1, expanded_rect.y0 + needed_h,
        )
        return grown, lines

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

    def _insert_with_shrink(
        self,
        page: fitz.Page,
        expanded_rect: fitz.Rect,
        text: str,
        fontname: str,
        initial_size: float,
        fontfile: Optional[str],
        color: Tuple[float, float, float],
        original_rect: fitz.Rect,
        op_index: int = -1,
        warnings: Optional[List[OpWarning]] = None,
    ) -> None:
        """
        Fallback: shrink font until text fits.

        Tries a configured number of shrink iterations. If still doesn't fit,
        logs a warning but continues.

        Args:
            page: Page to insert into
            expanded_rect: Expanded rectangle for insertion
            text: Text to insert
            fontname: Font name
            initial_size: Initial font size
            fontfile: Optional font file path
            color: RGB color tuple
            original_rect: Original rectangle (for logging)
        """
        fallback_size = initial_size

        for _ in range(TEXT_SHRINK_ITERATIONS):
            fallback_size = max(TEXT_SHRINK_MIN_FONT_SIZE, fallback_size * TEXT_SHRINK_FACTOR)

            result = page.insert_textbox(
                expanded_rect,
                text,
                fontname=fontname,
                fontsize=fallback_size,
                fontfile=fontfile,
                align=0,
                color=color
            )

            if result >= 0:
                self.logger.warning(
                    f"Text resized {initial_size:.2f}pt -> {fallback_size:.2f}pt "
                    f"rect=({original_rect.x0:.1f},{original_rect.y0:.1f},"
                    f"{original_rect.x1:.1f},{original_rect.y1:.1f}) text_len={len(text)}"
                )
                if warnings is not None:
                    warnings.append(OpWarning(
                        op_index=op_index,
                        severity="warn",
                        code="text.shrunk",
                        detail={
                            "fontsize_from": round(initial_size, 2),
                            "fontsize_to": round(fallback_size, 2),
                            "text_len": len(text),
                            "rect": (original_rect.x0, original_rect.y0,
                                     original_rect.x1, original_rect.y1),
                        },
                    ))
                return

        # Still failed after configured shrinks
        self.logger.warning(
            f"Text insertion failed at {fallback_size:.2f}pt (orig {initial_size:.2f}pt) "
            f"rect=({original_rect.x0:.1f},{original_rect.y0:.1f},"
            f"{original_rect.x1:.1f},{original_rect.y1:.1f}) text_len={len(text)}"
        )
        if warnings is not None:
            warnings.append(OpWarning(
                op_index=op_index,
                severity="error",
                code="text.overflow",
                detail={
                    "fontsize_from": round(initial_size, 2),
                    "fontsize_to": round(fallback_size, 2),
                    "text_len": len(text),
                    "rect": (original_rect.x0, original_rect.y0,
                             original_rect.x1, original_rect.y1),
                },
            ))

    def _apply_section_removal(
        self,
        page: fitz.Page,
        operations: List[Any]
    ) -> None:
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
                    self.logger.info(
                        f"Applied section removal on page {page.number}"
                    )
                    # Only one RemoveSectionAsImage per page supported
                    # (subsequent operations would fail due to page replacement)
                    break

                except Exception as e:
                    self.logger.error(f"Section removal failed: {e}")
                    raise  # Re-raise to allow caller to handle

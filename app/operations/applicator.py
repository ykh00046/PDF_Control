"""Operation Application Service — orchestrator.

Stateless, mode-aware multi-pass applicator for PDF operations. Unifies
preview and save paths to eliminate code duplication.

Design: Stateless service pattern for thread-safe operation application.
"""

import os
import fitz
from typing import Any, List, Dict, Tuple, Optional

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
from app.logger import get_logger
from app.operations.types import ApplyMode, TextMetadata
from app.operations.warnings import ApplyResult, OpWarning


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
        from app.model import RedactDelete, RedactReplace, CropMargins, RemoveSectionAsImage

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
            # Pre-Pass 1: Font embedding and alias mapping
            font_aliases = self._prepare_fonts(page, redactions)

            # Pre-Pass 2: Calculate optimal font sizes
            font_sizes = self._calculate_font_sizes(page, redactions)

            # Pass 2: Clear areas (mode-specific behavior)
            if mode == ApplyMode.SAVE:
                self._apply_redactions_destructive(page, redactions)
            else:
                self._apply_redactions_preview(page, redactions)

            # Pass 3: Insert replacement text
            self._insert_replacement_text(
                page, redactions, font_aliases, font_sizes, mode, warnings
            )

        # Pass 4: Section removal. In preview this is still safe because the
        # viewer renders against a detached temporary single-page document.
        if operations:
            self._apply_section_removal(page, operations)

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
        from app.model import CropMargins

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
        operations: List[Any]
    ) -> Dict[int, str]:
        """
        Embed custom fonts and return alias mapping.

        For each RedactReplace operation with a custom font file,
        this embeds the font into the page and returns the alias to use.

        Args:
            page: Page to embed fonts into
            operations: List of operations (filtered to redactions)

        Returns:
            Dict mapping operation index to font alias string
        """
        from app.model import RedactReplace

        font_aliases = {}

        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            alias = self._base14_font_alias(op.fontname, op.font_flags)

            if op.fontfile and os.path.exists(op.fontfile):
                # Use base filename as alias (e.g., "arial" from "arial.ttf")
                alias = os.path.splitext(os.path.basename(op.fontfile))[0]

                try:
                    # Check if font is already embedded on this page
                    is_embedded = any(
                        font[3] == alias for font in page.get_fonts()
                    )

                    if not is_embedded:
                        page.insert_font(fontname=alias, fontfile=op.fontfile)
                        self.logger.debug(
                            f"Embedded font '{op.fontfile}' with alias '{alias}'"
                        )
                    else:
                        self.logger.debug(
                            f"Font '{alias}' already present on page {page.number}"
                        )

                except (OSError, IOError) as e:
                    self.logger.error(
                        f"Font embedding failed for '{op.fontfile}': {e}. "
                        f"Falling back to default."
                    )
                    alias = op.fontname  # Fallback to default

            font_aliases[i] = alias

        return font_aliases

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
        from app.model import RedactReplace, _extract_text_metadata

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
                }

            if op.fontsize and op.fontsize > 0:
                raw_meta["fontsize"] = op.fontsize

            metadata_map[i] = TextMetadata(
                fontsize=float(raw_meta["fontsize"]),
                color=tuple(raw_meta["color"]),
                font_flags=int(raw_meta["font_flags"]),
                fontname=str(raw_meta["fontname"]),
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
        font_aliases: Dict[int, str],
        text_metadata: Dict[int, TextMetadata],
        mode: ApplyMode,
        warnings: List[OpWarning],
    ) -> None:
        """
        Insert replacement text for RedactReplace operations.

        Uses extracted metadata and fallback shrinking to ensure
        text fits within the specified rectangles.
        """
        from app.model import RedactReplace

        for i, op in enumerate(operations):
            if not isinstance(op, RedactReplace):
                continue

            # Get working values from metadata
            default_meta: TextMetadata = {
                "fontsize": TEXT_DEFAULT_FONT_SIZE,
                "color": TEXT_DEFAULT_COLOR,
                "font_flags": 0,
                "fontname": op.fontname,
            }
            meta = text_metadata.get(i, default_meta)
            final_fontsize = meta["fontsize"]
            text_color = meta["color"]
            font_flags = meta["font_flags"]
            font_alias = font_aliases.get(i, meta["fontname"])

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
                    op.fontfile, text_color, font_flags,
                    op_index=i,
                    warnings=warnings,
                    wrap_enabled=wrap_enabled,
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
            # reuse it for every probe. A custom fontfile takes precedence
            # over the Base-14 alias name.
            fit_font = (
                fitz.Font(fontname=fontname, fontfile=fontfile)
                if fontfile
                else fitz.Font(fontname=fontname)
            )
            target_width = expanded_rect.width * TEXT_AUTOFIT_WIDTH_RATIO

            # Only act when the text does not already fit on one line at its
            # intended size. Keeping the original size when it fits preserves
            # visual parity and avoids spurious warnings.
            if fit_font.text_length(text, fontsize=initial_fontsize) > target_width:
                handled = False

                # --- Wrap-first: expand height to fit multiple lines ---
                if wrap_enabled:
                    lines, longest_token = self._wrap_line_count(
                        fit_font, text, initial_fontsize, target_width
                    )
                    # Wrapping only helps when there is more than one line AND
                    # the widest word actually fits the line width.
                    if lines > 1 and longest_token <= target_width:
                        line_h = initial_fontsize * TEXT_WRAP_LINE_HEIGHT_FACTOR
                        needed_h = lines * line_h + TEXT_BOX_Y_PADDING
                        avail_h = (
                            page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN
                        ) - expanded_rect.y0
                        if needed_h <= avail_h:
                            # Grow the box downward; keep the original font size.
                            expanded_rect = fitz.Rect(
                                expanded_rect.x0, expanded_rect.y0,
                                expanded_rect.x1, expanded_rect.y0 + needed_h,
                            )
                            wrapped_lines = lines
                            handled = True

                # --- Fallback: width-based font shrink via binary search ---
                if not handled:
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

        # Try insert_textbox for better layout handling
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
        from app.model import RemoveSectionAsImage

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

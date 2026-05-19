"""
Text utility functions for safe PDF text handling.

Includes Unicode sanitization (inspired by opendataloader-pdf) and
page range parsing for batch operations.
"""
import re
from typing import List, Optional, Set, Tuple

# Matches lone surrogates (U+D800..U+DFFF) and null characters.
# These can appear in PDFs with malformed font encodings and cause
# crashes during text processing or display.
_INVALID_UNICODE_RE = re.compile(r"[\ud800-\udfff\x00]")

# Replacement character for invalid Unicode
REPLACEMENT_CHAR = "\ufffd"


def sanitize_unicode(text: str) -> str:
    """Replace lone surrogates and null characters with U+FFFD.

    PDFs with malformed font encodings can produce lone surrogates
    (U+D800-U+DFFF) and null characters that cause UnicodeEncodeError
    or display issues. This function safely replaces them.

    Args:
        text: Input string that may contain invalid Unicode.

    Returns:
        Cleaned string with invalid characters replaced by U+FFFD.
    """
    if not text:
        return text
    return _INVALID_UNICODE_RE.sub(REPLACEMENT_CHAR, text)


def parse_page_range(page_range_str: str, total_pages: int) -> Set[int]:
    """Parse a page range string into a set of 0-based page indices.

    Supports formats like:
        "1"       -> {0}
        "1,3,5"   -> {0, 2, 4}
        "1-5"     -> {0, 1, 2, 3, 4}
        "1,3,5-7" -> {0, 2, 4, 5, 6}
        "all"     -> all pages

    Page numbers are 1-based in input, converted to 0-based indices.
    Invalid or out-of-range values are silently skipped.

    Args:
        page_range_str: Page range string (e.g., "1,3,5-7").
        total_pages: Total number of pages in the document.

    Returns:
        Set of 0-based page indices.

    Raises:
        ValueError: If the input string is completely unparseable.
    """
    if not page_range_str or not page_range_str.strip():
        raise ValueError("Empty page range")

    text = page_range_str.strip().lower()

    if text == "all":
        return set(range(total_pages))

    result: Set[int] = set()
    parts = text.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            # Range: "3-7"
            range_parts = part.split("-", 1)
            try:
                start = int(range_parts[0].strip())
                end = int(range_parts[1].strip())
            except ValueError:
                continue  # Skip invalid range parts

            # Clamp to valid range (1-based input)
            start = max(1, start)
            end = min(total_pages, end)

            for page_num in range(start, end + 1):
                result.add(page_num - 1)  # Convert to 0-based
        else:
            # Single page: "3"
            try:
                page_num = int(part)
            except ValueError:
                continue  # Skip non-numeric parts

            if 1 <= page_num <= total_pages:
                result.add(page_num - 1)  # Convert to 0-based

    if not result and text != "all":
        raise ValueError(f"No valid pages in range: {page_range_str}")

    return result


def format_page_range(page_indices: Set[int]) -> str:
    """Format a set of 0-based page indices into a readable range string.

    Converts back to 1-based for display.
    Example: {0, 1, 2, 4, 6, 7, 8} -> "1-3, 5, 7-9"

    Args:
        page_indices: Set of 0-based page indices.

    Returns:
        Formatted page range string (1-based).
    """
    if not page_indices:
        return ""

    sorted_pages = sorted(page_indices)
    ranges: List[str] = []
    start = sorted_pages[0]
    end = start

    for page in sorted_pages[1:]:
        if page == end + 1:
            end = page
        else:
            if start == end:
                ranges.append(str(start + 1))
            else:
                ranges.append(f"{start + 1}-{end + 1}")
            start = page
            end = page

    # Add the last range
    if start == end:
        ranges.append(str(start + 1))
    else:
        ranges.append(f"{start + 1}-{end + 1}")

    return ", ".join(ranges)

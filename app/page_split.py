"""Pure page-grouping logic for document split.

I/O-free helpers that turn a split request into concrete 0-based page-index
groups. Keeping this separate from :mod:`app.document_session` lets the logic
be unit-tested in isolation and type-checked under mypy ``strict`` (the
session module is exempt for now — see ``typing-legacy-core``).
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional


class SplitMode(str, Enum):
    """How a document should be divided into output files."""

    SINGLE = "single"      # one file per page
    EVERY_N = "every_n"    # one file per N consecutive pages
    RANGES = "ranges"      # one file per user-specified range group


def parse_page_ranges(spec: str, page_count: int) -> List[List[int]]:
    """Parse a 1-based range spec into 0-based page-index groups.

    Example: ``"1-3, 5, 7-9"`` with ``page_count=9`` ->
    ``[[0, 1, 2], [4], [6, 7, 8]]``.

    Rules:
        - Groups are comma-separated; each group is a single page (``"5"``)
          or an inclusive range (``"7-9"``). Surrounding whitespace is ignored.
        - Input is 1-based; both range ends are inclusive.
        - Duplicates/overlaps across groups are allowed (may be intentional);
          input order is preserved.

    Args:
        spec: The user-entered range specification.
        page_count: Total pages in the document (for bounds checking).

    Returns:
        A list of groups, each a list of 0-based page indices.

    Raises:
        ValueError: empty spec, empty/blank group, non-integer token,
            value < 1, value > page_count, or a reversed range (``"5-3"``).
    """
    if page_count <= 0:
        raise ValueError("page_count must be positive")
    if not spec or not spec.strip():
        raise ValueError("range spec must not be empty")

    groups: List[List[int]] = []
    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            raise ValueError(f"empty range group in spec: {spec!r}")

        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2:
                raise ValueError(f"invalid range token: {token!r}")
            start = _parse_one_based(parts[0], page_count)
            end = _parse_one_based(parts[1], page_count)
            if start > end:
                raise ValueError(f"reversed range: {token!r}")
            groups.append([i - 1 for i in range(start, end + 1)])
        else:
            value = _parse_one_based(token, page_count)
            groups.append([value - 1])

    return groups


def _parse_one_based(text: str, page_count: int) -> int:
    """Parse a single 1-based page number and validate its bounds."""
    text = text.strip()
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"not a page number: {text!r}") from None
    if value < 1:
        raise ValueError(f"page number must be >= 1: {value}")
    if value > page_count:
        raise ValueError(f"page number {value} exceeds page count {page_count}")
    return value


def compute_split_groups(
    page_count: int,
    mode: SplitMode,
    every_n: Optional[int] = None,
    ranges_spec: Optional[str] = None,
) -> List[List[int]]:
    """Return 0-based page-index groups for the requested split mode.

    Args:
        page_count: Total pages in the document (must be > 0).
        mode: One of :class:`SplitMode`.
        every_n: Required for ``EVERY_N``; pages per output file (>= 1).
        ranges_spec: Required for ``RANGES``; see :func:`parse_page_ranges`.

    Returns:
        - ``SINGLE``  -> ``[[0], [1], ..., [page_count - 1]]``
        - ``EVERY_N`` -> consecutive chunks of ``every_n`` pages
        - ``RANGES``  -> :func:`parse_page_ranges` result

    Raises:
        ValueError: non-positive ``page_count``, missing/invalid mode argument,
            or any error propagated from :func:`parse_page_ranges`.
    """
    if page_count <= 0:
        raise ValueError("page_count must be positive")

    if mode == SplitMode.SINGLE:
        return [[i] for i in range(page_count)]

    if mode == SplitMode.EVERY_N:
        if every_n is None or every_n < 1:
            raise ValueError("every_n must be >= 1 for EVERY_N split")
        return [
            list(range(start, min(start + every_n, page_count)))
            for start in range(0, page_count, every_n)
        ]

    if mode == SplitMode.RANGES:
        if ranges_spec is None:
            raise ValueError("ranges_spec is required for RANGES split")
        return parse_page_ranges(ranges_spec, page_count)

    raise ValueError(f"unknown split mode: {mode!r}")

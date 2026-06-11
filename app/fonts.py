import os
import re
import sys
from typing import Dict, List, Optional

import fitz

from app.config import FONT_FLAG_BOLD, FONT_FLAG_ITALIC
from app.logger import get_logger

logger = get_logger()

# Subset-embedded fonts carry a "ABCDEF+" tag prefix (6 uppercase letters).
_SUBSET_PREFIX_RE = re.compile(r"^[A-Z]{6}\+")
# Style/weight tokens stripped to recover the bare family name.
_STYLE_TOKENS = {
    "bold", "italic", "oblique", "regular", "light", "medium", "semibold",
    "black", "thin", "extrabold", "heavy", "book", "roman", "mt", "ps", "psmt",
}

# Conditional import for cross-platform compatibility
if sys.platform == "win32":
    import winreg
else:
    winreg = None

# Cache for font paths to avoid repeated registry scans
_font_cache: Optional[Dict[str, str]] = None

def _populate_font_cache() -> None:
    """
    Populates the font cache by reading from the Windows Registry.
    This is much faster and more reliable than scanning font directories.
    """
    global _font_cache
    if _font_cache is not None:
        return

    _font_cache = {}
    
    if sys.platform != "win32" or winreg is None:
        logger.warning("Font registry lookup is only supported on Windows. Font cache will be empty.")
        return

    font_key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    fonts_dir = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts")

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, font_key_path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    value_name, value_data, _ = winreg.EnumValue(key, i)
                    # Key is like "Arial (TrueType)", value is "arial.ttf"
                    font_name = value_name.split(" (")[0].strip()
                    font_path = os.path.join(fonts_dir, value_data)
                    
                    # Store lowercased name for case-insensitive matching
                    _font_cache[font_name.lower()] = font_path
                    i += 1
                except OSError:
                    # Reached the end of the registry key values
                    break
        logger.info(f"Font cache populated with {len(_font_cache)} fonts from Windows Registry.")
    except OSError as e:
        logger.error(f"Failed to read fonts from Windows Registry: {e}")
        # Fallback or empty cache
        _font_cache = {}


def get_font_path_by_name(font_name: str) -> Optional[str]:
    """
    Gets a font file path by its family name using a cached dictionary
    populated from the Windows Registry.
    """
    if _font_cache is None:
        _populate_font_cache()

    # _populate_font_cache() always assigns a dict; narrow for the type checker.
    cache = _font_cache if _font_cache is not None else {}
    # Perform a case-insensitive search
    return cache.get(font_name.lower())

def _font_name_candidates(pdf_fontname: str, font_flags: int = 0) -> List[str]:
    """Build lowercase registry-lookup candidates for an extracted PDF font name.

    Ordered most-specific to most-general:
    subset prefix stripped -> raw name -> separators/camelCase spaced ->
    flag-derived style variants -> bare family. Duplicates removed,
    order preserved. Registry keys look like "arial bold" (see
    _populate_font_cache), hence the spacing normalization.
    """
    base = _SUBSET_PREFIX_RE.sub("", (pdf_fontname or "").strip())
    if not base:
        return []

    spaced = re.sub(r"[-_,]+", " ", base)
    decamel = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", spaced)
    normalized = re.sub(r"\s+", " ", decamel).strip().lower()

    tokens = normalized.split(" ")
    family_tokens = [t for t in tokens if t not in _STYLE_TOKENS]
    family = " ".join(family_tokens) if family_tokens else normalized

    candidates = [base.lower(), normalized]
    if font_flags & FONT_FLAG_BOLD and font_flags & FONT_FLAG_ITALIC:
        candidates.append(f"{family} bold italic")
    if font_flags & FONT_FLAG_BOLD:
        candidates.append(f"{family} bold")
    if font_flags & FONT_FLAG_ITALIC:
        candidates.append(f"{family} italic")
    candidates.append(family)

    seen = set()
    unique: List[str] = []
    for name in candidates:
        if name and name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _font_file_covers(fontfile: str, text: str) -> bool:
    """True when the font file has a glyph for every non-space char of text."""
    if not text:
        return True
    try:
        font = fitz.Font(fontfile=fontfile)
    except Exception as exc:
        # PyMuPDF raises its own FzError* hierarchy (not OSError/RuntimeError)
        # for unparsable font files; ANY construction failure simply means
        # "cannot vouch for coverage" -> reject the candidate.
        logger.debug(f"Font coverage probe failed for {fontfile}: {exc}")
        return False
    return all(font.has_glyph(ord(ch)) for ch in text if not ch.isspace())


def resolve_pdf_fontname(
    pdf_fontname: str, font_flags: int = 0, must_cover: str = ""
) -> Optional[str]:
    """Match an extracted PDF font name to an installed system font file.

    ``must_cover`` (the replacement text) rejects a match whose font lacks
    glyphs for it -- e.g. Arial must not be chosen for Hangul text. Returns
    the font file path, or None when nothing matches (caller falls back to
    its existing Base-14 / Korean-default behavior).
    """
    for candidate in _font_name_candidates(pdf_fontname, font_flags):
        path = get_font_path_by_name(candidate)
        if path and os.path.exists(path) and _font_file_covers(path, must_cover):
            logger.debug(f"Matched PDF font '{pdf_fontname}' -> {path}")
            return path
    return None


def get_default_korean_font_path() -> Optional[str]:
    """Returns path to a default Korean font (Malgun Gothic) if available."""
    if sys.platform == "win32":
        # Try common Korean fonts in order
        for font_name in ["Malgun Gothic", "Gulim", "Batang", "Dotum"]:
            path = get_font_path_by_name(font_name)
            if path:
                return path
    return None

if __name__ == "__main__":
    # Example usage
    from pprint import pprint
    from app.logger import setup_logger
    setup_logger()
    
    # Test getting a specific font
    arial_path = get_font_path_by_name("Arial")
    print(f"\nArial font path: {arial_path}")
    
    malgun_path = get_font_path_by_name("Malgun Gothic")
    print(f"Malgun Gothic font path: {malgun_path}")

    # The cache should be populated now, this call should be fast
    times_path = get_font_path_by_name("Times New Roman")
    print(f"Times New Roman font path: {times_path}")

    non_existent_path = get_font_path_by_name("NonExistentFont")
    print(f"NonExistentFont path: {non_existent_path}")


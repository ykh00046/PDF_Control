import os
import sys
from typing import Dict, Optional
from app.logger import get_logger

logger = get_logger()

# Conditional import for cross-platform compatibility
if sys.platform == "win32":
    import winreg
else:
    winreg = None

# Cache for font paths to avoid repeated registry scans
_font_cache: Optional[Dict[str, str]] = None

def _populate_font_cache():
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
    except Exception as e:
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
    
    # Perform a case-insensitive search
    return _font_cache.get(font_name.lower())

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


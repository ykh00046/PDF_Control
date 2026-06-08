"""
Path Helper Utility

Provides path resolution for resources in both development and frozen environments.
"""

import os
import sys
import tempfile
from pathlib import Path


def is_frozen() -> bool:
    """Check if running in PyInstaller frozen environment."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_base_path() -> Path:
    """
    Get base path for the application.
    
    Returns:
        Path to application base directory (frozen or development)
    """
    if is_frozen():
        # PyInstaller frozen environment
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # Development environment
        return Path(__file__).parent.parent


def get_resource_path(relative_path: str) -> Path:
    """
    Get absolute path to a resource file.
    
    Works in both development and PyInstaller frozen environments.
    
    Args:
        relative_path: Relative path from project root (e.g., 'app/i18n/en.json')
        
    Returns:
        Absolute path to the resource
        
    Example:
        >>> get_resource_path('app/i18n/en.json')
        Path('/path/to/app/i18n/en.json')
    """
    base = get_base_path()
    return base / relative_path


def get_i18n_path(filename: str) -> Path:
    """
    Get path to i18n translation file.
    
    Args:
        filename: Translation filename (e.g., 'en.json')
        
    Returns:
        Absolute path to translation file
    """
    return get_resource_path(f'app/i18n/{filename}')


def _platform_app_data_dir() -> Path:
    """Return the conventional per-user app-data directory for the current OS."""
    import platform

    system = platform.system()

    if system == 'Windows':
        app_data = Path.home() / 'AppData' / 'Roaming' / 'PDF_Control'
    elif system == 'Darwin':  # macOS
        app_data = Path.home() / 'Library' / 'Application Support' / 'PDF_Control'
    else:  # Linux and others
        app_data = Path.home() / '.config' / 'PDF_Control'

    return app_data


def get_app_data_dir() -> Path:
    """
    Get application data directory for user data (config, logs, etc.).

    Resolution order:
    1. ``PDF_CONTROL_APP_DATA_DIR`` environment override
    2. Development mode: project-local ``.appdata`` directory
    3. Frozen mode: platform-specific per-user app-data directory
    4. Temporary fallback if none of the above are writable

    Returns:
        Path to application data directory
    """
    candidates = []

    override = os.environ.get("PDF_CONTROL_APP_DATA_DIR")
    if override:
        candidates.append(Path(override))

    if is_frozen():
        candidates.append(_platform_app_data_dir())
    else:
        candidates.append(get_base_path() / ".appdata")
        candidates.append(_platform_app_data_dir())

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue

    fallback = Path(tempfile.gettempdir()) / "PDF_Control" / "appdata"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_config_path() -> Path:
    """Get path to config file."""
    return get_app_data_dir() / 'config.json'


def get_logs_dir() -> Path:
    """Get directory for rotating application logs."""
    logs_dir = get_app_data_dir() / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_log_path() -> Path:
    """Get path to log file."""
    return get_logs_dir() / 'app.log'


def get_temp_dir() -> Path:
    """
    Get temporary directory for the application.
    
    Returns:
        Path to temp directory
    """
    temp = Path(tempfile.gettempdir()) / 'PDF_Control'
    temp.mkdir(parents=True, exist_ok=True)
    return temp


# Legacy compatibility
def get_app_dir() -> str:
    """Legacy: Get base directory as string."""
    return str(get_base_path())


def get_data_path(relative_path: str) -> str:
    """Legacy: Get resource path as string."""
    return str(get_resource_path(relative_path))

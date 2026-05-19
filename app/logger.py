# app/logger.py
# Logging configuration and utilities

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from app.path_helper import get_logs_dir

# Global logger instance
_logger = None
_log_file_path: Path | None = None

def setup_logger(log_dir: str | Path | None = None, log_level: int = logging.DEBUG) -> logging.Logger:
    """
    Configure and return the application logger with rotating file handler.

    Args:
        log_dir: Directory to store log files (default: "logs")
        log_level: Logging level (default: INFO)

    Returns:
        Configured logger instance

    Log file format: logs/app_YYYYMMDD.log
    Rotation: Daily, keeps last 7 days
    """
    global _logger, _log_file_path

    if _logger is not None:
        return _logger

    # Create logs directory if it doesn't exist
    log_path = Path(log_dir) if log_dir is not None else get_logs_dir()
    log_path.mkdir(parents=True, exist_ok=True)

    # Create logger
    _logger = logging.getLogger("PDFRedactionTool")
    _logger.setLevel(log_level)

    # Prevent duplicate handlers if setup_logger is called multiple times
    if _logger.handlers:
        return _logger

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with daily rotation (keeps last 7 days)
    date_token = datetime.now().strftime('%Y%m%d')
    log_filename = log_path / f"app_{date_token}.log"
    try:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_filename,
            when='midnight',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
    except OSError:
        # Multi-process frozen runs on Windows can contend on a shared log file.
        log_filename = log_path / f"app_{date_token}_{os.getpid()}.log"
        file_handler = logging.FileHandler(
            filename=log_filename,
            encoding='utf-8'
        )
    file_handler.setLevel(logging.DEBUG)  # File logs everything
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)
    _log_file_path = log_filename

    # Console handler (for development/debugging)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Console only shows warnings and errors
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    _logger.info("=" * 80)
    _logger.info("PDF Redaction Tool - Logging initialized")
    _logger.info(f"Log file: {log_filename}")
    _logger.info(f"Log level: {logging.getLevelName(log_level)}")
    _logger.info("=" * 80)

    return _logger


def get_logger() -> logging.Logger:
    """
    Get the application logger instance.
    If not initialized, sets up with default configuration.

    Returns:
        Logger instance
    """
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def log_operation(operation_type: str, page_index: int, rect_count: int, **kwargs):
    """
    Log a PDF operation (delete/replace) with metadata only.

    PRIVACY: Does not log actual text content.

    Args:
        operation_type: Type of operation (e.g., "RedactDelete", "RedactReplace")
        page_index: Page number where operation occurred
        rect_count: Number of rectangles affected
        **kwargs: Additional metadata (font, size, etc.) - NO TEXT CONTENT
    """
    logger = get_logger()
    metadata = ", ".join(f"{k}={v}" for k, v in kwargs.items() if k != "text")
    logger.info(
        f"Operation: {operation_type} | Page: {page_index} | Rects: {rect_count} | {metadata}"
    )


def log_file_operation(operation: str, file_path: str, success: bool, error_msg: str = ""):
    """
    Log file I/O operations (open, save, close).

    Args:
        operation: Operation type (e.g., "open", "save", "close")
        file_path: Path to the file (filename only for privacy)
        success: Whether operation succeeded
        error_msg: Error message if failed
    """
    logger = get_logger()
    filename = Path(file_path).name  # Only log filename, not full path

    if success:
        logger.info(f"File {operation}: {filename} - SUCCESS")
    else:
        logger.error(f"File {operation}: {filename} - FAILED | Error: {error_msg}")


def log_render_performance(page_index: int, render_time_ms: float, zoom_level: float):
    """
    Log page rendering performance.

    Warns if render time exceeds 2 seconds (per PLAN.md Section 13).

    Args:
        page_index: Page number rendered
        render_time_ms: Render time in milliseconds
        zoom_level: Current zoom level
    """
    logger = get_logger()

    if render_time_ms > 2000:
        logger.warning(
            f"SLOW RENDER: Page {page_index} | {render_time_ms:.0f}ms | Zoom: {zoom_level:.2f}x"
        )
    else:
        logger.debug(
            f"Render: Page {page_index} | {render_time_ms:.0f}ms | Zoom: {zoom_level:.2f}x"
        )


def log_coordinate_transform(from_coords, to_coords, transform_type: str):
    """
    Log coordinate transformations for debugging.

    Args:
        from_coords: Source coordinates (QRectF, QPointF, etc.)
        to_coords: Destination coordinates (fitz.Rect, etc.)
        transform_type: Type of transform (e.g., "scene_to_pdf", "pdf_to_scene")
    """
    logger = get_logger()
    logger.debug(f"Coordinate transform [{transform_type}]: {from_coords} -> {to_coords}")


def log_memory_warning(current_mb: float, threshold_mb: float):
    """
    Log memory usage warnings.

    Args:
        current_mb: Current memory usage in MB
        threshold_mb: Threshold that was exceeded
    """
    logger = get_logger()
    logger.warning(f"MEMORY WARNING: {current_mb:.1f}MB / {threshold_mb:.1f}MB threshold")


def get_log_file_path() -> Path:
    """
    Get the current log file path.

    Returns:
        Path to current log file
    """
    global _log_file_path
    if _log_file_path is not None:
        return _log_file_path

    log_dir = get_logs_dir()
    log_filename = f"app_{datetime.now().strftime('%Y%m%d')}.log"
    return log_dir / log_filename

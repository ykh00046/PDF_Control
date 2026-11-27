"""
Process-based PDF preview renderer.

This module is invoked as a lightweight worker process so PyMuPDF rendering
does not run inside the GUI process.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from app.logger import get_logger
from app.model import Operation
from app.pdf_engine import render_page_preview


def _deserialize_operations(operations_data):
    """Rebuild Operation objects, counting entries that fail to load.

    Returns ``(operations, skipped_count)``. A non-deserializable entry is
    skipped (the preview renders without it) but must not vanish silently:
    the caller reports the count through the job result.
    """
    operations = []
    skipped = 0
    for op_data in operations_data:
        try:
            operations.append(Operation.from_dict(op_data))
        except Exception as exc:
            skipped += 1
            get_logger().warning(f"Render worker failed to deserialize op: {exc}")
    return operations, skipped


def _read_password_from_stdin() -> str | None:
    """Read the source password sent by the viewer over the stdin pipe.

    One-line protocol: the viewer writes the password followed by "\\n" and
    closes the pipe (passwords containing a newline are not supported). The
    password is intentionally never written to the job file so it cannot
    linger on disk after a crash.
    """
    stdin = sys.stdin
    # Both ends pin UTF-8 so non-ASCII passwords survive locale differences.
    reconfigure = getattr(stdin, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    return stdin.readline().rstrip("\n") or None


def run_render_job(job_path: str | Path) -> int:
    job_path = Path(job_path)
    with open(job_path, "r", encoding="utf-8") as handle:
        job = json.load(handle)

    # Only touch stdin when the viewer announced a password; the plain
    # (unencrypted) path must stay byte-for-byte identical to before.
    password = _read_password_from_stdin() if job.get("password_stdin") else None

    response_path = Path(job["response_path"])
    output_path = Path(job["output_path"])
    response_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "success": False,
        "page_index": job["page_index"],
        "zoom_level": job["zoom_level"],
        "duration_ms": 0.0,
        "warnings": [],
    }

    start_time = time.perf_counter()
    try:
        operations, skipped_operations = _deserialize_operations(job.get("operations_data", []))
        apply_result = render_page_preview(
            job["file_path"],
            job["page_index"],
            operations,
            job["zoom_level"],
            output_path,
            logger=get_logger(),
            password=password,
        )

        result["success"] = True
        result["duration_ms"] = (time.perf_counter() - start_time) * 1000
        result["warnings"] = [
            {
                "op_index": w.op_index,
                "severity": w.severity,
                "code": w.code,
                "detail": w.detail,
            }
            for w in (apply_result.warnings if apply_result else [])
        ]
        if skipped_operations:
            # The render still succeeds without the skipped ops, but the
            # caller must be able to see that the preview is incomplete.
            result["warnings"].append(f"{skipped_operations} operation(s) skipped (failed to deserialize)")
    except (OSError, IOError) as exc:
        result["error"] = str(exc)
    except Exception as exc:
        # Last-resort net: an unexpected error must produce a readable
        # response file, never kill the worker with a raw traceback.
        result["error"] = f"{type(exc).__name__}: {exc}"

    with open(response_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)

    return 0 if result["success"] else 1


def main(argv=None) -> int:
    argv = list(argv or [])
    if len(argv) != 1:
        raise SystemExit("Usage: render_worker <job.json>")

    return run_render_job(argv[0])

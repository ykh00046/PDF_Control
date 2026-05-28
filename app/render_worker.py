"""
Process-based PDF preview renderer.

This module is invoked as a lightweight worker process so PyMuPDF rendering
does not run inside the GUI process.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.logger import get_logger
from app.model import Operation
from app.pdf_engine import render_page_preview


def _deserialize_operations(operations_data):
    operations = []
    for op_data in operations_data:
        try:
            operations.append(Operation.from_dict(op_data))
        except Exception as exc:
            get_logger().warning(f"Render worker failed to deserialize op: {exc}")
    return operations


def run_render_job(job_path: str | Path) -> int:
    job_path = Path(job_path)
    with open(job_path, "r", encoding="utf-8") as handle:
        job = json.load(handle)

    response_path = Path(job["response_path"])
    output_path = Path(job["output_path"])
    response_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "success": False,
        "page_index": job["page_index"],
        "zoom_level": job["zoom_level"],
        "duration_ms": 0.0,
    }

    start_time = time.perf_counter()
    try:
        operations = _deserialize_operations(job.get("operations_data", []))
        apply_result = render_page_preview(
            job["file_path"],
            job["page_index"],
            operations,
            job["zoom_level"],
            output_path,
            logger=get_logger(),
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
    except (OSError, IOError) as exc:
        result["error"] = str(exc)

    with open(response_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)

    return 0 if result["success"] else 1


def main(argv=None) -> int:
    argv = list(argv or [])
    if len(argv) != 1:
        raise SystemExit("Usage: render_worker <job.json>")

    return run_render_job(argv[0])

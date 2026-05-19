from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


def build_assets(work_dir: Path) -> dict[str, str]:
    work_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = work_dir / "sample.pdf"
    image_path = work_dir / "preview.png"
    response_path = work_dir / "response.json"
    job_path = work_dir / "job.json"

    for path in (pdf_path, image_path, response_path, job_path):
        if path.exists():
            path.unlink()

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Frozen worker smoke test", fontsize=14)
    doc.save(pdf_path)
    doc.close()

    job = {
        "file_path": str(pdf_path),
        "page_index": 0,
        "zoom_level": 1.0,
        "operations_data": [],
        "output_path": str(image_path),
        "response_path": str(response_path),
    }
    job_path.write_text(json.dumps(job), encoding="utf-8")

    return {
        "work_dir": str(work_dir),
        "job_path": str(job_path),
        "response_path": str(response_path),
        "image_path": str(image_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    result = build_assets(Path(args.work_dir))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

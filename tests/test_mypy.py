"""Static type-checking enforcement for the operations pipeline.

Runs mypy --strict on the ``app.operations`` package via the config in
mypy.ini. A type-contract mismatch there silently broke 3 smoke tests on
2026-04-14; this test blocks the same class of regression at CI time.

Scope was widened from a single file to the whole package on 2026-05-27
as part of the operations-restructure PDCA cycle, again on 2026-06-02
(r2-quality-fixes) to the clean leaf modules in STRICT_LEAF_MODULES, and on
2026-06-10 (r6-quality) to the former legacy core (pdf_engine,
document_session, document_model, model).
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# Leaf modules promoted to the strict gate in the r2-quality-fixes cycle.
# Their per-module strict settings live in mypy.ini.
STRICT_LEAF_MODULES = [
    "app/config.py",
    "app/logger.py",
    "app/path_helper.py",
    "app/text_utils.py",
    "app/text_metadata.py",
    "app/fonts.py",
    "app/page_split.py",
    "app/encryption.py",
    # Legacy-core promotion (r6-quality, 2026-06-10)
    "app/pdf_engine.py",
    "app/document_session.py",
    "app/document_model.py",
    "app/model.py",
]


@pytest.mark.timeout(60)
def test_operations_package_passes_mypy_strict():
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "-p", "app.operations"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mypy --strict failed on app.operations:\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


@pytest.mark.timeout(60)
def test_strict_leaf_modules_pass_mypy():
    result = subprocess.run(
        [sys.executable, "-m", "mypy", *STRICT_LEAF_MODULES],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mypy --strict failed on strict leaf modules:\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

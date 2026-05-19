"""Static type-checking enforcement for the operations pipeline.

Runs mypy on app/operations_service.py via the config in mypy.ini.
A type-contract mismatch there silently broke 3 smoke tests on 2026-04-14;
this test blocks the same class of regression at CI time.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.mark.timeout(60)
def test_operations_service_passes_mypy_strict():
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "app/operations_service.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mypy --strict failed on app/operations_service.py:\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

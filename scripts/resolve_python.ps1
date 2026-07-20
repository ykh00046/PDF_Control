# Shared Python resolver for build/smoke scripts.
#
# On this machine a bare `python` can resolve to an unrelated tool venv
# (e.g. a 3.11 agent venv), which silently builds against the wrong
# interpreter/site-packages. Resolve the project interpreter explicitly:
#   1. PDF_CONTROL_PYTHON environment override
#   2. `py -3.13` (the pinned project version, see requirements.txt)
#   3. bare `python` as a last resort
function Resolve-ProjectPython {
    if ($env:PDF_CONTROL_PYTHON) {
        if (Test-Path $env:PDF_CONTROL_PYTHON) {
            return $env:PDF_CONTROL_PYTHON
        }
        throw "PDF_CONTROL_PYTHON is set but does not exist: $env:PDF_CONTROL_PYTHON"
    }

    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $resolved = & $launcher.Source -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            return ([string]$resolved).Trim()
        }
    }

    $fallback = Get-Command python -ErrorAction SilentlyContinue
    if ($fallback) {
        Write-Warning "Falling back to bare 'python' ($($fallback.Source)); set PDF_CONTROL_PYTHON if this is not the project interpreter."
        return $fallback.Source
    }

    throw "No Python interpreter found. Install Python 3.13 or set PDF_CONTROL_PYTHON."
}

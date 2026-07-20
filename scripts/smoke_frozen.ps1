param(
    [string]$ExePath = "",
    [string]$WorkDir = "",
    [int]$GuiWaitSeconds = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $ExePath) {
    $ExePath = Join-Path $projectRoot "dist\PDF_Control\PDF_Control.exe"
}
if (-not $WorkDir) {
    $WorkDir = Join-Path $projectRoot "logs\release_smoke"
}

$appDataDir = Join-Path $WorkDir "appdata"
New-Item -ItemType Directory -Path $appDataDir -Force | Out-Null

if (-not (Test-Path $ExePath)) {
    throw "Frozen executable not found: $ExePath"
}

. (Join-Path $PSScriptRoot "resolve_python.ps1")
$pythonPath = Resolve-ProjectPython

$assetJson = & $pythonPath (Join-Path $projectRoot "scripts\create_frozen_smoke_assets.py") --work-dir $WorkDir
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create smoke assets."
}

$assets = $assetJson | ConvertFrom-Json

$previousAppDataOverride = $env:PDF_CONTROL_APP_DATA_DIR
$env:PDF_CONTROL_APP_DATA_DIR = $appDataDir

try {
    $worker = Start-Process -FilePath $ExePath `
        -ArgumentList "--render-worker", $assets.job_path `
        -WorkingDirectory $projectRoot `
        -PassThru `
        -Wait

    if ($worker.ExitCode -ne 0) {
        throw "Render worker exited with code $($worker.ExitCode)"
    }

    if (-not (Test-Path $assets.response_path)) {
        throw "Render worker did not create response file: $($assets.response_path)"
    }
    if (-not (Test-Path $assets.image_path)) {
        throw "Render worker did not create preview image: $($assets.image_path)"
    }

    $response = Get-Content $assets.response_path | ConvertFrom-Json
    if (-not $response.success) {
        throw "Render worker reported failure."
    }

    $gui = Start-Process -FilePath $ExePath `
        -WorkingDirectory $projectRoot `
        -PassThru

    Start-Sleep -Seconds $GuiWaitSeconds

    if ($gui.HasExited) {
        throw "GUI smoke test failed: process exited early with code $($gui.ExitCode)"
    }

    Stop-Process -Id $gui.Id -Force
    $gui.WaitForExit()

    [PSCustomObject]@{
        exe_path = $ExePath
        work_dir = $WorkDir
        worker_exit_code = $worker.ExitCode
        worker_duration_ms = $response.duration_ms
        gui_survived_seconds = $GuiWaitSeconds
    } | ConvertTo-Json
}
finally {
    if ($null -eq $previousAppDataOverride) {
        Remove-Item Env:PDF_CONTROL_APP_DATA_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:PDF_CONTROL_APP_DATA_DIR = $previousAppDataOverride
    }
}

param(
    [switch]$Zip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python was not found on PATH."
}

Write-Host "Building PDF Control (onedir)..."
$env:PYTHONNOUSERSITE = "1"
& $python.Source -I -m PyInstaller --clean --noconfirm pdf_control.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$distDir = Join-Path $projectRoot "dist\PDF_Control"
if (-not (Test-Path $distDir)) {
    throw "Build succeeded but dist\\PDF_Control was not created."
}

Write-Host "Build output: $distDir"

if ($Zip) {
    $zipPath = Join-Path $projectRoot "dist\PDF_Control_windows.zip"
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    Compress-Archive -Path $distDir -DestinationPath $zipPath
    Write-Host "Archive created: $zipPath"
}

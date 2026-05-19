param(
    [switch]$SkipBuild,
    [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $SkipBuild) {
    & (Join-Path $projectRoot "scripts\build_windows.ps1")
}

if (-not $SkipSmoke) {
    & (Join-Path $projectRoot "scripts\smoke_frozen.ps1")
}

$distDir = Join-Path $projectRoot "dist\PDF_Control"
if (-not (Test-Path $distDir)) {
    throw "Build output not found: $distDir"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $projectRoot ("dist\PDF_Control_windows_{0}.zip" -f $stamp)
Compress-Archive -Path $distDir -DestinationPath $zipPath -Force

$hash = Get-FileHash $zipPath -Algorithm SHA256
$manifest = [PSCustomObject]@{
    built_at = (Get-Date).ToString("s")
    archive_path = $zipPath
    archive_sha256 = $hash.Hash
    archive_size_bytes = (Get-Item $zipPath).Length
}

$manifestPath = Join-Path $projectRoot "dist\release_manifest.json"
$manifest | ConvertTo-Json | Set-Content -Path $manifestPath -Encoding UTF8

[PSCustomObject]@{
    zip_path = $zipPath
    manifest_path = $manifestPath
    sha256 = $hash.Hash
} | ConvertTo-Json

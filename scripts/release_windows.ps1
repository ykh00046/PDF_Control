param(
    [switch]$SkipBuild,
    [switch]$SkipSmoke,
    # Thumbprint of a code-signing certificate in Cert:\CurrentUser\My.
    # Optional: unset means an unsigned build (SmartScreen will warn).
    # A self-signed cert only helps machines that trust it (e.g. IT-deployed);
    # real SmartScreen relief needs a purchased OV/EV certificate.
    [string]$SignThumbprint = $env:PDF_CONTROL_SIGN_THUMBPRINT
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

$signed = $false
if ($SignThumbprint) {
    $exePath = Join-Path $distDir "PDF_Control.exe"
    $certPath = "Cert:\CurrentUser\My\$SignThumbprint"
    if (-not (Test-Path $certPath)) {
        throw "Code-signing certificate not found: $certPath"
    }
    $cert = Get-Item $certPath
    $sig = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert `
        -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com"
    if ($sig.Status -eq "Valid") {
        $signed = $true
    }
    elseif ($sig.SignerCertificate) {
        # Signature applied but the chain doesn't end in a trusted root
        # (typical for a self-signed cert). Usable where the cert is trusted.
        Write-Warning "Signature applied but not chain-trusted on this machine: $($sig.Status) - $($sig.StatusMessage)"
        $signed = $true
    }
    else {
        throw "Signing failed: $($sig.Status) - $($sig.StatusMessage)"
    }
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
    signed = $signed
}

$manifestPath = Join-Path $projectRoot "dist\release_manifest.json"
$manifest | ConvertTo-Json | Set-Content -Path $manifestPath -Encoding UTF8

[PSCustomObject]@{
    zip_path = $zipPath
    manifest_path = $manifestPath
    sha256 = $hash.Hash
} | ConvertTo-Json

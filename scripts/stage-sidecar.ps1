#!/usr/bin/env pwsh
# scripts/stage-sidecar.ps1
# PyInstaller (onefile) で backend.exe をビルドし、Tauri sidecar として配置する
#
# 使い方:
#   pwsh scripts/stage-sidecar.ps1
#   (もしくは Windows なら) powershell -ExecutionPolicy Bypass -File scripts/stage-sidecar.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$binDir  = Join-Path $root "src-tauri\binaries"

# 1) venv の Python を解決
$pythonExe = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "venv が無いので作成します..." -ForegroundColor Yellow
    & python -m venv (Join-Path $backend "venv")
    & $pythonExe -m pip install -q --upgrade pip
    & $pythonExe -m pip install -q -r (Join-Path $backend "requirements.txt")
    & $pythonExe -m pip install -q pyinstaller
}

# 2) PyInstaller (onefile)
Write-Host "PyInstaller で backend.exe をビルド中 (1〜3 分)..." -ForegroundColor Cyan
Push-Location $backend
try {
    & $pythonExe -m PyInstaller `
        --clean --noconfirm `
        --distpath dist-onefile `
        --workpath build-onefile `
        backend-onefile.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
}
finally {
    Pop-Location
}

# 3) target triple を確定して sidecar 名にリネームコピー
$targetTriple = (& "$env:USERPROFILE\.cargo\bin\rustc.exe" -Vv | Select-String "^host:" | ForEach-Object { $_.ToString().Split(" ")[1] })
if (-not $targetTriple) {
    Write-Host "rustc が見つかりません。Rust を入れてから再実行してください。" -ForegroundColor Red
    exit 1
}

$sidecarName = "backend-$targetTriple"
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $sidecarName += ".exe"
}

New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$src = Join-Path $backend "dist-onefile\backend.exe"
$dst = Join-Path $binDir $sidecarName

if (-not (Test-Path $src)) { throw "ビルド成果物が見つかりません: $src" }
Copy-Item -Force $src $dst

Write-Host ""
Write-Host "✓ sidecar 配置完了" -ForegroundColor Green
Write-Host "  $dst"
Write-Host "  size: $((Get-Item $dst).Length / 1MB) MB"
Write-Host ""
Write-Host "次は: npm --prefix frontend exec tauri build" -ForegroundColor Cyan

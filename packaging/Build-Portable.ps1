# Builds the standalone portable app and zips it for handover.
# Requires the dev environment set up (.venv with deps + pyinstaller).
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File packaging\Build-Portable.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Output "Building standalone app with PyInstaller (this takes a few minutes)..."
& ".\.venv\Scripts\pyinstaller.exe" "packaging\BiometricAttendance.spec" `
    --noconfirm --distpath dist --workpath build

$src = Join-Path $root "dist\BiometricAttendance"
if (-not (Test-Path $src)) { throw "Build folder not found: $src" }

$zip = Join-Path $root "dist\BiometricAttendance-portable.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Write-Output "Zipping portable folder..."
Compress-Archive -Path $src -DestinationPath $zip

Write-Output ""
Write-Output "Done."
Write-Output "  Portable folder: $src"
Write-Output "  Zip to hand over: $zip"
Write-Output "The college unzips it and double-clicks BiometricAttendance.exe."

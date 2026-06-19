# One-time setup for a fresh machine that already has Python 3.14 installed.
# Creates the virtual environment and installs all dependencies, then offers to
# create the Desktop shortcut. Run once:
#   powershell -ExecutionPolicy Bypass -File launcher\Setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Output "Creating virtual environment (.venv)..."
python -m venv .venv

Write-Output "Installing dependencies (this downloads ~hundreds of MB the first time)..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Output "Creating Desktop shortcut..."
& "$PSScriptRoot\Create-Desktop-Shortcut.ps1"

Write-Output ""
Write-Output "Setup complete. Double-click 'Biometric Attendance' on the Desktop to start."
Write-Output "(The first launch downloads the face model, ~300 MB, once.)"

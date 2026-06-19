# Creates a Desktop shortcut "Biometric Attendance" that launches the app with no
# console window. Run once: right-click this file -> "Run with PowerShell", or:
#   powershell -ExecutionPolicy Bypass -File launcher\Create-Desktop-Shortcut.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "Start-Attendance.vbs"
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    Write-Warning "Bundled Python not found at $pythonw. Run the one-time setup first."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "Biometric Attendance.lnk"

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
# Launch the VBS via wscript so no console window ever appears.
$sc.TargetPath = "$env:WINDIR\System32\wscript.exe"
$sc.Arguments = "`"$launcher`""
$sc.WorkingDirectory = $root
$sc.IconLocation = "$pythonw, 0"
$sc.Description = "Biometric Attendance"
$sc.Save()

Write-Output "Desktop shortcut created: $lnkPath"

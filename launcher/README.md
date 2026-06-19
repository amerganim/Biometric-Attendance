# Running the app without commands

For the dedicated attendance laptop, end users should never need a terminal.

## First-time setup (once per machine)

Requires **Python 3.14** installed (from python.org). Then either:

- Right-click `launcher\Setup.ps1` → **Run with PowerShell**, or
- Run: `powershell -ExecutionPolicy Bypass -File launcher\Setup.ps1`

This creates the environment, installs everything, and puts a **Biometric
Attendance** icon on the Desktop.

## Daily use

**Double-click the "Biometric Attendance" Desktop icon.** The app opens in a window
with no console; press **F11** for fullscreen kiosk mode, **Escape** to exit.

If you ever need to recreate just the icon, run
`launcher\Create-Desktop-Shortcut.ps1`.

## Auto-start on boot (optional, for an always-on kiosk)

Press `Win + R`, type `shell:startup`, Enter, and copy the Desktop shortcut into
that folder. The app will then launch automatically when the laptop starts.

## Distributing to a machine *without* Python

The steps above need Python installed. To ship a single self-contained installer
that needs nothing pre-installed, we package the app with PyInstaller (+ an Inno
Setup installer) — planned as the next distribution step.

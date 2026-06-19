# Packaging — standalone portable app

Produces a Windows build that runs **without Python installed**, so the college can
just unzip and double-click.

## Build it (on a dev machine with the project set up)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\Build-Portable.ps1
```

This runs PyInstaller using [`BiometricAttendance.spec`](BiometricAttendance.spec) and
produces:

- `dist\BiometricAttendance\` — the portable folder
- `dist\BiometricAttendance-portable.zip` — the same folder zipped for handover

## Hand it to the college

1. Give them `BiometricAttendance-portable.zip`.
2. They **unzip it** anywhere (e.g. `C:\BiometricAttendance` or a USB drive).
3. They **double-click `BiometricAttendance.exe`** — no install, no admin rights.

The app keeps its data (database, logs, check-in thumbnails) in a `data\` folder
**next to the .exe**, so the whole thing is self-contained and portable.

## First launch needs internet (once)

On the very first run, the face-recognition model (~300 MB) downloads automatically
and is cached. After that it works offline. So run it once with internet before or
during handover.

## Before you hand it over

- Enroll teachers and set the **work start time** in Settings.
- Set a **developer password** (Settings → Cloud Sync) to lock the Supabase keys so
  staff can't change them.
- Change the default admin password (`admin` / `admin123`).
- Optionally place a shortcut to `BiometricAttendance.exe` in the Startup folder
  (`shell:startup`) for auto-launch, and press **F11** for fullscreen kiosk mode.

## Notes

- Build size is ~1–1.5 GB (bundles Python, OpenCV, ONNX Runtime, insightface).
- `dist/` and `build/` are gitignored; only the spec and scripts are committed.

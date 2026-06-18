# Biometric-Attendance

Face-recognition attendance system for a college (~45 teachers). It runs on one
**dedicated laptop** used as a fixed kiosk: a teacher walks up, the camera recognizes
them, a liveness check confirms a real person (not a photo), and attendance is saved
to a local database.

**Phase 1 (this app):** a self-contained, fully **offline** Windows desktop app —
admin panel, teacher registration + face enrollment, live recognition + anti-spoofing,
and local attendance storage.
**Phase 2 (later):** cloud sync (Supabase) and a web admin/reporting dashboard.

## Tech stack

- **Python 3.14**, **CustomTkinter** GUI
- **insightface** (ArcFace recognition via ONNX) + **onnxruntime**
- **mediapipe** for the active liveness challenge (blink / head-turn)
- Optional **Silent-Face ONNX** model for passive anti-spoofing
- **SQLite** local database, **bcrypt** admin passwords, **openpyxl** Excel export

> DeepFace/TensorFlow are intentionally not used: TensorFlow has no Python 3.14
> wheels. The ONNX stack above provides the same capabilities and is lighter/faster.

## Setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The first launch downloads the face model pack (~300 MB, cached afterwards under your
user profile's `.insightface` folder).

## Run

```powershell
.\.venv\Scripts\python.exe main.py
```

The app opens on the **kiosk** screen. Press **F11** for fullscreen (kiosk mode),
**Escape** to leave.

### Default admin login

- Username: `admin`
- Password: `admin123`

Change it immediately in **Admin → Settings → Change Admin Password**.

## How it's used

1. **Admin → Teachers → + Add Teacher** — register each teacher's details (get their
   consent to store facial data).
2. **Enroll** next to a teacher — capture a few face samples in good lighting.
3. **Kiosk** — teachers check in/out; the first scan of the day is a check-IN, the
   next is a check-OUT. Late check-ins are flagged using the configured work-start
   time + grace period.
4. **Admin → Reports** — filter by date/teacher and export to CSV or Excel.

## Anti-spoofing

Two independent layers:

- **Active challenge (on by default):** the kiosk randomly asks the teacher to blink
  or turn their head, verified with mediapipe landmarks — defeats a held-up photo or
  a pre-recorded video of someone else.
- **Passive anti-spoof (optional):** drop a Silent-Face-style ONNX model at
  `data/models/antispoof.onnx` to additionally reject printed photos / phone screens
  with no user action. Without the file, the app runs and relies on the active
  challenge; the `liveness_threshold` setting controls strictness once a model is
  present.

Every check-in also saves an audit thumbnail under `data/thumbnails/`.

## Project layout

```
main.py            entry point
config.py          paths, defaults, thresholds
app/db/            SQLite schema + repositories (CRUD)
app/core/          camera, face engine, liveness, attendance service
app/security/      admin password hashing / auth
app/ui/            CustomTkinter views (kiosk, login, admin, teachers, enroll, reports, settings)
app/utils/         image + export helpers
data/              local DB, thumbnails, models, logs (gitignored)
```

## Not included yet (Phase 2)

Supabase cloud sync, React web dashboard, PyInstaller `.exe` packaging, Windows
auto-start + kiosk lockdown.

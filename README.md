# Biometric Attendance

Face-recognition attendance for an organization (designed for ~dozens of people). A
person walks up to a fixed laptop "kiosk", the camera recognizes them, a liveness
check confirms it's a real person (not a photo or video), and attendance is saved —
working fully **offline**, with **optional** cloud sync and a web dashboard.

It's built to be **self-hosted by anyone**: nothing is hardcoded. Run it locally as-is,
or connect **your own** free Supabase + Vercel to view attendance from anywhere — all
configured through the app (no code changes), and protected by a developer password.

## What you get

- **Desktop kiosk app (Windows)** — admin panel, teacher registration + face
  enrollment, live recognition with **anti-spoofing**, local attendance with late
  rules, and CSV/Excel reports. Runs offline; no internet required.
- **Optional cloud sync** — push attendance to your own Supabase project, instantly
  after each check-in.
- **Optional web dashboard (React)** — view/filter/export attendance and the teacher
  list from any browser; deploy free to Vercel.

## Three ways to run it

### A) Just the kiosk, offline (simplest)

1. Download `BiometricAttendance-portable.zip` from the
   [Releases](../../releases) page, unzip it, and double-click `BiometricAttendance.exe`.
   *(No Python, no install. First launch downloads the ~300 MB face model once.)*
2. Log in to **Admin** with `admin` / `admin123` (change it in Settings).
3. **Teachers → + Add Teacher → Enroll** each face, then use the **Kiosk** screen.

That's a complete, working attendance system with no cloud needed.

### B) Run from source (for developers)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Press **F11** for fullscreen kiosk mode, **Escape** to exit. To make a no-console
desktop shortcut, see [`launcher/`](launcher/). To build the portable `.exe`, see
[`packaging/`](packaging/) (or just push a `v*` tag — GitHub Actions builds and
publishes it; see [`.github/workflows/build-release.yml`](.github/workflows/build-release.yml)).

### C) Add your own cloud + dashboard (view attendance from anywhere)

Bring your **own** free accounts — each deployment is fully independent:

1. **Supabase** (cloud database): follow [`supabase/README.md`](supabase/README.md) to
   create a project, run [`supabase/schema.sql`](supabase/schema.sql), and get your keys.
2. **Desktop app** → Admin → **Settings → Cloud Sync**: paste your **Project URL** +
   **service_role key**, enable sync, then **set a developer password** to lock those
   fields so day-to-day admins can't change them (see "Developer password" below).
3. **Dashboard**: deploy [`dashboard/`](dashboard/) to Vercel with your **URL + anon
   key**. One click:

   [![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/amerganim/Biometric-Attendance&root-directory=dashboard&env=VITE_SUPABASE_URL,VITE_SUPABASE_ANON_KEY)

   (set **Root Directory** = `dashboard`, and add `VITE_SUPABASE_URL` +
   `VITE_SUPABASE_ANON_KEY`). Full steps in [`dashboard/README.md`](dashboard/README.md).

Sync is **one-way** (kiosk → cloud) and the dashboard is **read-only**. Face data and
check-in photos **never leave the laptop** — only text attendance data syncs.

## Developer password (locking the cloud keys)

The Supabase URL + `service_role` key are sensitive and shouldn't be changed by
everyday staff. In **Settings → Cloud Sync** you set a separate **developer password**;
once set, those fields are **🔒 locked** (admins can still click "Sync now"). To edit
them later you click **Unlock** and enter the developer password. This is how each
self-hoster secures their own backend keys on their own machine.

## Anti-spoofing

- **Active challenge (on):** the kiosk asks the person to blink or turn their head,
  verified from the face detector's keypoints — defeats a held-up photo.
- **Passive anti-spoof (optional):** drop a Silent-Face-style ONNX model at
  `data/models/antispoof.onnx` to also reject printed photos / phone screens with no
  user action (`liveness_threshold` controls strictness).

Every check-in also saves an audit thumbnail under `data/thumbnails/`.

## Tech stack

- **Python 3.x**, **CustomTkinter** GUI
- **insightface** (RetinaFace detection + ArcFace recognition) on **onnxruntime** (CPU)
- **SQLite** local DB, **bcrypt** passwords, **openpyxl** Excel export, **requests** sync
- **Supabase** (Postgres + Auth + RLS) cloud · **React + Vite** dashboard

> TensorFlow/DeepFace are intentionally avoided; the ONNX stack is lighter and works
> across Python versions including 3.14.

## Project layout

```
main.py            entry point
config.py          paths, defaults, thresholds, icon
app/core/          camera, face engine, liveness, attendance service
app/db/            SQLite schema + repositories
app/sync/          one-way Supabase push + background scheduler
app/security/      admin + developer password auth
app/ui/            CustomTkinter views (kiosk, login, admin, teachers, enroll, reports, settings)
app/utils/         image + export helpers
dashboard/         React (Vite) read-only web dashboard
supabase/          cloud schema.sql + setup guide
packaging/         PyInstaller spec, icon, portable build script
launcher/          no-console desktop shortcut + setup scripts
.github/workflows/ build & release CI
data/              local DB, thumbnails, models, logs (gitignored)
```

## Privacy note

You store people's facial data, so get their consent. Face **embeddings** (math
vectors) are the primary record; thumbnails are kept locally for audit only.

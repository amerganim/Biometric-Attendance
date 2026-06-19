# Attendance Web Dashboard

A read-only web view of the attendance data synced to Supabase by the desktop kiosk
app. Admins log in to view, filter, and export attendance and see the teacher list.
All teacher registration / face enrollment stays in the desktop app.

## Prerequisites

- Node.js 18+ installed.
- A Supabase project with the schema applied and a login user created — see
  [`../supabase/README.md`](../supabase/README.md).

## Configure

```bash
cd dashboard
cp .env.example .env
```

Edit `.env` and paste your **Project URL** and **anon public key**
(Supabase → Project Settings → API). The anon key is safe to expose in a deployed
site; Row Level Security limits it to authenticated reads.

## Run locally

```bash
npm install
npm run dev
```

Open the printed URL, log in with the email/password you created in Supabase
Authentication, and you'll see attendance and teachers.

## Build / deploy (free)

```bash
npm run build      # outputs static files to dist/
```

Deploy `dist/` to **Vercel** or **Netlify**:
- Push this repo to GitHub, import it in Vercel/Netlify.
- Set the project root to `dashboard/` (build command `npm run build`, output `dist`).
- Add env vars `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in the host's settings.

## Features

- Email/password login (Supabase Auth).
- Attendance table with date-range, teacher, and status (present/late) filters.
- Export the current view to **CSV** or **Excel**.
- Read-only teacher list.

This dashboard never writes to the database; it only reads what the kiosk syncs up.

# Cloud setup (Supabase) — one time

This connects the kiosk app to a free cloud database so attendance can be viewed
from anywhere via the web dashboard. Sync is one-way: the laptop pushes data up;
the dashboard only reads. Photos and face data never leave the laptop.

## 1. Create the project

1. Go to <https://supabase.com> → sign up (free) → **New project**.
2. Pick a name and a strong database password, choose the nearest region, create it.
3. Wait ~2 minutes for it to finish provisioning.

## 2. Create the tables

1. In the project, open **SQL Editor** → **New query**.
2. Paste the contents of [`schema.sql`](schema.sql) and click **Run**.
   You should see the `teachers` and `attendance` tables under **Table Editor**.

## 3. Get your keys

Open **Project Settings → API** and copy three values:

| Value | Used by | Secret? |
|---|---|---|
| **Project URL** | both | no |
| **`anon` public key** | web dashboard | safe to publish |
| **`service_role` key** | desktop app sync only | **KEEP SECRET** |

> The `service_role` key bypasses all security rules. Only paste it into the desktop
> app on the kiosk laptop. Never put it in the dashboard or in git.

## 4. Create a dashboard login

Open **Authentication → Users → Add user**, enter an email + password. This is the
account you'll use to log in to the web dashboard.

## 5. Connect the desktop app

In the desktop app: **Admin → Settings → Cloud Sync**:
1. Paste the **Project URL** and the **`service_role` key**.
2. Tick **Enable cloud sync** and click **Sync now**.
3. Your teachers and attendance should appear in Supabase **Table Editor**.

## 6. Run the dashboard

See [`../dashboard/README.md`](../dashboard/README.md) — paste the **Project URL** and
the **`anon` key** into the dashboard's `.env`, then run or deploy it.

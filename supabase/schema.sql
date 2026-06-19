-- Biometric-Attendance — Phase 2 cloud schema.
-- Run this once in the Supabase SQL Editor (see supabase/README.md).
--
-- Mirrors the local SQLite tables but WITHOUT face embeddings or photo paths —
-- only text attendance data is synced to the cloud. The desktop app pushes rows
-- with the service_role key (which bypasses RLS); the web dashboard reads them as
-- an authenticated user.

create table if not exists public.teachers (
    id             uuid primary key,
    full_name      text not null,
    employee_code  text,
    email          text,
    phone          text,
    department     text,
    active         boolean not null default true,
    consent_signed boolean not null default false,
    created_at     timestamptz,
    updated_at     timestamptz
);

create table if not exists public.attendance (
    id             uuid primary key,
    teacher_id     uuid references public.teachers(id) on delete cascade,
    check_type     text not null,                 -- 'in' | 'out'
    "timestamp"    timestamptz not null,
    status         text not null default 'present', -- 'present' | 'late'
    liveness_score real,
    created_at     timestamptz
);

create index if not exists idx_attendance_teacher on public.attendance(teacher_id);
create index if not exists idx_attendance_time    on public.attendance("timestamp");

-- ---------------------------------------------------------------------------
-- Row Level Security: dashboard users may READ; nobody may write via anon/auth.
-- The desktop sync uses the service_role key, which bypasses RLS entirely.
-- ---------------------------------------------------------------------------
alter table public.teachers   enable row level security;
alter table public.attendance enable row level security;

drop policy if exists "authenticated read teachers" on public.teachers;
create policy "authenticated read teachers" on public.teachers
    for select to authenticated using (true);

drop policy if exists "authenticated read attendance" on public.attendance;
create policy "authenticated read attendance" on public.attendance
    for select to authenticated using (true);

-- Catholic Jobs Watcher — Supabase schema
-- Run this once in the TCAI Supabase project (SQL editor).

create table if not exists job_watcher_seen (
  id uuid primary key default gen_random_uuid(),
  posting_id text not null,
  source text not null,
  company text,
  title text,
  location text,
  url text,
  raw jsonb,
  description text,
  fit_score int,
  catholic_aligned boolean,
  senior_design_or_product boolean,
  remote_or_indiana boolean,
  fit_reason text,
  status text not null default 'new'
    check (status in ('new', 'starred', 'applied', 'dismissed')),
  first_seen_at timestamptz not null default now(),
  notified_at timestamptz,
  status_updated_at timestamptz,
  unique (source, posting_id)
);

create index if not exists job_watcher_seen_first_seen_idx
  on job_watcher_seen (first_seen_at desc);

create index if not exists job_watcher_seen_unnotified_idx
  on job_watcher_seen (notified_at)
  where notified_at is null;

create index if not exists job_watcher_seen_status_idx
  on job_watcher_seen (status);

-- Keep status_updated_at in lockstep with status changes.
create or replace function job_watcher_seen_touch_status()
returns trigger language plpgsql as $$
begin
  if (tg_op = 'UPDATE' and new.status is distinct from old.status) then
    new.status_updated_at := now();
  end if;
  return new;
end $$;

drop trigger if exists job_watcher_seen_touch_status_trg on job_watcher_seen;
create trigger job_watcher_seen_touch_status_trg
  before update on job_watcher_seen
  for each row execute function job_watcher_seen_touch_status();

-- ------------------------------------------------------------------
-- Row-Level Security
-- ------------------------------------------------------------------
alter table job_watcher_seen enable row level security;

-- Anon role can read every row (dashboard is read-mostly).
drop policy if exists "anon can read" on job_watcher_seen;
create policy "anon can read"
  on job_watcher_seen
  for select
  to anon
  using (true);

-- Anon role can update *only* the status field. The using/with check
-- predicates don't restrict columns directly; column-level perms below do.
drop policy if exists "anon can update status" on job_watcher_seen;
create policy "anon can update status"
  on job_watcher_seen
  for update
  to anon
  using (true)
  with check (true);

-- Restrict the anon role at the column level so the dashboard can only
-- write `status` and `status_updated_at` (everything else is server-only).
revoke update on job_watcher_seen from anon;
grant update (status, status_updated_at) on job_watcher_seen to anon;

-- Note: the service_role bypasses RLS, so the watcher inserts work
-- without additional policies.

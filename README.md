# Catholic Jobs Watcher

A scheduled job watcher that finds senior UX / product / design roles at
genuinely Catholic organizations, scores each posting with Google
Gemini 2.0 Flash (free tier) for fit, dedupes via Supabase, and notifies
via daily email digest + a dashboard.

## What it does

Every morning at 13:00 UTC (~8am ET), GitHub Actions runs the watcher:

1. **Fetch** postings from a curated list of ATS-backed careers boards
   (Greenhouse / Lever / Ashby / Workable), RSS feeds (Indeed), and
   eventual custom scrapers.
2. **Pre-filter** by title regex (level keyword × discipline keyword) so
   we don't burn LLM quota on obviously off-target postings.
3. **Dedupe** against Supabase by `(source, posting_id)`.
4. **Score** each new posting with `gemini-2.0-flash` using
   `response_schema` for guaranteed JSON returning `{catholic_aligned,
   senior_design_or_product, remote_or_indiana, fit_score, fit_reason}`.
5. **Store** every scored posting (so we have history).
6. **Email** a digest via Resend if any posting is Catholic-aligned,
   senior, and scored ≥ 7 — zero-hit days send nothing.
7. **Dashboard** (GitHub Pages) lets you triage matches: Star, Applied,
   Dismiss, Reset.

## Repo layout

```
catholic-jobs-watcher/
├── .github/workflows/
│   ├── check.yml                # daily cron + run
│   └── deploy-dashboard.yml     # build & deploy dashboard to Pages
├── db/
│   └── schema.sql               # Supabase tables + RLS policies
├── dashboard/                   # static site (Pages)
│   ├── index.html
│   ├── app.js
│   ├── config.js                # populated by deploy workflow
│   └── styles.css
├── watcher/                     # Python job
│   ├── sources.py               # source registry
│   ├── fetchers.py              # ATS / RSS / scrape clients
│   ├── scorer.py                # Gemini fit scoring
│   ├── notifier.py              # Resend digest
│   ├── state.py                 # Supabase read/write
│   ├── main.py                  # orchestrator (CLI entrypoint)
│   └── requirements.txt
└── README.md
```

## One-time setup

### 1. Supabase

Run `db/schema.sql` in the TCAI Supabase project's SQL editor. It creates
`job_watcher_seen` plus RLS policies that let the dashboard (anon role)
read everything and update only the `status` column. The service role
bypasses RLS, so the watcher's inserts work without extra policies.

### 2. Resend

Create a Resend API key. Out of the box, the watcher sends from
`onboarding@resend.dev` — fine for testing. For real use, verify a domain
in Resend and set the `RESEND_FROM` Actions Variable below (e.g.
`Catholic Jobs <jobs@yourdomain.com>`).

### 3. GitHub repo settings → Secrets and Variables → Actions

**Repository Secrets** (sensitive, never exposed to client):

- `GEMINI_API_KEY` — Google AI Studio API key for Gemini scoring.
  Get a free one (no card required) at https://aistudio.google.com/apikey
- `SUPABASE_URL` — TCAI Supabase project URL
- `SUPABASE_SERVICE_KEY` — TCAI service-role key (server-only; bypasses RLS)
- `RESEND_API_KEY` — Resend API key
- `NOTIFY_EMAIL` — where digests go (e.g. `michaelkrontz@gmail.com`)
- `DASHBOARD_SECRET` — optional, any non-empty string gates the dashboard

**Repository Variables** (visible in build logs; safe for public values):

- `SUPABASE_URL` — same Supabase URL, mirrored for the dashboard build
- `SUPABASE_ANON_KEY` — anon key (safe in client when RLS is enabled)
- `RESEND_FROM` — optional, e.g. `Catholic Jobs <jobs@yourdomain.com>`
- `DASHBOARD_URL` — optional, used in the email footer
  (default: `https://truecatholicai.github.io/catholic-jobs-watcher/`)

### 4. GitHub Pages

Settings → Pages → Source = "GitHub Actions". After the first push to
`main` that touches `dashboard/**`, the deploy workflow publishes the
site to `https://truecatholicai.github.io/catholic-jobs-watcher/`.

### 5. Cold start

The first scheduled run will see *everything* as new and try to score
all of it. To avoid a 200-posting digest, do one of these on first run:

- Trigger `catholic-jobs-watch` manually with `cap = 5` and let the
  remaining matches accrue in the dashboard for catch-up triage, **or**
- Trigger it with `skip_notify = true` to seed Supabase silently, then
  let the next day's cron pick things up cleanly.

## Day-to-day use

- **Email** — automatic, daily. Empty days send nothing.
- **Dashboard** — visit the Pages URL, optionally paste the
  `DASHBOARD_SECRET` if configured. Active view shows new + starred
  matches ≥ 7; History view shows everything with filters.
- **Manual run** — Actions tab → `catholic-jobs-watch` → "Run workflow".
  Options: `dry_run` (no DB/email), `skip_notify` (DB only), `cap` (cap
  digest size).

## Adding a new source

### ATS (Greenhouse / Lever / Ashby / Workable / Rippling) — one line

1. Find the org's careers page; view source / inspect network traffic
   to identify the ATS provider and slug. Examples:
   - Greenhouse: `boards.greenhouse.io/<slug>` → slug is `<slug>`
   - Lever: `jobs.lever.co/<slug>` → slug is `<slug>`
   - Ashby: `jobs.ashbyhq.com/<slug>` → slug is `<slug>`
   - Workable: apply links `apply.workable.com/<slug>/j/<code>/`
     or `<slug>@jobs.workablemail.com`
   - Rippling: `<slug>.rippling-ats.com` → slug is `<slug>`
2. Append an entry to `ATS_SOURCES` in `watcher/sources.py`:

   ```python
   {"name": "greenhouse:newslug", "provider": "greenhouse",
    "slug": "newslug", "company": "New Org"},
   ```

3. Commit, push. Next scheduled run picks it up.

### Currently-seeded sources

ATS-backed (direct):
- **Word on Fire** — Rippling-ATS (RSS-based)
- **Ascension Press** — Workable (`ascension-publishing-group`)

Aggregators:
- **Indeed RSS** — Catholic-tagged senior UX/PM/Design search
- **jobsforcatholics.com** — Catholic-specific aggregator (JSON-LD scrape)

Known-but-skipped (enterprise HR systems or anti-bot blocks — senior
postings should still surface via the aggregators):
- **Hallow** — Gem (jobs.gem.com/hallow). JS-only SPA, no public API;
  needs Playwright.
- **Augustine Institute / Formed** — ADP WorkforceNow. No public JSON.
- **FOCUS** — careers page Cloudflare-blocks scrapers.
- **Catholic Relief Services** — careers page Cloudflare-blocks scrapers.
- **Knights of Columbus** — SAP SuccessFactors (`career41.sapsf.com`).
- **Catholic Charities USA** — federation only, no central ATS.

### RSS

Append to `RSS_SOURCES` in `watcher/sources.py` with `{name, url,
company}`. RSS items with titles like `"Role - Company - Location"` are
auto-parsed.

### Custom scraper (Playwright / httpx + HTML)

1. Add `fetch_<name>(source)` in `watcher/fetchers.py` returning
   normalized posting dicts.
2. Append an entry to `SCRAPE_SOURCES` in `watcher/sources.py` with
   `{name, fn: "fetch_<name>", company}`.
3. If the source blocks scrapers, leave it commented and move on.

## Local development

```bash
cd watcher
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Smoke test — no DB / no email
python -m watcher.main --dry-run -v

# Full pass (needs env vars)
export GEMINI_API_KEY=...
export SUPABASE_URL=...
export SUPABASE_SERVICE_KEY=...
export RESEND_API_KEY=...
export NOTIFY_EMAIL=...
python -m watcher.main --skip-notify -v   # populate DB without email
python -m watcher.main --cap 5 -v         # cold-start safe
```

## Security notes

- The **anon** key in `dashboard/config.js` is intentionally public and
  is gated by RLS (read-everything, update-status-only on a single
  table). Never put the **service** key in the dashboard.
- `DASHBOARD_SECRET` is a client-side check stored in `localStorage`.
  Not real auth — fine for a personal triage tool given the underlying
  data is public job postings. Don't repurpose this dashboard for
  sensitive data without proper auth.

## Cost

- Gemini 2.0 Flash: free tier (1500 req/day, 15 RPM). Watcher uses
  <100 calls/day at the prefilter rate, so **$0/month** with no credit
  card on file. The 4.5s inter-call sleep in `main.py` keeps us under
  the RPM limit even at burst-cold-start volumes.
- Supabase: trivial; reuses the existing TCAI project.
- Resend: free tier covers daily digests.
- GitHub Actions: well within the free tier (cron + a small dashboard
  build).

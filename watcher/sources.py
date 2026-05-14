"""Source registry for Catholic Jobs Watcher.

Each source declares its kind (ats / rss / scrape) and the parameters
needed by the matching fetcher in fetchers.py.

Adding a new ATS source: drop a dict into ATS_SOURCES with the right
provider and slug. That's it.

Adding a new scraper: write a fetch_<name>() in fetchers.py, then
register it here under SCRAPE_SOURCES.

----------------------------------------------------------------------
ATS assignments confirmed by investigation (2026-05-14)
----------------------------------------------------------------------
  Hallow                    → Gem (jobs.gem.com/hallow) — SPA, no public
                              API; needs Playwright. DEFERRED.
  Word on Fire              → Rippling-ATS (HiringThing under the hood);
                              public RSS at /api/rss.xml per board.
  Ascension Press           → Workable; slug "ascension-publishing-group".

ATS-backed (still to investigate):
  Augustine Institute / Formed → ADP WorkforceNow (enterprise; no public
                                 JSON board). Aggregators only.
  FOCUS                        → careers page Cloudflare-blocks scrapers.
                                 Aggregators only.
  Catholic Relief Services     → careers page Cloudflare-blocks scrapers.
                                 Aggregators only.
  Knights of Columbus          → SAP SuccessFactors (career41.sapsf.com).
                                 Enterprise; aggregators only.
  Catholic Charities USA       → No central ATS — federation of member
                                 orgs each running their own HR system.
                                 Aggregators only.

For everything in the "aggregators only" bucket, senior postings still
get caught via Indeed RSS, jobsforcatholics.com, and CatholicJobs.com.
"""

ATS_SOURCES = [
    # --- Greenhouse ---
    # (no confirmed Catholic-org Greenhouse boards yet — list left empty
    # rather than seeded with guesses)

    # --- Lever ---
    # (none yet)

    # --- Ashby ---
    # (none yet)

    # --- Workable ---
    # Use the full brand "Ascension Press" — the short form "Ascension"
    # is ambiguous (Ascension Health is a separate, non-Catholic-defining
    # enterprise) and Haiku needs the disambiguation since the Catholic
    # mission language doesn't appear in their Workable description until
    # past the 2500-char DESC_MAX truncation window.
    {"name": "workable:ascension", "provider": "workable",
     "slug": "ascension-publishing-group", "company": "Ascension Press"},

    # --- Rippling-ATS (HiringThing) ---
    {"name": "rippling:wordonfire", "provider": "rippling",
     "slug": "word-on-fire", "company": "Word on Fire"},
]

RSS_SOURCES = [
    {
        "name": "rss:indeed-catholic-senior",
        "company": None,  # parsed per-item from feed title
        "url": (
            "https://www.indeed.com/rss?"
            "q=%22catholic%22+%28ux+OR+%22product+design%22+OR+%22product+management%22%29"
            "+%28director+OR+principal+OR+manager+OR+head%29&l="
        ),
    },
]

# Custom scrapers (Playwright or httpx + HTML/JSON-LD parsing).
# Each entry maps to a fetch_<name> in fetchers.py.
SCRAPE_SOURCES = [
    {"name": "scrape:jobsforcatholics", "company": None,
     "fn": "fetch_jobsforcatholics"},
    # ----- DEFERRED (need Playwright or session-aware fetch) -----
    # {"name": "scrape:gem-hallow",   "company": "Hallow",
    #  "fn": "fetch_gem_hallow"},   # Hallow's Gem SPA — needs Playwright
    # {"name": "scrape:catholicjobs", "company": None,
    #  "fn": "fetch_catholicjobs"},
    # {"name": "scrape:ewtn",         "company": "EWTN",
    #  "fn": "fetch_ewtn"},
    # {"name": "scrape:osv",          "company": "Our Sunday Visitor",
    #  "fn": "fetch_osv"},
    # {"name": "scrape:ignatius",     "company": "Ignatius Press",
    #  "fn": "fetch_ignatius"},
    # {"name": "scrape:catholicanswers", "company": "Catholic Answers",
    #  "fn": "fetch_catholic_answers"},
    # {"name": "scrape:usccb",        "company": "USCCB",
    #  "fn": "fetch_usccb"},
    # {"name": "scrape:relevantradio","company": "Relevant Radio",
    #  "fn": "fetch_relevant_radio"},
    # Universities (lower priority — wire up once ATS sources are humming):
    # {"name": "scrape:notredame",    "company": "University of Notre Dame",
    #  "fn": "fetch_notredame"},
    # {"name": "scrape:catholicu",    "company": "Catholic University of America",
    #  "fn": "fetch_catholicu"},
    # {"name": "scrape:bostoncollege","company": "Boston College",
    #  "fn": "fetch_bostoncollege"},
    # {"name": "scrape:georgetown",   "company": "Georgetown University",
    #  "fn": "fetch_georgetown"},
    # {"name": "scrape:villanova",    "company": "Villanova University",
    #  "fn": "fetch_villanova"},
    # {"name": "scrape:steubenville", "company": "Franciscan University of Steubenville",
    #  "fn": "fetch_steubenville"},
    # {"name": "scrape:avemaria",     "company": "Ave Maria University",
    #  "fn": "fetch_avemaria"},
    # {"name": "scrape:stthomasmn",   "company": "University of St. Thomas (MN)",
    #  "fn": "fetch_stthomas_mn"},
    # {"name": "scrape:stthomastx",   "company": "University of St. Thomas (TX)",
    #  "fn": "fetch_stthomas_tx"},
]

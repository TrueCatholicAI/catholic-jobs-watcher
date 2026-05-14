"""Source registry for Catholic Jobs Watcher.

Each source declares its kind (ats / rss / scrape) and the parameters
needed by the matching fetcher in fetchers.py.

Adding a new ATS source: drop a dict into ATS_SOURCES with the right
provider and slug. That's it.

Adding a new scraper: write a fetch_<name>() in fetchers.py, then
register it here under SCRAPE_SOURCES.
"""

ATS_SOURCES = [
    # --- Greenhouse ---
    {"name": "greenhouse:hallow",          "provider": "greenhouse", "slug": "hallow",            "company": "Hallow"},
    {"name": "greenhouse:wordonfire",      "provider": "greenhouse", "slug": "wordonfire",        "company": "Word on Fire"},
    {"name": "greenhouse:ascensionpress",  "provider": "greenhouse", "slug": "ascensionpress",    "company": "Ascension"},
    {"name": "greenhouse:augustine",       "provider": "greenhouse", "slug": "augustineinstitute","company": "Augustine Institute / Formed"},
    {"name": "greenhouse:focus",           "provider": "greenhouse", "slug": "focus",             "company": "FOCUS"},
    {"name": "greenhouse:crs",             "provider": "greenhouse", "slug": "catholicreliefservices", "company": "Catholic Relief Services"},
    {"name": "greenhouse:knightsofcolumbus","provider": "greenhouse","slug": "knightsofcolumbus", "company": "Knights of Columbus"},
    {"name": "greenhouse:catholiccharitiesusa","provider":"greenhouse","slug":"catholiccharitiesusa","company":"Catholic Charities USA"},

    # --- Lever ---
    # (placeholders — drop in if/when we find an org using Lever)

    # --- Ashby ---
    # (placeholders)

    # --- Workable ---
    # (placeholders)
]

RSS_SOURCES = [
    {
        "name": "rss:indeed-catholic-senior",
        "company": None,  # populated per-item from feed
        "url": (
            "https://www.indeed.com/rss?"
            "q=%22catholic%22+%28ux+OR+%22product+design%22+OR+%22product+management%22%29"
            "+%28director+OR+principal+OR+manager+OR+head%29&l="
        ),
    },
]

# Custom scrapers (Playwright or httpx + HTML parsing).
# Each entry maps to a fetch_<name> in fetchers.py.
SCRAPE_SOURCES = [
    # name, label, company shown
    # {"name": "scrape:catholicjobs",  "company": None, "fn": "fetch_catholicjobs"},
    # {"name": "scrape:ewtn",          "company": "EWTN", "fn": "fetch_ewtn"},
    # {"name": "scrape:osv",           "company": "Our Sunday Visitor", "fn": "fetch_osv"},
    # {"name": "scrape:ignatius",      "company": "Ignatius Press", "fn": "fetch_ignatius"},
    # {"name": "scrape:catholicanswers","company": "Catholic Answers", "fn": "fetch_catholic_answers"},
    # {"name": "scrape:usccb",         "company": "USCCB", "fn": "fetch_usccb"},
    # {"name": "scrape:relevantradio", "company": "Relevant Radio", "fn": "fetch_relevant_radio"},
    # Universities (lower priority — wire up once ATS sources are humming):
    # {"name": "scrape:notredame",     "company": "University of Notre Dame", "fn": "fetch_notredame"},
    # {"name": "scrape:catholicu",     "company": "Catholic University of America", "fn": "fetch_catholicu"},
    # {"name": "scrape:bostoncollege", "company": "Boston College", "fn": "fetch_bostoncollege"},
    # {"name": "scrape:georgetown",    "company": "Georgetown University", "fn": "fetch_georgetown"},
    # {"name": "scrape:villanova",     "company": "Villanova University", "fn": "fetch_villanova"},
    # {"name": "scrape:steubenville",  "company": "Franciscan University of Steubenville", "fn": "fetch_steubenville"},
    # {"name": "scrape:avemaria",      "company": "Ave Maria University", "fn": "fetch_avemaria"},
    # {"name": "scrape:stthomasmn",    "company": "University of St. Thomas (MN)", "fn": "fetch_stthomas_mn"},
    # {"name": "scrape:stthomastx",    "company": "University of St. Thomas (TX)", "fn": "fetch_stthomas_tx"},
]

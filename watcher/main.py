"""Orchestrator: fetch -> pre-filter -> dedup -> score -> store -> notify."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Any

from . import fetchers, notifier, scorer, sources, state

log = logging.getLogger("watcher")


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def fetch_all() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for src in sources.ATS_SOURCES:
        rows = fetchers.fetch_ats(src)
        log.info("ats %s: %d postings", src["name"], len(rows))
        out.extend(rows)
    for src in sources.RSS_SOURCES:
        rows = fetchers.fetch_rss(src)
        log.info("rss %s: %d postings", src["name"], len(rows))
        out.extend(rows)
    for src in sources.SCRAPE_SOURCES:
        rows = fetchers.fetch_scrape(src)
        log.info("scrape %s: %d postings", src["name"], len(rows))
        out.extend(rows)
    return out


def run(
    *,
    dry_run: bool = False,
    skip_notify: bool = False,
    cap_notifications: int | None = None,
    threshold: int = 7,
) -> dict[str, int]:
    """Single end-to-end pass. Returns a small stats dict."""
    stats = {"fetched": 0, "prefilter_passed": 0, "new": 0, "scored": 0, "inserted": 0, "notified": 0}

    fetched = fetch_all()
    stats["fetched"] = len(fetched)
    if not fetched:
        log.warning("no postings fetched from any source")
        return stats

    passed = [p for p in fetched if scorer.passes_prefilter(p)]
    stats["prefilter_passed"] = len(passed)
    log.info("prefilter: %d / %d kept", len(passed), len(fetched))

    if dry_run:
        for p in passed[:20]:
            log.info("DRY %s | %s @ %s | %s", p["source"], p["title"], p.get("company"), p.get("url"))
        return stats

    db = state._client()
    new_postings = state.filter_new(db, passed)
    stats["new"] = len(new_postings)
    log.info("dedup: %d new (of %d prefiltered)", len(new_postings), len(passed))

    llm_client = None
    if new_postings:
        llm_client = scorer._client()

    # Gemini free tier is 15 RPM; 4.5s between calls = 13.3 RPM, safely
    # under the limit even if the first request lands at second 0 of
    # the rate window.
    rate_sleep = 4.5

    for i, posting in enumerate(new_postings):
        if i > 0:
            time.sleep(rate_sleep)
        score = scorer.score_posting_with_retry(posting, client=llm_client)
        if score is not None:
            stats["scored"] += 1
        inserted = state.insert_scored(db, posting, score)
        if inserted:
            stats["inserted"] += 1

    if skip_notify:
        log.info("notify: skipped (flag)")
        return stats

    matches = state.fetch_unnotified_matches(db, threshold=threshold)
    if cap_notifications:
        matches = matches[:cap_notifications]
    if not matches:
        log.info("notify: 0 matches, skipping email")
        return stats

    sent = notifier.send_digest(matches)
    if sent:
        state.mark_notified(db, [m["id"] for m in matches])
        stats["notified"] = len(matches)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Catholic Jobs Watcher")
    ap.add_argument("--dry-run", action="store_true", help="Fetch + pre-filter only; no DB writes, no email.")
    ap.add_argument("--skip-notify", action="store_true", help="Score + store but do not send email.")
    ap.add_argument("--cap", type=int, default=None, help="Cap the number of postings included in the digest (cold-start safety).")
    ap.add_argument("--threshold", type=int, default=7, help="Minimum fit_score to include in digest (default 7).")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    configure_logging(args.verbose)

    # Fail fast on missing required env (except in --dry-run, which doesn't need DB/email).
    if not args.dry_run:
        missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GEMINI_API_KEY") if not os.environ.get(k)]
        if missing:
            log.error("missing required env: %s", ", ".join(missing))
            return 2

    stats = run(
        dry_run=args.dry_run,
        skip_notify=args.skip_notify,
        cap_notifications=args.cap,
        threshold=args.threshold,
    )
    log.info("done: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())

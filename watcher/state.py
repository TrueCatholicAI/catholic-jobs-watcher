"""Supabase persistence for job postings."""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable

from supabase import Client, create_client

log = logging.getLogger(__name__)

TABLE = "job_watcher_seen"


def _client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, key)


def existing_keys(client: Client, postings: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    """Return the (source, posting_id) pairs already in Supabase."""
    pairs = [(p["source"], p["posting_id"]) for p in postings]
    if not pairs:
        return set()
    sources = sorted({s for s, _ in pairs})
    ids = sorted({pid for _, pid in pairs})
    # Filter both sides server-side; cheap enough at our volumes.
    resp = (
        client.table(TABLE)
        .select("source,posting_id")
        .in_("source", sources)
        .in_("posting_id", ids)
        .execute()
    )
    return {(row["source"], row["posting_id"]) for row in (resp.data or [])}


def filter_new(client: Client, postings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = existing_keys(client, postings)
    return [p for p in postings if (p["source"], p["posting_id"]) not in seen]


def insert_scored(client: Client, posting: dict[str, Any], score: dict[str, Any] | None) -> dict[str, Any] | None:
    """Insert a scored (or unscored) posting. Returns the inserted row, or None on conflict/error."""
    row = {
        "posting_id": posting["posting_id"],
        "source": posting["source"],
        "company": posting.get("company"),
        "title": posting.get("title"),
        "location": posting.get("location"),
        "url": posting.get("url"),
        "raw": posting.get("raw"),
        "description": posting.get("description"),
    }
    if score:
        row.update({
            "fit_score": score.get("fit_score"),
            "catholic_aligned": score.get("catholic_aligned"),
            "senior_design_or_product": score.get("senior_design_or_product"),
            "remote_or_indiana": score.get("remote_or_indiana"),
            "fit_reason": score.get("fit_reason"),
        })
    try:
        resp = client.table(TABLE).insert(row).execute()
        return (resp.data or [None])[0]
    except Exception as exc:  # noqa: BLE001
        # Likely a unique-violation race; safe to skip.
        log.info("insert skipped for %s/%s: %s", row["source"], row["posting_id"], exc)
        return None


def fetch_unnotified_matches(client: Client, threshold: int = 7) -> list[dict[str, Any]]:
    resp = (
        client.table(TABLE)
        .select("*")
        .is_("notified_at", "null")
        .eq("status", "new")
        .eq("catholic_aligned", True)
        .eq("senior_design_or_product", True)
        .gte("fit_score", threshold)
        .order("fit_score", desc=True)
        .order("first_seen_at", desc=True)
        .execute()
    )
    return resp.data or []


def mark_notified(client: Client, ids: list[str]) -> None:
    if not ids:
        return
    # Use Postgres NOW() via RPC-style update — supabase-py sends a single PATCH with a filter.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    client.table(TABLE).update({"notified_at": now}).in_("id", ids).execute()

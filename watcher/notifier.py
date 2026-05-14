"""Resend email digest."""

from __future__ import annotations

import html
import logging
import os
from datetime import date
from typing import Any

import httpx

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "Catholic Jobs Watcher <onboarding@resend.dev>"
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://truecatholicai.github.io/catholic-jobs-watcher/",
)


def _badge_color(score: int | None) -> str:
    if score is None:
        return "#9ca3af"
    if score >= 9:
        return "#16a34a"
    if score >= 7:
        return "#0891b2"
    return "#6b7280"


def _row_html(row: dict[str, Any]) -> str:
    title = html.escape(row.get("title") or "(untitled)")
    company = html.escape(row.get("company") or "")
    location = html.escape(row.get("location") or "")
    url = row.get("url") or "#"
    score = row.get("fit_score")
    reason = html.escape(row.get("fit_reason") or "")
    color = _badge_color(score)
    return f"""
    <tr><td style="padding:14px 0;border-bottom:1px solid #e5e7eb;">
      <div style="font-size:16px;font-weight:600;margin-bottom:4px;">
        <a href="{html.escape(url)}" style="color:#0f172a;text-decoration:none;">{title}</a>
        <span style="display:inline-block;margin-left:8px;padding:2px 8px;border-radius:999px;
                     background:{color};color:white;font-size:12px;font-weight:700;vertical-align:middle;">
          {score if score is not None else "?"}/10
        </span>
      </div>
      <div style="color:#475569;font-size:14px;margin-bottom:6px;">
        <strong>{company}</strong>{(" · " + location) if location else ""}
      </div>
      <div style="color:#334155;font-size:14px;line-height:1.45;">{reason}</div>
    </td></tr>
    """


def build_digest_html(rows: list[dict[str, Any]]) -> str:
    items = "\n".join(_row_html(r) for r in rows)
    return f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f8fafc;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:640px;margin:0 auto;background:white;border-radius:12px;padding:24px;">
    <h1 style="font-size:20px;margin:0 0 4px;">Catholic Jobs — {len(rows)} new match{"" if len(rows)==1 else "es"}</h1>
    <div style="color:#64748b;font-size:13px;margin-bottom:16px;">{date.today().isoformat()}</div>
    <table style="width:100%;border-collapse:collapse;">{items}</table>
    <div style="margin-top:24px;font-size:13px;color:#64748b;">
      <a href="{html.escape(DASHBOARD_URL)}" style="color:#0891b2;">Open dashboard →</a>
    </div>
  </div>
</body></html>"""


def send_digest(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        log.info("notifier: no rows, skipping email")
        return False
    api_key = os.environ.get("RESEND_API_KEY")
    to = os.environ.get("NOTIFY_EMAIL")
    if not api_key or not to:
        log.warning("notifier: RESEND_API_KEY or NOTIFY_EMAIL missing — skipping send")
        return False

    plural = "" if len(rows) == 1 else "es"
    subject = f"[Catholic Jobs] {len(rows)} new match{plural} — {date.today().isoformat()}"
    body = build_digest_html(rows)

    sender = os.environ.get("RESEND_FROM", DEFAULT_FROM)
    payload = {"from": sender, "to": [to], "subject": subject, "html": body}

    try:
        r = httpx.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        r.raise_for_status()
        log.info("notifier: sent digest (%d rows) to %s", len(rows), to)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("notifier: send failed: %s", exc)
        return False

"""Fetchers for each source kind.

Every fetcher returns a list of normalized posting dicts:
    {
        "source":      "<source_name>",
        "posting_id":  "<stable id>",
        "title":       "...",
        "company":     "...",
        "location":    "...",
        "url":         "...",
        "description": "<cleaned plaintext>",
        "raw":         {<full upstream payload>},
    }
"""

from __future__ import annotations

import hashlib
import logging
import re
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree as ET

import httpx

log = logging.getLogger(__name__)

HTTP_TIMEOUT = 30.0
UA = "catholic-jobs-watcher/1.0 (+https://github.com/TrueCatholicAI/catholic-jobs-watcher)"


# ---------- HTML -> text ----------

class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "li", "div", "h1", "h2", "h3", "h4", "tr"):
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._chunks.append(data)


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    text = "".join(p._chunks)
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def hash_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


# ---------- ATS clients ----------

def fetch_greenhouse(slug: str, source_name: str, company: str) -> list[dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    out: list[dict[str, Any]] = []
    try:
        r = httpx.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": UA})
        if r.status_code == 404:
            log.warning("greenhouse %s: board not found", slug)
            return []
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("greenhouse %s fetch failed: %s", slug, exc)
        return []

    for job in payload.get("jobs", []):
        loc = (job.get("location") or {}).get("name") or ""
        out.append({
            "source": source_name,
            "posting_id": str(job.get("id")),
            "title": (job.get("title") or "").strip(),
            "company": company,
            "location": loc,
            "url": job.get("absolute_url") or "",
            "description": html_to_text(job.get("content")),
            "raw": job,
        })
    return out


def fetch_lever(slug: str, source_name: str, company: str) -> list[dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    out: list[dict[str, Any]] = []
    try:
        r = httpx.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": UA})
        if r.status_code == 404:
            return []
        r.raise_for_status()
        jobs = r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("lever %s fetch failed: %s", slug, exc)
        return []

    for job in jobs:
        desc_html = job.get("descriptionPlain") or job.get("description") or ""
        cats = job.get("categories") or {}
        out.append({
            "source": source_name,
            "posting_id": str(job.get("id")),
            "title": (job.get("text") or "").strip(),
            "company": company,
            "location": cats.get("location") or "",
            "url": job.get("hostedUrl") or job.get("applyUrl") or "",
            "description": html_to_text(desc_html) if "<" in desc_html else desc_html,
            "raw": job,
        })
    return out


def fetch_ashby(slug: str, source_name: str, company: str) -> list[dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    out: list[dict[str, Any]] = []
    try:
        r = httpx.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": UA})
        if r.status_code == 404:
            return []
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("ashby %s fetch failed: %s", slug, exc)
        return []

    for job in payload.get("jobs", []):
        out.append({
            "source": source_name,
            "posting_id": str(job.get("id")),
            "title": (job.get("title") or "").strip(),
            "company": company,
            "location": job.get("locationName") or "",
            "url": job.get("jobUrl") or "",
            "description": html_to_text(job.get("descriptionHtml") or job.get("descriptionPlain") or ""),
            "raw": job,
        })
    return out


def fetch_workable(slug: str, source_name: str, company: str) -> list[dict[str, Any]]:
    url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"
    out: list[dict[str, Any]] = []
    try:
        r = httpx.post(
            url,
            json={"query": "", "department": [], "location": []},
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": UA, "Accept": "application/json"},
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("workable %s fetch failed: %s", slug, exc)
        return []

    for job in payload.get("results", []):
        loc_parts = [job.get("city"), job.get("state"), job.get("country")]
        loc = ", ".join(p for p in loc_parts if p) or ("Remote" if job.get("remote") else "")
        shortcode = job.get("shortcode") or ""
        url_job = f"https://apply.workable.com/{slug}/j/{shortcode}/" if shortcode else ""
        out.append({
            "source": source_name,
            "posting_id": str(job.get("id") or shortcode),
            "title": (job.get("title") or "").strip(),
            "company": company,
            "location": loc,
            "url": url_job,
            "description": html_to_text(job.get("description") or ""),
            "raw": job,
        })
    return out


_ATS_DISPATCH = {
    "greenhouse": fetch_greenhouse,
    "lever":      fetch_lever,
    "ashby":      fetch_ashby,
    "workable":   fetch_workable,
}


def fetch_ats(source: dict[str, Any]) -> list[dict[str, Any]]:
    fn = _ATS_DISPATCH.get(source["provider"])
    if not fn:
        log.warning("unknown ATS provider %r", source["provider"])
        return []
    return fn(source["slug"], source["name"], source["company"])


# ---------- RSS ----------

def fetch_rss(source: dict[str, Any]) -> list[dict[str, Any]]:
    url = source["url"]
    out: list[dict[str, Any]] = []
    try:
        r = httpx.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as exc:  # noqa: BLE001
        log.warning("rss %s fetch failed: %s", source["name"], exc)
        return []

    # RSS 2.0: <rss><channel><item>...
    items = root.findall(".//item")
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        # Indeed RSS embeds company in title like "Job Title - Company - Location"
        company = source.get("company")
        location = ""
        if " - " in title and not company:
            parts = [p.strip() for p in title.split(" - ")]
            if len(parts) >= 3:
                title, company, location = parts[0], parts[1], " - ".join(parts[2:])
            elif len(parts) == 2:
                title, company = parts[0], parts[1]
        out.append({
            "source": source["name"],
            "posting_id": hash_id(source["name"], link, title),
            "title": title,
            "company": company or "",
            "location": location,
            "url": link,
            "description": html_to_text(desc),
            "raw": {"title": title, "link": link, "description": desc},
        })
    return out


# ---------- Scrape dispatch (stubs to be filled in later) ----------

def fetch_scrape(source: dict[str, Any]) -> list[dict[str, Any]]:
    fn_name = source.get("fn")
    fn = globals().get(fn_name) if fn_name else None
    if not callable(fn):
        log.info("scrape %s: not implemented yet", source["name"])
        return []
    try:
        return fn(source)  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        log.warning("scrape %s failed: %s", source["name"], exc)
        return []


# Example skeleton for a future Playwright-based scraper:
#
# def fetch_ewtn(source: dict[str, Any]) -> list[dict[str, Any]]:
#     from playwright.sync_api import sync_playwright
#     out: list[dict[str, Any]] = []
#     with sync_playwright() as p:
#         browser = p.chromium.launch()
#         page = browser.new_page(user_agent=UA)
#         page.goto("https://www.ewtn.com/careers", wait_until="domcontentloaded")
#         # ... extract postings ...
#         browser.close()
#     return out

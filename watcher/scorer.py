"""Gemini-based fit scoring for job postings.

Uses Google AI Studio's free tier (1500 req/day, 15 RPM) via the unified
google-genai SDK with response_schema for guaranteed structured output.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

log = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"
# 5000 chars covers the "back half" of most postings — mission/values
# language (e.g. "Familiarity with the Catholic market is a plus" on
# the Ascension PM role at char 4060) routinely sits past 2500. Token
# cost stays trivial at Gemini Flash free-tier rates.
DESC_MAX = 5000

# Cheap pre-filter: senior level AND design/product/UX keywords.
# Intentionally loose — the LLM does the real filtering.
_LEVEL_RE = re.compile(
    r"\b(principal|director|manager|head|vp|vice\s+president|lead|sr\.?|senior|chief)\b",
    re.IGNORECASE,
)
_DISCIPLINE_RE = re.compile(
    r"\b(ux|ui|user\s+experience|product\s+design|product\s+manager|product\s+management|"
    r"design(?:er)?|digital\s+experience|cx|customer\s+experience|experience\s+design|"
    r"prod\s+mgmt)\b",
    re.IGNORECASE,
)


def passes_prefilter(posting: dict[str, Any]) -> bool:
    title = posting.get("title") or ""
    return bool(_LEVEL_RE.search(title) and _DISCIPLINE_RE.search(title))


SYSTEM_PROMPT = """You are filtering job postings for a Principal UX Designer \
seeking senior roles at genuinely Catholic organizations.

Evaluate the posting below and return your assessment.

Definitions:
- "catholic_aligned": The hiring organization is genuinely Catholic — a \
Catholic university, diocese, Catholic media/publishing/app company, \
Catholic nonprofit, or Catholic-owned business with an explicit Catholic \
mission. Generic "faith-based" or Protestant organizations do NOT count. \
When in doubt, lean false.
- "senior_design_or_product": The role is Principal, Director, Manager, \
Head, VP, Lead, or Senior level in UX, Design, Product Design, Product \
Management, or Digital Experience. Individual contributor "Senior \
Designer" counts. Pure engineering, marketing, or content roles do NOT \
count even if senior.
- "remote_or_indiana": Role is fully remote, hybrid with reasonable travel \
from Indianapolis IN, or based in Indiana.
- "fit_score": 1-10 holistic fit. 10 = dream role (e.g. Head of Product \
at Hallow, remote). 7+ = worth notifying. Below 7 = log but don't notify.
- "fit_reason": One sentence (max 20 words) explaining the score."""

# Gemini's schema format uses uppercase string types (not lowercase
# JSON Schema). Also: no minimum/maximum constraints — we clamp
# fit_score defensively after parsing.
REPORT_FIT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "catholic_aligned": {"type": "BOOLEAN"},
        "senior_design_or_product": {"type": "BOOLEAN"},
        "remote_or_indiana": {"type": "BOOLEAN"},
        "fit_score": {"type": "INTEGER"},
        "fit_reason": {"type": "STRING"},
    },
    "required": [
        "catholic_aligned",
        "senior_design_or_product",
        "remote_or_indiana",
        "fit_score",
        "fit_reason",
    ],
}


def _client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _build_user_message(posting: dict[str, Any]) -> str:
    location = (posting.get("location") or "").strip()
    raw_desc = (posting.get("description") or "").strip()
    # Prepend the structured location to the description body so it
    # survives the 5000-char truncation and the model weighs it for
    # remote_or_indiana even when the body itself doesn't mention
    # location. Belt-and-suspenders alongside the dedicated Location:
    # field below.
    combined = f"Location: {location}\n\n{raw_desc}" if location else raw_desc
    desc = combined[:DESC_MAX]
    return (
        "Posting:\n"
        f"Title: {posting.get('title') or ''}\n"
        f"Company: {posting.get('company') or ''}\n"
        f"Location: {location}\n"
        f"Description: {desc}"
    )


def score_posting(posting: dict[str, Any], client: genai.Client | None = None) -> dict[str, Any] | None:
    """Score one posting. Returns the structured fit dict or None on failure.

    Same signature as the previous Anthropic-backed implementation so the
    rest of the pipeline (main.py, state.py) doesn't change.
    """
    client = client or _client()
    user_message = _build_user_message(posting)

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=REPORT_FIT_SCHEMA,
                temperature=0.0,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini call failed for %s/%s: %s", posting.get("source"), posting.get("posting_id"), exc)
        return None

    text = (resp.text or "").strip()
    if not text:
        log.warning("gemini returned empty body for %s/%s", posting.get("source"), posting.get("posting_id"))
        return None
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("gemini JSON parse failed for %s/%s: %s | body=%r",
                    posting.get("source"), posting.get("posting_id"), exc, text[:200])
        return None

    # Defensive clamp — Gemini's schema can't enforce min/max on integers,
    # and we don't want a stray 0 or 11 leaking through to the digest.
    try:
        result["fit_score"] = max(1, min(10, int(result.get("fit_score", 1))))
    except (TypeError, ValueError):
        result["fit_score"] = 1

    return result


def score_posting_with_retry(
    posting: dict[str, Any],
    client: genai.Client | None = None,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    """Wrap score_posting with exponential backoff for transient 429/503s.

    Gemini's free tier occasionally rate-limits or hiccups under load. We
    keep the retries tight (1s, 2s, 4s) since per-run cost is bounded.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return score_posting(posting, client=client)
        except genai_errors.APIError as exc:
            last_exc = exc
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status not in (429, 500, 502, 503, 504):
                # Non-transient — don't retry.
                log.warning("gemini non-transient error for %s/%s: %s",
                            posting.get("source"), posting.get("posting_id"), exc)
                return None
            wait = 2 ** attempt  # 1s, 2s, 4s
            log.info("gemini %s for %s — retry %d/%d in %ds",
                     status, posting.get("posting_id"), attempt + 1, max_retries, wait)
            time.sleep(wait)
    log.warning("gemini retries exhausted for %s/%s: %s",
                posting.get("source"), posting.get("posting_id"), last_exc)
    return None

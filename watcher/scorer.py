"""Haiku-based fit scoring for job postings."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from anthropic import Anthropic

log = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
DESC_MAX = 2500

# Cheap pre-filter: senior level AND design/product/UX keywords.
# Intentionally loose — Haiku does the real filtering.
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


PROMPT = """You are filtering job postings for a Principal UX Designer seeking senior \
roles at genuinely Catholic organizations.

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
- "fit_reason": One sentence (max 20 words) explaining the score.

Posting:
Title: {title}
Company: {company}
Location: {location}
Description: {description}
"""

TOOL_SPEC = {
    "name": "report_fit",
    "description": "Report the fit assessment for the posting.",
    "input_schema": {
        "type": "object",
        "properties": {
            "catholic_aligned": {"type": "boolean"},
            "senior_design_or_product": {"type": "boolean"},
            "remote_or_indiana": {"type": "boolean"},
            "fit_score": {"type": "integer", "minimum": 1, "maximum": 10},
            "fit_reason": {"type": "string"},
        },
        "required": [
            "catholic_aligned",
            "senior_design_or_product",
            "remote_or_indiana",
            "fit_score",
            "fit_reason",
        ],
    },
}


def _client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=api_key)


def score_posting(posting: dict[str, Any], client: Anthropic | None = None) -> dict[str, Any] | None:
    """Score one posting. Returns the structured tool output dict or None on failure."""
    client = client or _client()
    desc = (posting.get("description") or "")[:DESC_MAX]
    prompt = PROMPT.format(
        title=posting.get("title") or "",
        company=posting.get("company") or "",
        location=posting.get("location") or "",
        description=desc,
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            tools=[TOOL_SPEC],
            tool_choice={"type": "tool", "name": "report_fit"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Haiku call failed for %s/%s: %s", posting.get("source"), posting.get("posting_id"), exc)
        return None

    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "report_fit":
            return dict(block.input)
    log.warning("Haiku returned no tool_use for %s/%s", posting.get("source"), posting.get("posting_id"))
    return None

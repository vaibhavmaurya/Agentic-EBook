"""
Deterministic source quality scorer — no LLM call.

Scores a fetched source on authority, freshness, and content richness.
Returns a float 0.0–1.0.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Domains that typically carry high-authority technical content
_HIGH_AUTHORITY_DOMAINS = {
    "arxiv.org", "wikipedia.org", "github.com", "docs.python.org",
    "developer.mozilla.org", "aws.amazon.com", "cloud.google.com",
    "azure.microsoft.com", "kubernetes.io", "openai.com", "anthropic.com",
    "research.google", "dl.acm.org", "ieee.org", "nature.com",
    "medium.com", "stackoverflow.com", "towardsdatascience.com",
}

_LOW_AUTHORITY_SIGNALS = {
    "pinterest", "instagram", "facebook", "twitter", "reddit",
    "quora", "yahoo", "bing.com", "google.com",
}


def score_source(url: str, text: str, topic_keywords: list[str]) -> float:
    """
    Score a source on a 0.0–1.0 scale.

    Criteria:
      - Domain authority    (0–0.35)
      - Content richness    (0–0.35): length + keyword coverage
      - URL quality signals (0–0.30): HTTPS, no query spam, clean path
    """
    domain = _get_domain(url)

    # ── Domain authority ──────────────────────────────────────────────────────
    authority_score = 0.15  # neutral baseline
    for high in _HIGH_AUTHORITY_DOMAINS:
        if high in domain:
            authority_score = 0.35
            break
    for low in _LOW_AUTHORITY_SIGNALS:
        if low in domain:
            authority_score = 0.05
            break

    # ── Content richness ──────────────────────────────────────────────────────
    word_count = len(text.split())
    # Sigmoid-ish: 500 words → ~0.15, 2000 words → ~0.25, 5000+ → ~0.30
    length_score = min(0.20, word_count / 25_000)

    # Keyword coverage
    text_lower = text.lower()
    matched = sum(1 for kw in topic_keywords if kw.lower() in text_lower)
    coverage = matched / max(len(topic_keywords), 1)
    keyword_score = coverage * 0.15

    richness_score = length_score + keyword_score

    # ── URL quality ───────────────────────────────────────────────────────────
    url_score = 0.10
    if url.startswith("https://"):
        url_score += 0.10
    parsed = urlparse(url)
    # Penalise heavily parametrised URLs
    if len(parsed.query) < 50:
        url_score += 0.10

    return round(min(1.0, authority_score + richness_score + url_score), 3)


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""

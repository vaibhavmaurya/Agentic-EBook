"""
Web search tool — wraps multiple search backends with a priority fallback chain.

Priority: Bing Search API → SerpAPI → DuckDuckGo (no API key, rate-limited)

Configure in model_config.yaml under research_tools.web_search.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def web_search(
    query: str,
    num_results: int = 5,
    bing_api_key: Optional[str] = None,
    serpapi_key: Optional[str] = None,
) -> list[SearchResult]:
    """
    Search the web and return a list of results.

    Tries backends in order: Bing → SerpAPI → DuckDuckGo.
    """
    if bing_api_key:
        try:
            return _bing_search(query, num_results, bing_api_key)
        except Exception:
            pass  # fall through to next backend

    if serpapi_key:
        try:
            return _serpapi_search(query, num_results, serpapi_key)
        except Exception:
            pass

    return _duckduckgo_search(query, num_results)


# ── Bing Search API ───────────────────────────────────────────────────────────

def _bing_search(query: str, num_results: int, api_key: str) -> list[SearchResult]:
    import requests
    resp = requests.get(
        "https://api.bing.microsoft.com/v7.0/search",
        headers={"Ocp-Apim-Subscription-Key": api_key},
        params={"q": query, "count": num_results, "responseFilter": "Webpages"},
        timeout=10,
    )
    resp.raise_for_status()
    pages = resp.json().get("webPages", {}).get("value", [])
    return [
        SearchResult(title=p["name"], url=p["url"], snippet=p.get("snippet", ""))
        for p in pages[:num_results]
    ]


# ── SerpAPI ───────────────────────────────────────────────────────────────────

def _serpapi_search(query: str, num_results: int, api_key: str) -> list[SearchResult]:
    import requests
    resp = requests.get(
        "https://serpapi.com/search",
        params={"q": query, "api_key": api_key, "num": num_results, "engine": "google"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("organic_results", [])
    return [
        SearchResult(title=r["title"], url=r["link"], snippet=r.get("snippet", ""))
        for r in results[:num_results]
    ]


# ── DuckDuckGo (no API key) ───────────────────────────────────────────────────

def _duckduckgo_search(query: str, num_results: int) -> list[SearchResult]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=num_results))
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            )
            for r in raw
        ]
    except ImportError:
        raise RuntimeError(
            "No web search backend available. Install duckduckgo-search or configure "
            "bing_secret_name / serpapi_secret_name in model_config.yaml."
        )

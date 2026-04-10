"""
URL fetcher — retrieves a web page and returns the main text content.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str          # extracted plain text, stripped of HTML
    status_code: int


def fetch_url(
    url: str,
    timeout_sec: int = 15,
    max_content_bytes: int = 512_000,
    user_agent: str = "EbookBot/1.0",
) -> Optional[FetchedPage]:
    """
    Fetch and extract text from a URL. Returns None on failure (404, timeout, etc.).
    """
    try:
        import requests
        from .extract_content import extract_text

        resp = requests.get(
            url,
            headers={"User-Agent": user_agent},
            timeout=timeout_sec,
            stream=True,
        )
        if resp.status_code >= 400:
            return None

        raw = b""
        for chunk in resp.iter_content(chunk_size=8192):
            raw += chunk
            if len(raw) >= max_content_bytes:
                break

        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type and "text" not in content_type:
            return None

        html = raw.decode("utf-8", errors="replace")
        title, text = extract_text(html)

        return FetchedPage(
            url=url,
            title=title,
            text=text,
            status_code=resp.status_code,
        )
    except Exception:
        return None

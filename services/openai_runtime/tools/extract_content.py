"""
HTML → plain text extractor using BeautifulSoup.
"""
from __future__ import annotations

import re


def extract_text(html: str) -> tuple[str, str]:
    """
    Parse HTML and return (title, clean_text).

    Strips scripts, styles, navigation, and boilerplate.
    Returns meaningful paragraph-level content joined by newlines.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback: strip all HTML tags with regex (low quality but no dep)
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return (title.group(1).strip() if title else ""), text[:50_000]

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "noscript", "iframe", "svg"]):
        tag.decompose()

    title = soup.find("title")
    title_text = title.get_text(strip=True) if title else ""

    # Extract meaningful blocks
    blocks: list[str] = []
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "td", "th", "pre", "code"]):
        t = tag.get_text(separator=" ", strip=True)
        if len(t) > 30:   # skip tiny fragments
            blocks.append(t)

    # Fall back to all body text if no blocks found
    if not blocks:
        body = soup.find("body")
        if body:
            blocks = [body.get_text(separator="\n", strip=True)]

    text = "\n".join(blocks)
    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return title_text, text

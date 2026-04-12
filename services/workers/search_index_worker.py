"""
RebuildIndexes — Step Functions worker (stage 14 of 14).

Steps:
  1. Query DynamoDB for all active topics that have a published version
  2. For each topic, read the manifest.json from S3 (content_uri, sections, etc.)
  3. Build a Lunr.js-compatible search index JSON over title + description + content excerpt
  4. Build a table-of-contents (TOC) JSON sorted by topic order
  5. Write both to s3://<bucket>/site/current/search/index.json and .../toc.json
  6. Write a sitemap.json listing all published topic slugs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env.local")
except ImportError:
    pass

from services.workers.base import (
    _S3_BUCKET,
    extract_execution_input,
    get_s3,
    get_s3_json,
    get_table,
)
from shared_types.tracer import stage_completed, stage_started

_STAGE = "RebuildIndexes"
_EXCERPT_CHARS = 500   # characters of content to index per topic


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _list_published_topics() -> list[dict]:
    """Return all active topic META items that have a published version."""
    table = get_table()
    from boto3.dynamodb.conditions import Key, Attr
    resp = table.query(
        IndexName="GSI1-EntityType-OrderKey",
        KeyConditionExpression=Key("ENTITY_TYPE").eq("TOPIC"),
        FilterExpression=Attr("active").eq(True) & Attr("current_published_version").exists(),
    )
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: int(x.get("order", 0)))


def _read_manifest(content_uri: str) -> dict:
    """
    content_uri points to content.md; derive the sibling manifest.json URI.
    Returns {} on any fetch error.
    """
    if not content_uri or not content_uri.startswith("s3://"):
        return {}
    manifest_uri = content_uri.replace("/content.md", "/manifest.json")
    try:
        return get_s3_json(manifest_uri)
    except Exception:
        return {}


def _content_excerpt(content_uri: str) -> str:
    """Fetch the first _EXCERPT_CHARS of the Markdown content for indexing."""
    if not content_uri or not content_uri.startswith("s3://"):
        return ""
    try:
        rest = content_uri[5:]
        bucket, key = rest.split("/", 1)
        resp = get_s3().get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{_EXCERPT_CHARS * 2}")
        raw = resp["Body"].read().decode("utf-8", errors="replace")
        # Strip Markdown headings/symbols for cleaner search text
        text = re.sub(r"#+ ", "", raw)
        text = re.sub(r"[*_`\[\]()>]", "", text)
        return text[:_EXCERPT_CHARS].replace("\n", " ").strip()
    except Exception:
        return ""


def _write_site_file(key: str, data: Any) -> str:
    get_s3().put_object(
        Bucket=_S3_BUCKET,
        Key=key,
        Body=json.dumps(data, default=str).encode(),
        ContentType="application/json",
    )
    return f"s3://{_S3_BUCKET}/{key}"


def rebuild_indexes(topic_id: str, run_id: str) -> dict:
    stage_started(run_id, _STAGE)

    topics = _list_published_topics()
    now = datetime.now(timezone.utc).isoformat()

    # ── Build Lunr.js documents list ──────────────────────────────────────────
    # Lunr expects: { id, title, body }
    # The public site loads this JSON and builds the in-browser index from it.
    lunr_docs = []
    toc_entries = []

    for topic in topics:
        tid = topic.get("topic_id") or topic.get("PK", "").replace("TOPIC#", "")
        title = topic.get("title", "")
        description = topic.get("description", "")
        content_uri = topic.get("content_uri", "")
        version = topic.get("current_published_version", "")
        published_at = topic.get("published_at", "")
        order = int(topic.get("order", 0))

        manifest = _read_manifest(content_uri)
        sections = manifest.get("sections", topic.get("sections", []))
        release_notes = manifest.get("diff", {}).get("release_notes", "")
        word_count = manifest.get("word_count", 0)
        excerpt = _content_excerpt(content_uri)
        slug = _slugify(title) or tid

        lunr_docs.append({
            "id": tid,
            "slug": slug,
            "title": title,
            "body": f"{description} {excerpt}",
            "sections": sections,
        })

        toc_entries.append({
            "topic_id": tid,
            "slug": slug,
            "title": title,
            "description": description,
            "order": order,
            "version": version,
            "published_at": published_at,
            "word_count": word_count,
            "section_count": len(sections),
            "release_notes": release_notes,
        })

    # ── Write search/index.json ───────────────────────────────────────────────
    search_payload = {
        "generated_at": now,
        "topic_count": len(lunr_docs),
        "documents": lunr_docs,
    }
    index_uri = _write_site_file("site/current/search/index.json", search_payload)

    # ── Write toc.json ────────────────────────────────────────────────────────
    toc_payload = {
        "generated_at": now,
        "topic_count": len(toc_entries),
        "topics": toc_entries,
    }
    toc_uri = _write_site_file("site/current/toc.json", toc_payload)

    # ── Write sitemap.json ────────────────────────────────────────────────────
    sitemap = {
        "generated_at": now,
        "topics": [{"slug": e["slug"], "topic_id": e["topic_id"]} for e in toc_entries],
    }
    sitemap_uri = _write_site_file("site/current/sitemap.json", sitemap)

    # No Amplify rebuild needed — public site fetches content from API at runtime.

    stage_completed(
        run_id, _STAGE,
        index_uri=index_uri,
        toc_uri=toc_uri,
        topic_count=len(lunr_docs),
    )
    return {
        "topic_id": topic_id,
        "run_id": run_id,
        "index_uri": index_uri,
        "toc_uri": toc_uri,
        "sitemap_uri": sitemap_uri,
        "topic_count": len(lunr_docs),
    }


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    return rebuild_indexes(inp["topic_id"], inp["run_id"])


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild_indexes(args.topic_id, args.run_id), indent=2))


if __name__ == "__main__":
    _cli()

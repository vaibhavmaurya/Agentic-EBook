"""
PublishTopic — Step Functions worker (stage 13 of 14).

Steps:
  1. Determine the next published version number (v001, v002, …)
  2. Copy final_draft content from review/ → published/topics/<id>/v<NNN>/
  3. Write a manifest.json alongside the content (sections, word_count, release_notes, etc.)
  4. Write TOPIC#<id> | PUBLISHED#v<NNN> DDB record
  5. Update TOPIC#<id> | META with current_published_version + published_at + content_uri
"""
from __future__ import annotations

import argparse
import json
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
    get_topic_meta,
)
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "PublishTopic"


def _next_version(topic_id: str) -> str:
    """Return the next version string: v001, v002, …"""
    table = get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={
            ":pk": f"TOPIC#{topic_id}",
            ":prefix": "PUBLISHED#",
        },
    )
    existing = len(resp.get("Items", []))
    return f"v{existing + 1:03d}"


def _copy_markdown(topic_id: str, version: str, content: str) -> str:
    """Write content.md to the published prefix and return its s3:// URI."""
    key = f"published/topics/{topic_id}/{version}/content.md"
    get_s3().put_object(
        Bucket=_S3_BUCKET,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )
    return f"s3://{_S3_BUCKET}/{key}"


def publish_topic(
    topic_id: str,
    run_id: str,
    review_artifact_uri: str | None = None,
    diff_summary_uri: str | None = None,
) -> dict:
    stage_started(run_id, _STAGE)

    if not review_artifact_uri:
        err = "review_artifact_uri is required for PublishTopic."
        stage_failed(run_id, _STAGE, err, "MISSING_INPUT")
        raise ValueError(err)

    artifact = get_s3_json(review_artifact_uri)
    diff = get_s3_json(diff_summary_uri) if diff_summary_uri else {}

    topic = get_topic_meta(topic_id)
    title = topic["title"] if topic else artifact.get("title", topic_id)

    version = _next_version(topic_id)
    now = datetime.now(timezone.utc).isoformat()

    content = artifact.get("content", "")
    sections = artifact.get("sections", [])
    word_count = artifact.get("word_count", 0)
    scorecard = artifact.get("scorecard", {})

    # ── 1. Write content.md to published prefix ───────────────────────────────
    content_uri = _copy_markdown(topic_id, version, content)

    # ── 2. Write manifest.json alongside the content ──────────────────────────
    manifest = {
        "topic_id": topic_id,
        "run_id": run_id,
        "version": version,
        "title": title,
        "published_at": now,
        "content_uri": content_uri,
        "sections": sections,
        "word_count": word_count,
        "scorecard": scorecard,
        "diff": {
            "is_first_version": diff.get("is_first_version", True),
            "release_notes": diff.get("release_notes", ""),
            "sections_added": diff.get("sections_added", []),
            "sections_removed": diff.get("sections_removed", []),
            "sections_changed": diff.get("sections_changed", []),
        },
    }
    manifest_key = f"published/topics/{topic_id}/{version}/manifest.json"
    get_s3().put_object(
        Bucket=_S3_BUCKET,
        Key=manifest_key,
        Body=json.dumps(manifest, default=str).encode(),
        ContentType="application/json",
    )
    manifest_uri = f"s3://{_S3_BUCKET}/{manifest_key}"

    # ── 3. Write PUBLISHED# DDB record ────────────────────────────────────────
    table = get_table()
    table.put_item(Item={
        "PK": f"TOPIC#{topic_id}",
        "SK": f"PUBLISHED#{version}",
        "ENTITY_TYPE": "PUBLISHED_VERSION",
        "topic_id": topic_id,
        "run_id": run_id,
        "version": version,
        "title": title,
        "content_uri": content_uri,
        "manifest_uri": manifest_uri,
        "word_count": word_count,
        "release_notes": diff.get("release_notes", ""),
        "published_at": now,
        "UPDATED_AT": now,
    })

    # ── 4. Update META with current published version ─────────────────────────
    table.update_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": "META"},
        UpdateExpression=(
            "SET current_published_version = :ver, "
            "published_at = :now, "
            "content_uri = :curi, "
            "UPDATED_AT = :now"
        ),
        ExpressionAttributeValues={
            ":ver": version,
            ":now": now,
            ":curi": content_uri,
        },
    )

    stage_completed(
        run_id, _STAGE,
        published_version=version,
        word_count=word_count,
        content_uri=content_uri,
    )
    return {
        "topic_id": topic_id,
        "run_id": run_id,
        "published_version": version,
        "content_uri": content_uri,
        "manifest_uri": manifest_uri,
    }


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    build = event.get("build_result", {}).get("body", {})
    diff = event.get("diff_result", {}).get("body", {})
    return publish_topic(
        inp["topic_id"], inp["run_id"],
        review_artifact_uri=build.get("review_artifact_uri"),
        diff_summary_uri=diff.get("diff_summary_uri"),
    )


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--review-artifact-uri", required=True)
    parser.add_argument("--diff-summary-uri")
    args = parser.parse_args()
    print(json.dumps(
        publish_topic(
            args.topic_id, args.run_id,
            review_artifact_uri=args.review_artifact_uri,
            diff_summary_uri=args.diff_summary_uri,
        ), indent=2
    ))


if __name__ == "__main__":
    _cli()

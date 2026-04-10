"""
GenerateDiffAndReleaseNotes — Step Functions worker (stage 10 of 14).

Fetches the prior published version from S3 (if any) and calls
run_diff_agent() to produce release notes and a section-level change summary.
"""
from __future__ import annotations

import argparse
import json
import sys
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
    extract_execution_input,
    get_s3_json,
    get_table,
    get_topic_meta,
    put_s3_json,
)
from services.openai_runtime import run_diff_agent
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "GenerateDiffAndReleaseNotes"


def _get_prior_published_content(topic_id: str) -> str | None:
    """
    Read the latest published version's Markdown from S3.
    Returns None if no version has been published yet.
    """
    table = get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={":pk": f"TOPIC#{topic_id}", ":prefix": "PUBLISHED#"},
        ScanIndexForward=False,  # descending — most recent first
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return None

    latest = items[0]
    content_uri = latest.get("content_uri")
    if not content_uri:
        return None

    try:
        artifact = get_s3_json(content_uri)
        return artifact.get("content")
    except Exception:
        return None


def generate_diff(topic_id: str, run_id: str,
                  context_uri: str | None = None,
                  final_draft_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE, agent_name="diff")

    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        topic_context = {"topic_id": topic_id, "run_id": run_id,
                         "title": topic["title"], "description": topic["description"],
                         "instructions": topic["instructions"]}

    if not final_draft_uri:
        err = "final_draft_uri is required for GenerateDiffAndReleaseNotes."
        stage_failed(run_id, _STAGE, err, "MISSING_INPUT")
        raise ValueError(err)

    final_draft = get_s3_json(final_draft_uri)
    prior_content = _get_prior_published_content(topic_id)

    diff_summary = run_diff_agent(topic_context, final_draft, prior_content)
    meta = diff_summary.pop("_meta", {})

    diff_summary_uri = put_s3_json(topic_id, run_id, "diff", "diff_summary.json", diff_summary)

    stage_completed(
        run_id, _STAGE,
        agent_name="diff",
        model_name=meta.get("model"),
        cost_usd=_cost(meta),
        is_first_version=diff_summary.get("is_first_version", True),
    )
    return {"topic_id": topic_id, "run_id": run_id,
            "diff_summary_uri": diff_summary_uri,
            "is_first_version": diff_summary.get("is_first_version", True),
            "release_notes": diff_summary.get("release_notes", "")}


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    ctx = event.get("context_result", {}).get("body", {})
    editorial = event.get("editorial_result", {}).get("body", {})
    return generate_diff(inp["topic_id"], inp["run_id"],
                         ctx.get("context_uri"), editorial.get("final_draft_uri"))


def _cost(meta: dict) -> float:
    from services.openai_runtime.config import estimate_cost_usd
    return estimate_cost_usd("diff", meta.get("input_tokens", 0), meta.get("output_tokens", 0))


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--final-draft-uri", required=True)
    args = parser.parse_args()
    print(json.dumps(generate_diff(args.topic_id, args.run_id,
                                   final_draft_uri=args.final_draft_uri), indent=2))


if __name__ == "__main__":
    _cli()

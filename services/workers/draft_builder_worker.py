"""
BuildDraftArtifact — Step Functions worker (stage 9 of 14).

Assembles the admin review artifact from the final edited draft:
  - Writes review/review_artifact.json  (content + metadata + scorecard)
  - Writes review/preview.md            (plain Markdown for quick reading)

No LLM call — pure data assembly and S3 writes.
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
    extract_execution_input,
    get_s3_json,
    get_topic_meta,
    put_s3_json,
)
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "BuildDraftArtifact"


def build_draft_artifact(
    topic_id: str,
    run_id: str,
    context_uri: str | None = None,
    final_draft_uri: str | None = None,
    scorecard_uri: str | None = None,
    diff_summary_uri: str | None = None,
) -> dict:
    stage_started(run_id, _STAGE)

    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        topic_context = {
            "topic_id": topic_id,
            "run_id": run_id,
            "title": topic["title"],
            "description": topic["description"],
        }

    if not final_draft_uri:
        err = "final_draft_uri is required for BuildDraftArtifact."
        stage_failed(run_id, _STAGE, err, "MISSING_INPUT")
        raise ValueError(err)

    final_draft = get_s3_json(final_draft_uri)
    scorecard = get_s3_json(scorecard_uri) if scorecard_uri else {}
    diff_summary = get_s3_json(diff_summary_uri) if diff_summary_uri else {}

    # Assemble the structured review artifact consumed by the Admin UI
    review_artifact = {
        "topic_id": topic_id,
        "run_id": run_id,
        "title": topic_context.get("title", ""),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "content": final_draft.get("content", ""),
        "sections": final_draft.get("sections", []),
        "word_count": final_draft.get("word_count", 0),
        "scorecard": scorecard.get("scorecard", {}),
        "changes_summary": scorecard.get("changes_summary", ""),
        "diff_summary": {
            "is_first_version": diff_summary.get("is_first_version", True),
            "sections_added": diff_summary.get("sections_added", []),
            "sections_removed": diff_summary.get("sections_removed", []),
            "sections_changed": diff_summary.get("sections_changed", []),
            "release_notes": diff_summary.get("release_notes", ""),
        },
    }

    review_artifact_uri = put_s3_json(
        topic_id, run_id, "review", "review_artifact.json", review_artifact
    )

    # Plain Markdown copy for quick reading in the UI or email
    preview_key = f"topics/{topic_id}/runs/{run_id}/review/preview.md"
    from services.workers.base import get_s3, _S3_BUCKET
    get_s3().put_object(
        Bucket=_S3_BUCKET,
        Key=preview_key,
        Body=final_draft.get("content", "").encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )
    preview_uri = f"s3://{_S3_BUCKET}/{preview_key}"

    stage_completed(run_id, _STAGE,
                    review_artifact_uri=review_artifact_uri,
                    preview_uri=preview_uri)
    return {
        "topic_id": topic_id,
        "run_id": run_id,
        "review_artifact_uri": review_artifact_uri,
        "preview_uri": preview_uri,
    }


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    ctx = event.get("context_result", {}).get("body", {})
    editorial = event.get("editorial_result", {}).get("body", {})
    diff = event.get("diff_result", {}).get("body", {})
    return build_draft_artifact(
        inp["topic_id"], inp["run_id"],
        context_uri=ctx.get("context_uri"),
        final_draft_uri=editorial.get("final_draft_uri"),
        scorecard_uri=editorial.get("scorecard_uri"),
        diff_summary_uri=diff.get("diff_summary_uri"),
    )


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--final-draft-uri", required=True)
    parser.add_argument("--scorecard-uri")
    parser.add_argument("--diff-summary-uri")
    args = parser.parse_args()
    print(json.dumps(
        build_draft_artifact(
            args.topic_id, args.run_id,
            final_draft_uri=args.final_draft_uri,
            scorecard_uri=args.scorecard_uri,
            diff_summary_uri=args.diff_summary_uri,
        ), indent=2
    ))


if __name__ == "__main__":
    _cli()

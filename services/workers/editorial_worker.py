"""
EditorialReview — Step Functions worker (stage 8 of 14).
Calls run_editor_agent() using the low_capability model.
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

from services.workers.base import extract_execution_input, get_s3_json, get_topic_meta, put_s3_json
from services.openai_runtime import run_editor_agent
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "EditorialReview"


def editorial_review(topic_id: str, run_id: str,
                     context_uri: str | None = None, draft_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE, agent_name="editor")

    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        topic_context = {"topic_id": topic_id, "run_id": run_id,
                         "title": topic["title"], "description": topic["description"],
                         "instructions": topic["instructions"],
                         "subtopics": topic.get("subtopics", [])}

    if not draft_uri:
        err = "draft_uri is required for EditorialReview."
        stage_failed(run_id, _STAGE, err, "MISSING_INPUT")
        raise ValueError(err)

    draft_content = get_s3_json(draft_uri)
    final = run_editor_agent(topic_context, draft_content)
    meta = final.pop("_meta", {})

    final_draft_uri = put_s3_json(topic_id, run_id, "review", "final_draft.md",
                                   {"content": final["content"],
                                    "sections": draft_content.get("sections", []),
                                    "word_count": final["word_count"]})
    scorecard_uri = put_s3_json(topic_id, run_id, "review", "scorecard.json",
                                 {"scorecard": final["scorecard"],
                                  "changes_summary": final["changes_summary"]})

    stage_completed(
        run_id, _STAGE,
        agent_name="editor",
        model_name=meta.get("model"),
        cost_usd=_cost(meta),
        overall_score=final["scorecard"].get("overall"),
    )
    return {"topic_id": topic_id, "run_id": run_id,
            "final_draft_uri": final_draft_uri,
            "scorecard_uri": scorecard_uri,
            "scorecard": final["scorecard"],
            "word_count": final.get("word_count")}


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    ctx = event.get("context_result", {}).get("body", {})
    draft = event.get("draft_result", {}).get("body", {})
    return editorial_review(inp["topic_id"], inp["run_id"],
                            ctx.get("context_uri"), draft.get("draft_uri"))


def _cost(meta: dict) -> float:
    from services.openai_runtime.config import estimate_cost_usd
    return estimate_cost_usd("editor", meta.get("input_tokens", 0), meta.get("output_tokens", 0))


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--draft-uri", required=True)
    args = parser.parse_args()
    print(json.dumps(editorial_review(args.topic_id, args.run_id,
                                      draft_uri=args.draft_uri), indent=2))


if __name__ == "__main__":
    _cli()

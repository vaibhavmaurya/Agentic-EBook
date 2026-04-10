"""
DraftChapter — Step Functions worker (stage 7 of 14).
Calls run_writer_agent() using the high_capability model.
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
from services.openai_runtime import run_writer_agent
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "DraftChapter"


def draft_chapter(topic_id: str, run_id: str,
                  context_uri: str | None = None, verified_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE, agent_name="writer")

    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        topic_context = {"topic_id": topic_id, "run_id": run_id,
                         "title": topic["title"], "description": topic["description"],
                         "instructions": topic["instructions"],
                         "subtopics": topic.get("subtopics", [])}

    if not verified_uri:
        err = "verified_uri is required for DraftChapter."
        stage_failed(run_id, _STAGE, err, "MISSING_INPUT")
        raise ValueError(err)

    validated_evidence = get_s3_json(verified_uri)
    draft = run_writer_agent(topic_context, validated_evidence)
    meta = draft.pop("_meta", {})
    draft_uri = put_s3_json(topic_id, run_id, "draft", "draft.md",
                             {"content": draft["content"], "sections": draft["sections"],
                              "word_count": draft["word_count"]})

    stage_completed(
        run_id, _STAGE,
        agent_name="writer",
        model_name=meta.get("model"),
        cost_usd=_cost(meta),
        word_count=draft.get("word_count"),
    )
    return {"topic_id": topic_id, "run_id": run_id, "draft_uri": draft_uri,
            "word_count": draft.get("word_count")}


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    ctx = event.get("context_result", {}).get("body", {})
    persist = event.get("persist_result", {}).get("body", {})
    verify = event.get("verify_result", {}).get("body", {})
    verified_uri = persist.get("verified_uri") or verify.get("verified_uri")
    return draft_chapter(inp["topic_id"], inp["run_id"], ctx.get("context_uri"), verified_uri)


def _cost(meta: dict) -> float:
    from services.openai_runtime.config import estimate_cost_usd
    return estimate_cost_usd("writer", meta.get("input_tokens", 0), meta.get("output_tokens", 0))


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--verified-uri", required=True)
    args = parser.parse_args()
    print(json.dumps(draft_chapter(args.topic_id, args.run_id, verified_uri=args.verified_uri), indent=2))


if __name__ == "__main__":
    _cli()

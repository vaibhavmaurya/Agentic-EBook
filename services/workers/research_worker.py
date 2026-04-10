"""
ResearchTopic — Step Functions worker (stage 4 of 14).
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
from services.openai_runtime import run_research_agent
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "ResearchTopic"


def research_topic(topic_id: str, run_id: str, context_uri: str | None = None, plan_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE, agent_name="research")

    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        topic_context = {
            "topic_id": topic_id, "run_id": run_id,
            "title": topic["title"], "description": topic["description"],
            "instructions": topic["instructions"], "subtopics": topic.get("subtopics", []),
        }

    if plan_uri:
        research_plan = get_s3_json(plan_uri)
    else:
        research_plan = {"search_queries": [topic_context["title"]], "key_questions": []}

    evidence = run_research_agent(topic_context, research_plan)
    meta = evidence.pop("_meta", {})
    evidence_uri = put_s3_json(topic_id, run_id, "raw", "evidence.json", evidence)

    stage_completed(
        run_id, _STAGE,
        agent_name="research",
        model_name=meta.get("model"),
        cost_usd=_cost(meta),
        sources_found=evidence.get("total_sources", 0),
    )
    return {"topic_id": topic_id, "run_id": run_id, "evidence_uri": evidence_uri}


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    ctx = event.get("context_result", {}).get("body", {})
    plan = event.get("plan_result", {}).get("body", {})
    return research_topic(inp["topic_id"], inp["run_id"],
                          ctx.get("context_uri"), plan.get("plan_uri"))


def _cost(meta: dict) -> float:
    from services.openai_runtime.config import estimate_cost_usd
    return estimate_cost_usd("research", meta.get("input_tokens", 0), meta.get("output_tokens", 0))


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(research_topic(args.topic_id, args.run_id), indent=2))


if __name__ == "__main__":
    _cli()

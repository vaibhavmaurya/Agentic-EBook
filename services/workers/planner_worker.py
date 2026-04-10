"""
PlanTopic — Step Functions worker (stage 3 of 14).

Calls openai_runtime.run_planner_agent() and writes the research plan to S3.
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
from services.openai_runtime import run_planner_agent
from shared_types.models import utc_now
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "PlanTopic"


def plan_topic(topic_id: str, run_id: str, context_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE, agent_name="planner")

    # Load topic context — from S3 if URI provided, else rebuild from DDB
    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        if not topic:
            err = f"Topic {topic_id} not found."
            stage_failed(run_id, _STAGE, err, "TOPIC_NOT_FOUND")
            raise ValueError(err)
        topic_context = {
            "topic_id": topic_id,
            "run_id": run_id,
            "title": topic["title"],
            "description": topic["description"],
            "instructions": topic["instructions"],
            "subtopics": topic.get("subtopics", []),
        }

    plan = run_planner_agent(topic_context)
    meta = plan.pop("_meta", {})
    plan_uri = put_s3_json(topic_id, run_id, "plan", "research_plan.json", plan)

    stage_completed(
        run_id, _STAGE,
        agent_name="planner",
        model_name=meta.get("model"),
        cost_usd=_cost(meta),
    )
    return {"topic_id": topic_id, "run_id": run_id, "plan_uri": plan_uri}


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    # context_uri is set by AssembleTopicContext via ResultPath in SFN state
    context_result = event.get("context_result", {}).get("body", {})
    context_uri = context_result.get("context_uri")
    return plan_topic(inp["topic_id"], inp["run_id"], context_uri)


def _cost(meta: dict) -> float:
    from services.openai_runtime.config import estimate_cost_usd
    return estimate_cost_usd("planner", meta.get("input_tokens", 0), meta.get("output_tokens", 0))


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(plan_topic(args.topic_id, args.run_id), indent=2))


if __name__ == "__main__":
    _cli()

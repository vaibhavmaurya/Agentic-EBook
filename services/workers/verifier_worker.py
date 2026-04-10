"""
VerifyEvidence — Step Functions worker (stage 5 of 14).
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
from services.openai_runtime import run_verifier_agent
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "VerifyEvidence"


def verify_evidence(topic_id: str, run_id: str,
                    context_uri: str | None = None, evidence_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE, agent_name="verifier")

    if context_uri:
        topic_context = get_s3_json(context_uri)
    else:
        topic = get_topic_meta(topic_id)
        topic_context = {"topic_id": topic_id, "run_id": run_id,
                         "title": topic["title"], "description": topic["description"],
                         "instructions": topic["instructions"]}

    if not evidence_uri:
        err = "evidence_uri is required for VerifyEvidence."
        stage_failed(run_id, _STAGE, err, "MISSING_INPUT")
        raise ValueError(err)

    evidence_set = get_s3_json(evidence_uri)

    validated = run_verifier_agent(topic_context, evidence_set)
    meta = validated.pop("_meta", {})
    verified_uri = put_s3_json(topic_id, run_id, "verified", "validated_evidence.json", validated)

    stage_completed(
        run_id, _STAGE,
        agent_name="verifier",
        model_name=meta.get("model"),
        cost_usd=_cost(meta),
        quality_score=validated.get("quality_score"),
    )
    return {"topic_id": topic_id, "run_id": run_id, "verified_uri": verified_uri,
            "quality_score": validated.get("quality_score")}


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    ctx = event.get("context_result", {}).get("body", {})
    research = event.get("research_result", {}).get("body", {})
    return verify_evidence(inp["topic_id"], inp["run_id"],
                           ctx.get("context_uri"), research.get("evidence_uri"))


def _cost(meta: dict) -> float:
    from services.openai_runtime.config import estimate_cost_usd
    return estimate_cost_usd("verifier", meta.get("input_tokens", 0), meta.get("output_tokens", 0))


def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-uri", required=True)
    args = parser.parse_args()
    print(json.dumps(verify_evidence(args.topic_id, args.run_id, evidence_uri=args.evidence_uri), indent=2))


if __name__ == "__main__":
    _cli()

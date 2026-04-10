"""
AssembleTopicContext — Step Functions worker (stage 2 of 14).

Responsibility:
  - Read topic config from DynamoDB (topic_id comes from execution input)
  - Read the prior published version (if any) for diff context
  - Assemble the full topic context object
  - Write context.json to S3 under topics/<id>/runs/<run_id>/context/
  - Return the S3 URI so downstream workers can load it

Returns (becomes $.context_result.body in SFN state):
    {
        "topic_id": str,
        "run_id": str,
        "context_uri": "s3://...",
    }
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
    get_topic_meta,
    put_s3_json,
    set_run_status,
)
from shared_types.models import RunStatus
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "AssembleTopicContext"


def assemble_topic_context(topic_id: str, run_id: str) -> dict:
    stage_started(run_id, _STAGE)

    topic = get_topic_meta(topic_id)
    if not topic:
        err = f"Topic {topic_id} not found."
        stage_failed(run_id, _STAGE, err, "TOPIC_NOT_FOUND")
        raise ValueError(err)

    context = {
        "topic_id": topic_id,
        "run_id": run_id,
        "title": topic["title"],
        "description": topic["description"],
        "instructions": topic["instructions"],
        "subtopics": topic.get("subtopics", []),
        "prior_published_version": topic.get("current_published_version"),
    }

    context_uri = put_s3_json(topic_id, run_id, "context", "context.json", context)

    stage_completed(run_id, _STAGE, context_uri=context_uri)
    return {
        "topic_id": topic_id,
        "run_id": run_id,
        "context_uri": context_uri,
    }


def handler(event: dict, context: Any) -> dict:
    inp = extract_execution_input(event)
    return assemble_topic_context(inp["topic_id"], inp["run_id"])


def _cli():
    parser = argparse.ArgumentParser(description="Run AssembleTopicContext worker locally")
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    result = assemble_topic_context(args.topic_id, args.run_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()

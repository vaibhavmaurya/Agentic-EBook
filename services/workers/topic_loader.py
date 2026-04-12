"""
LoadTopicConfig — Step Functions worker (stage 1 of 14).

Responsibility:
  - Verify the topic exists and is active
  - Update the RUN record status from PENDING → RUNNING
  - Write STAGE_STARTED / STAGE_COMPLETED trace events
  - Return the topic configuration dict so downstream workers can reference it

Returns (becomes $.loader_result.body in SFN state):
    {
        "topic_id": str,
        "run_id": str,
        "title": str,
        "description": str,
        "instructions": str,
        "subtopics": list[str],
        "trigger_source": str,
        "triggered_by": str,
    }

Usage (isolated local test):
    python services/workers/topic_loader.py --topic-id <id> --run-id <id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ── Path setup for local execution ───────────────────────────────────────────
# When run directly (python services/workers/topic_loader.py), the repo root
# is two levels up.  We need it on sys.path so shared_types can be imported.
_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load .env.local if present (only applies when running directly, not in Lambda)
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env.local")
except ImportError:
    pass

from services.workers.base import (
    extract_execution_input,
    get_topic_meta,
    set_run_status,
)
from shared_types.models import RunStatus, utc_now
from shared_types.tracer import stage_completed, stage_failed, stage_started

_STAGE = "LoadTopicConfig"


# ── Core logic ────────────────────────────────────────────────────────────────

def load_topic_config(topic_id: str, run_id: str, trigger_source: str, triggered_by: str) -> dict:
    """
    Fetch topic config and transition run status to RUNNING.

    Raises:
        ValueError: if the topic is not found or is inactive
    """
    stage_started(run_id, _STAGE)

    topic = get_topic_meta(topic_id)
    if not topic:
        err = f"Topic {topic_id} not found in DynamoDB."
        stage_failed(run_id, _STAGE, err, "TOPIC_NOT_FOUND")
        raise ValueError(err)

    if not topic.get("active", True):
        err = f"Topic {topic_id} is inactive (soft-deleted)."
        stage_failed(run_id, _STAGE, err, "TOPIC_INACTIVE")
        raise ValueError(err)

    # Transition run status → RUNNING (also set started_at if not already set by trigger API)
    from services.workers.base import get_table, utc_now as _utc_now
    _now = _utc_now()
    run_rec = get_table().get_item(Key={"PK": f"TOPIC#{topic_id}", "SK": f"RUN#{run_id}"}).get("Item", {})
    extra = {} if run_rec.get("started_at") else {"started_at": _now}
    set_run_status(topic_id, run_id, RunStatus.RUNNING, **extra)

    result = {
        "topic_id": topic_id,
        "run_id": run_id,
        "title": topic["title"],
        "description": topic["description"],
        "instructions": topic["instructions"],
        "subtopics": topic.get("subtopics", []),
        "trigger_source": trigger_source,
        "triggered_by": triggered_by,
    }

    stage_completed(run_id, _STAGE)
    return result


# ── Lambda entry point ────────────────────────────────────────────────────────

def handler(event: dict, context: Any) -> dict:
    inp = extract_execution_input(event)
    topic_id: str = inp["topic_id"]
    run_id: str = inp["run_id"]
    trigger_source: str = inp.get("trigger_source", "admin_manual")
    triggered_by: str = inp.get("triggered_by", "unknown")

    return load_topic_config(topic_id, run_id, trigger_source, triggered_by)


# ── Local CLI ─────────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(description="Run LoadTopicConfig worker locally")
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trigger-source", default="admin_manual")
    parser.add_argument("--triggered-by", default="local-dev")
    args = parser.parse_args()

    result = load_topic_config(
        topic_id=args.topic_id,
        run_id=args.run_id,
        trigger_source=args.trigger_source,
        triggered_by=args.triggered_by,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()

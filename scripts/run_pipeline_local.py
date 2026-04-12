#!/usr/bin/env python
"""
Local pipeline runner — mimics the Step Functions state machine locally.

Calls each worker handler in sequence, passing the accumulated state as input
(exactly what the state machine does with "Payload.$": "$").

Usage:
    python scripts/run_pipeline_local.py --topic-id <id> --run-id <id>
    python scripts/run_pipeline_local.py --topic-id <id>          # auto run_id
    python scripts/run_pipeline_local.py --create-topic           # create + run

Run from repo root with venv activated:
    source .venv/Scripts/activate
    python scripts/run_pipeline_local.py --create-topic
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Add repo root to path so workers can import their deps
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Load .env.local
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env.local")
except ImportError:
    pass

import boto3
from boto3.dynamodb.conditions import Key


# ── helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    import datetime
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, handler_fn, state: dict) -> dict:
    """Call a worker handler with the current state and merge result back in."""
    log(f">> {name}...")
    try:
        result = handler_fn(state, None)
        state[f"{_stage_key(name)}"] = {"body": result}
        log(f"  OK {name} -> {json.dumps(result)[:200]}")
        return state
    except Exception as e:
        log(f"  FAIL {name} FAILED: {e}")
        raise


def _stage_key(stage_name: str) -> str:
    """Map stage name → state key (matches SFN ResultPath)."""
    return {
        "LoadTopicConfig":           "loader_result",
        "AssembleTopicContext":      "context_result",
        "PlanTopic":                 "plan_result",
        "ResearchTopic":             "research_result",
        "VerifyEvidence":            "verify_result",
        "PersistEvidenceArtifacts":  "persist_result",
        "DraftChapter":              "draft_result",
        "EditorialReview":           "editorial_result",
        "BuildDraftArtifact":        "build_result",
        "GenerateDiffAndReleaseNotes": "diff_result",
        "NotifyAdminForReview":      "notify_result",
        "PublishTopic":              "publish_result",
        "RebuildIndexes":            "index_result",
    }[stage_name]


def create_topic_and_run() -> tuple[str, str]:
    """Create a test topic in DynamoDB and return (topic_id, run_id)."""
    import os, datetime
    from services.api.topics import lambda_handler as topics_handler

    topic_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    payload = {
        "title": "Agentic AI Architecture and Design Pattern",
        "description": "What is Agent in the Agentic AI. What are the components. What are the most popular design patterns for an Agent.",
        "instructions": (
            "Start with a clear overview of what an Agentic AI system is. "
            "Present key components in tabular format: name, role, brief description. "
            "Include a conceptual block diagram description. "
            "Describe at least 3 common design patterns: ReAct, Plan-and-Execute, Reflection. "
            "Use sequence diagrams (text) to show agent-tool interaction. "
            "Keep language clear for intermediate developers."
        ),
        "subtopics": [
            "What is an Agent",
            "Key Components",
            "Design Patterns",
            "ReAct Pattern",
            "Plan and Execute",
            "Reflection Pattern",
        ],
        "schedule_type": "manual",
        "cron_expression": None,
    }

    event = {
        "requestContext": {"http": {"method": "POST"}},
        "rawPath": "/admin/topics",
        "body": json.dumps(payload),
        "headers": {"content-type": "application/json"},
    }
    resp = topics_handler(event, None)
    body = json.loads(resp["body"])
    created_id = body.get("topic_id", topic_id)
    log(f"Topic created: {created_id}")

    # Create run record in DynamoDB
    import os
    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
    region = os.environ.get("AWS_REGION", "us-east-1")
    now = datetime.datetime.utcnow().isoformat() + "Z"
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    table.put_item(Item={
        "PK": f"TOPIC#{created_id}",
        "SK": f"RUN#{run_id}",
        "ENTITY_TYPE": "RUN",
        "topic_id": created_id,
        "run_id": run_id,
        "status": "RUNNING",
        "trigger_source": "local_test",
        "triggered_by": "run_pipeline_local.py",
        "started_at": now,
        "updated_at": now,
    })
    log(f"Run record created: {run_id}")
    return created_id, run_id


# ── import workers ────────────────────────────────────────────────────────────

def import_workers():
    from services.workers import topic_loader
    from services.workers import topic_context_builder
    from services.workers import planner_worker
    from services.workers import research_worker
    from services.workers import verifier_worker
    from services.workers import artifact_persister
    from services.workers import draft_worker
    from services.workers import editorial_worker
    from services.workers import draft_builder_worker
    from services.workers import diff_worker
    from services.workers import approval_worker
    from services.workers import publish_worker
    from services.workers import search_index_worker
    return {
        "LoadTopicConfig":             topic_loader.handler,
        "AssembleTopicContext":        topic_context_builder.handler,
        "PlanTopic":                   planner_worker.handler,
        "ResearchTopic":               research_worker.handler,
        "VerifyEvidence":              verifier_worker.handler,
        "PersistEvidenceArtifacts":    artifact_persister.handler,
        "DraftChapter":                draft_worker.handler,
        "EditorialReview":             editorial_worker.handler,
        "BuildDraftArtifact":          draft_builder_worker.handler,
        "GenerateDiffAndReleaseNotes": diff_worker.handler,
        "NotifyAdminForReview":        approval_worker.handler,
        "PublishTopic":                publish_worker.handler,
        "RebuildIndexes":              search_index_worker.handler,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run pipeline locally without Step Functions.")
    parser.add_argument("--topic-id", help="Existing topic ID")
    parser.add_argument("--run-id", help="Run ID (auto-generated if omitted)")
    parser.add_argument("--create-topic", action="store_true", help="Create a test topic first")
    parser.add_argument("--stop-before", help="Stop before this stage (for partial runs)")
    parser.add_argument("--start-from", help="Skip stages before this one (state rebuilt by re-running prior stages silently)")
    parser.add_argument("--auto-approve", action="store_true", help="Automatically approve the draft and run PublishTopic + RebuildIndexes")
    args = parser.parse_args()

    if args.create_topic:
        topic_id, run_id = create_topic_and_run()
    else:
        if not args.topic_id:
            print("ERROR: provide --topic-id or use --create-topic")
            sys.exit(1)
        topic_id = args.topic_id
        run_id = args.run_id or str(uuid.uuid4())

    log(f"\nStarting local pipeline")
    log(f"  topic_id = {topic_id}")
    log(f"  run_id   = {run_id}")
    log("")

    # Initial state (mirrors SFN start_execution input)
    state: dict = {"topic_id": topic_id, "run_id": run_id}

    stages = [
        "LoadTopicConfig",
        "AssembleTopicContext",
        "PlanTopic",
        "ResearchTopic",
        "VerifyEvidence",
        "PersistEvidenceArtifacts",
        "DraftChapter",
        "EditorialReview",
        "BuildDraftArtifact",
        "GenerateDiffAndReleaseNotes",
        "NotifyAdminForReview",
    ]

    handlers = import_workers()

    past_start = not bool(args.start_from)
    for stage in stages:
        if args.stop_before and stage == args.stop_before:
            log(f"Stopping before {stage} (as requested).")
            break
        if not past_start:
            if stage == args.start_from:
                past_start = True
            else:
                # Run silently to rebuild accumulated state
                try:
                    result = handlers[stage](state, None)
                    state[_stage_key(stage)] = {"body": result}
                except Exception:
                    pass
                continue
        state = run_stage(stage, handlers[stage], state)

    if args.auto_approve and not (args.stop_before and "PublishTopic" == args.stop_before):
        log("\n=== Auto-approving draft ===")
        # Inject approval decision into state (mimics SFN RouteApprovalDecision)
        state["approval_result"] = {"decision": "approve", "notes": "auto-approved by local runner"}
        state = run_stage("PublishTopic", handlers["PublishTopic"], state)
        state = run_stage("RebuildIndexes", handlers["RebuildIndexes"], state)
        log("\n=== Pipeline COMPLETE (published) ===")
        log(f"topic_id = {topic_id}")
        log(f"run_id   = {run_id}")
        publish = state.get("publish_result", {}).get("body", {})
        log(f"published_version = {publish.get('published_version', publish.get('version', '?'))}")
    else:
        log("\n=== Pipeline complete (stopped before WaitForApproval) ===")
        log(f"topic_id = {topic_id}")
        log(f"run_id   = {run_id}")
        log("\nTo approve via API:")
        log(f'  curl -X POST http://localhost:8000/admin/topics/{topic_id}/review/{run_id} \\')
        log(f'       -H "Authorization: Bearer <token>" \\')
        log(f'       -H "Content-Type: application/json" \\')
        log(f'       -d \'{{"decision":"approve","notes":"local test"}}\'')


if __name__ == "__main__":
    main()

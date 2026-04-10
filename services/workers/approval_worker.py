"""
NotifyAdminForReview / WaitForApproval / StoreRejection — Step Functions worker (stages 11, 12, 14).

Responsibilities by invocation context (detected via event payload):
  - "notify"    → send SES email, store task token + REVIEW record in DDB
  - "wait"      → handle the waitForTaskToken callback (called by WaitForApproval state)
  - "rejection" → mark run as REJECTED in DDB

Implemented in M5.
"""
from __future__ import annotations

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

from services.workers.base import extract_execution_input
from shared_types.tracer import stage_completed, stage_started

_STAGE = "NotifyAdminForReview"


def handler(event: dict, context: Any) -> dict:
    """
    Handles three invocations:
      1. NotifyAdminForReview state — no task_token in event
      2. WaitForApproval state — task_token present in event (via Payload mapping)
      3. StoreRejection state — approval_result.decision == "reject"
    """
    # WaitForApproval passes: { "task_token": "...", "input": <full $$> }
    if "task_token" in event:
        task_token = event["task_token"]
        inp = extract_execution_input(event.get("input", {}))
        run_id = inp["run_id"]
        stage_started(run_id, "WaitForApproval")
        # TODO M5: store task_token in DynamoDB REVIEW record, send SES notification
        stage_completed(run_id, "WaitForApproval")
        # WaitForApproval pauses here — Lambda returns and SFN waits for SendTaskSuccess/Failure
        return {"topic_id": inp["topic_id"], "run_id": run_id, "task_token_stored": True, "status": "STUB"}

    inp = extract_execution_input(event)
    run_id = inp["run_id"]
    stage_started(run_id, _STAGE)
    # TODO M5: send SES notification to admin
    stage_completed(run_id, _STAGE)
    return {"topic_id": inp["topic_id"], "run_id": run_id, "status": "STUB"}

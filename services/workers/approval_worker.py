"""
NotifyAdminForReview — Step Functions worker (stage 11 of 14).

Responsibilities (detected via event payload):
  "notify"  → store task token + REVIEW record in DDB, send SES email to admin
  "reject"  → mark REVIEW record as REJECTED (called after WaitForApproval on rejection path)

WaitForApproval itself is a pure Step Functions waitForTaskToken state — no Lambda.
The task token is retrieved from DDB by the admin approval API (services/api/reviews.py)
when the admin submits their decision.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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

import boto3

from services.workers.base import (
    extract_execution_input,
    get_table,
    get_topic_meta,
)
from shared_types.tracer import stage_completed, stage_started

_STAGE_NOTIFY = "NotifyAdminForReview"
_STAGE_REJECT = "StoreRejection"

_AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
_SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "")
_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", _SES_SENDER)
_ADMIN_UI_BASE = os.environ.get("ADMIN_UI_BASE_URL", "http://localhost:5173")
# How long the admin has to act before Step Functions times out the wait state
_REVIEW_TIMEOUT_HOURS = int(os.environ.get("REVIEW_TIMEOUT_HOURS", "72"))


# ── notify ────────────────────────────────────────────────────────────────────

def notify_admin(topic_id: str, run_id: str, task_token: str,
                 review_artifact_uri: str | None = None,
                 diff_summary_uri: str | None = None) -> dict:
    """
    Store the task token + REVIEW record in DDB and send an SES notification.
    Called by the NotifyAdminForReview Lambda state (stage 11).
    """
    stage_started(run_id, _STAGE_NOTIFY)

    topic = get_topic_meta(topic_id)
    title = topic["title"] if topic else topic_id

    timeout_at = (datetime.now(timezone.utc) + timedelta(hours=_REVIEW_TIMEOUT_HOURS)).isoformat()

    # Persist the REVIEW record — admin approval API reads this to retrieve task_token
    table = get_table()
    table.put_item(Item={
        "PK": f"TOPIC#{topic_id}",
        "SK": f"REVIEW#{run_id}",
        "ENTITY_TYPE": "REVIEW",
        "REVIEW_STATUS": "REVIEW_STATUS#PENDING_REVIEW",
        "topic_id": topic_id,
        "run_id": run_id,
        "task_token": task_token,
        "review_status": "PENDING_REVIEW",
        "review_artifact_uri": review_artifact_uri or "",
        "diff_summary_uri": diff_summary_uri or "",
        "timeout_at": timeout_at,
        "UPDATED_AT": datetime.now(timezone.utc).isoformat(),
    })

    _send_review_email(topic_id, run_id, title)

    stage_completed(run_id, _STAGE_NOTIFY,
                    review_status="PENDING_REVIEW",
                    timeout_at=timeout_at)
    return {"topic_id": topic_id, "run_id": run_id,
            "review_status": "PENDING_REVIEW",
            "timeout_at": timeout_at}


def _send_review_email(topic_id: str, run_id: str, title: str) -> None:
    if not _SES_SENDER or not _ADMIN_EMAIL:
        return  # SES not configured in dev — skip silently

    review_url = f"{_ADMIN_UI_BASE}/admin/topics/{topic_id}/review/{run_id}"
    subject = f"[Ebook Platform] Review ready: {title}"
    body_html = f"""
<html><body>
<h2>Draft ready for review</h2>
<p><strong>Topic:</strong> {title}</p>
<p><strong>Run ID:</strong> {run_id}</p>
<p><a href="{review_url}">Open in Admin Console →</a></p>
<p>This review will time out in {_REVIEW_TIMEOUT_HOURS} hours if no action is taken.</p>
</body></html>
"""
    body_text = (
        f"Draft ready for review\n\nTopic: {title}\nRun: {run_id}\n"
        f"Review URL: {review_url}\n\n"
        f"This review will time out in {_REVIEW_TIMEOUT_HOURS} hours."
    )

    try:
        ses = boto3.client("ses", region_name=_AWS_REGION)
        ses.send_email(
            Source=_SES_SENDER,
            Destination={"ToAddresses": [_ADMIN_EMAIL]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                },
            },
        )
    except Exception as exc:
        # Non-fatal — the task token is already stored; admin can find the review in the UI
        print(f"[approval_worker] SES send failed (non-fatal): {exc}")


# ── reject ────────────────────────────────────────────────────────────────────

def store_rejection(topic_id: str, run_id: str,
                    notes: str = "", reviewer: str = "") -> dict:
    """
    Mark the REVIEW record as REJECTED. Called by the StoreRejection state (stage 14).
    """
    stage_started(run_id, _STAGE_REJECT)

    table = get_table()
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": f"REVIEW#{run_id}"},
        UpdateExpression=(
            "SET review_status = :s, REVIEW_STATUS = :rskey, "
            "rejected_at = :now, UPDATED_AT = :now, "
            "notes = :notes, reviewer = :reviewer"
        ),
        ExpressionAttributeValues={
            ":s": "REJECTED",
            ":rskey": "REVIEW_STATUS#REJECTED",
            ":now": now,
            ":notes": notes,
            ":reviewer": reviewer,
        },
    )

    stage_completed(run_id, _STAGE_REJECT, review_status="REJECTED")
    return {"topic_id": topic_id, "run_id": run_id, "review_status": "REJECTED"}


# ── handler ───────────────────────────────────────────────────────────────────

def handler(event: dict, _context: Any) -> dict:
    """
    Dispatches to notify_admin or store_rejection based on event shape.

    NotifyAdminForReview state passes:
      { "task_token": "<sfn task token>", ...execution context... }

    StoreRejection state passes:
      { "approval_decision": "reject", "notes": "...", "reviewer": "...", ...context... }
    """
    inp = extract_execution_input(event)
    topic_id = inp["topic_id"]
    run_id = inp["run_id"]

    if "task_token" in event:
        # NotifyAdminForReview — SFN injects the task token via Parameters mapping
        build = event.get("build_result", {}).get("body", {})
        diff = event.get("diff_result", {}).get("body", {})
        return notify_admin(
            topic_id, run_id,
            task_token=event["task_token"],
            review_artifact_uri=build.get("review_artifact_uri"),
            diff_summary_uri=diff.get("diff_summary_uri"),
        )

    # StoreRejection path
    approval = event.get("approval_result", {})
    return store_rejection(
        topic_id, run_id,
        notes=approval.get("notes", ""),
        reviewer=approval.get("reviewer", ""),
    )

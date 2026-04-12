"""
Admin Review and Approval Lambda handler — M5.

Routes handled:
  GET  /admin/topics/{topicId}/review/{runId}
       Returns the staged draft artifact URI, diff summary, scorecard, and run metadata
       so the admin UI can render the review page.

  POST /admin/topics/{topicId}/review/{runId}
       Body: { "decision": "approve" | "reject", "notes": "..." }
       Retrieves the SFN task token from DynamoDB and calls SendTaskSuccess (approve)
       or SendTaskFailure (reject), which resumes the waiting Step Functions execution.

  GET  /admin/reviews
       Returns all pending reviews (REVIEW_STATUS#PENDING_REVIEW) via GSI3.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
_AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))


# ── AWS client factories ──────────────────────────────────────────────────────

def _table():
    return boto3.resource("dynamodb", region_name=_AWS_REGION).Table(_TABLE_NAME)


def _sfn():
    endpoint = os.environ.get("STEP_FUNCTIONS_ENDPOINT", "").strip()
    kwargs: dict = {"region_name": _AWS_REGION}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("stepfunctions", **kwargs)


# ── Response helpers ──────────────────────────────────────────────────────────

def _ok(body: Any, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _err(code: str, message: str, status: int) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": code, "message": message}),
    }


def _parse_body(event: dict) -> dict:
    body = event.get("body") or "{}"
    if isinstance(body, str):
        return json.loads(body)
    return body


def _caller_identity(event: dict) -> str:
    ctx = event.get("requestContext", {})
    jwt_claims = ctx.get("authorizer", {}).get("jwt", {}).get("claims", {})
    return jwt_claims.get("email") or jwt_claims.get("sub") or "unknown"


# ── Review record helpers ─────────────────────────────────────────────────────

def _get_review(topic_id: str, run_id: str) -> dict | None:
    resp = _table().get_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": f"REVIEW#{run_id}"}
    )
    return resp.get("Item")


def _get_run(topic_id: str, run_id: str) -> dict | None:
    resp = _table().get_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": f"RUN#{run_id}"}
    )
    return resp.get("Item")


def _list_pending_reviews() -> list[dict]:
    """Query GSI3 for all PENDING_REVIEW items, sorted by UPDATED_AT."""
    resp = _table().query(
        IndexName="GSI3-ReviewStatus-UpdatedAt",
        KeyConditionExpression=Key("REVIEW_STATUS").eq("REVIEW_STATUS#PENDING_REVIEW"),
        ScanIndexForward=False,  # Most recent first
    )
    return resp.get("Items", [])


# ── Route handlers ────────────────────────────────────────────────────────────

def _fetch_s3_json(uri: str) -> dict | None:
    """Fetch a JSON object from an s3:// URI. Returns None on any error."""
    if not uri or not uri.startswith("s3://"):
        return None
    try:
        s3 = boto3.client("s3", region_name=_AWS_REGION)
        rest = uri[5:]
        bucket, key = rest.split("/", 1)
        resp = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read())
    except Exception:
        return None


def _handle_get_review(topic_id: str, run_id: str) -> dict:
    """
    GET /admin/topics/{topicId}/review/{runId}

    Returns everything the admin UI needs to render the review page.
    S3 artifact content is inlined — the browser cannot access private S3 directly.
    """
    review = _get_review(topic_id, run_id)
    if not review:
        return _err("REVIEW_NOT_FOUND",
                    f"No review record found for run {run_id}", 404)

    run = _get_run(topic_id, run_id)

    # Inline the review artifact (content, sections, scorecard, diff_summary)
    artifact = _fetch_s3_json(review.get("review_artifact_uri", "")) or {}
    diff = _fetch_s3_json(review.get("diff_summary_uri", "")) or {}

    return _ok({
        "topic_id": topic_id,
        "run_id": run_id,
        "title": artifact.get("title", ""),
        "review_status": review.get("review_status"),
        "timeout_at": review.get("timeout_at"),
        "reviewer": review.get("reviewer"),
        "notes": review.get("notes"),
        "approved_at": review.get("approved_at"),
        "rejected_at": review.get("rejected_at"),
        # Inlined draft content
        "content": artifact.get("content", ""),
        "sections": artifact.get("sections", []),
        "word_count": artifact.get("word_count", 0),
        "scorecard": artifact.get("scorecard", {}),
        "changes_summary": artifact.get("changes_summary", ""),
        # Inlined diff / release notes
        "diff": {
            "is_first_version": diff.get("is_first_version", True),
            "sections_added": diff.get("sections_added", []),
            "sections_removed": diff.get("sections_removed", []),
            "sections_changed": diff.get("sections_changed", []),
            "release_notes": diff.get("release_notes", ""),
        },
        "run": {
            "status": run.get("status") if run else None,
            "trigger_source": run.get("trigger_source") if run else None,
            "started_at": run.get("started_at") if run else None,
            "cost_usd_total": run.get("cost_usd_total") if run else None,
        },
    })


def _handle_list_reviews() -> dict:
    """GET /admin/reviews — all pending reviews across all topics."""
    items = _list_pending_reviews()
    reviews = [
        {
            "topic_id": item.get("topic_id"),
            "run_id": item.get("run_id"),
            "title": item.get("title", ""),
            "review_status": item.get("review_status"),
            "timeout_at": item.get("timeout_at"),
            "updated_at": item.get("UPDATED_AT"),
        }
        for item in items
    ]
    return _ok({"reviews": reviews, "count": len(reviews)})


def _handle_submit_review(event: dict, topic_id: str, run_id: str) -> dict:
    """
    POST /admin/topics/{topicId}/review/{runId}

    Body: { "decision": "approve" | "reject", "notes": "..." }

    Retrieves the SFN task token from DynamoDB and calls:
      - SendTaskSuccess  → resumes SFN on the approval path (triggers PublishTopic)
      - SendTaskFailure  → resumes SFN on the rejection path (triggers StoreRejection)
    """
    body = _parse_body(event)
    decision = body.get("decision", "").lower()
    notes = body.get("notes", "")
    reviewer = _caller_identity(event)

    if decision not in ("approve", "reject"):
        return _err("INVALID_DECISION",
                    "decision must be 'approve' or 'reject'", 400)

    review = _get_review(topic_id, run_id)
    if not review:
        return _err("REVIEW_NOT_FOUND",
                    f"No review record found for run {run_id}", 404)

    if review.get("review_status") != "PENDING_REVIEW":
        return _err("ALREADY_DECIDED",
                    f"This review has already been {review.get('review_status', 'processed')}.", 409)

    task_token = review.get("task_token")
    if not task_token:
        return _err("NO_TASK_TOKEN",
                    "Task token missing from review record. The pipeline may have timed out.", 409)

    now = datetime.now(timezone.utc).isoformat()
    sfn = _sfn()

    if decision == "approve":
        sfn.send_task_success(
            taskToken=task_token,
            output=json.dumps({
                "decision": "approve",
                "notes": notes,
                "reviewer": reviewer,
                "decided_at": now,
            }),
        )
        new_status = "APPROVED"
        update_expr = (
            "SET review_status = :s, REVIEW_STATUS = :rskey, "
            "approved_at = :now, UPDATED_AT = :now, "
            "notes = :notes, reviewer = :reviewer"
        )
        update_vals = {
            ":s": "APPROVED",
            ":rskey": "REVIEW_STATUS#APPROVED",
            ":now": now,
            ":notes": notes,
            ":reviewer": reviewer,
        }
    else:
        sfn.send_task_failure(
            taskToken=task_token,
            error="ReviewRejected",
            cause=json.dumps({"notes": notes, "reviewer": reviewer}),
        )
        new_status = "REJECTED"
        update_expr = (
            "SET review_status = :s, REVIEW_STATUS = :rskey, "
            "rejected_at = :now, UPDATED_AT = :now, "
            "notes = :notes, reviewer = :reviewer"
        )
        update_vals = {
            ":s": "REJECTED",
            ":rskey": "REVIEW_STATUS#REJECTED",
            ":now": now,
            ":notes": notes,
            ":reviewer": reviewer,
        }

    _table().update_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": f"REVIEW#{run_id}"},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=update_vals,
    )

    return _ok({
        "topic_id": topic_id,
        "run_id": run_id,
        "review_status": new_status,
        "decided_at": now,
        "reviewer": reviewer,
    })


# ── Lambda handler ────────────────────────────────────────────────────────────

def _parse_path_params(path: str) -> dict:
    """Extract topicId and runId from rawPath since API GW proxy+ only provides 'proxy'."""
    import re
    m = re.match(r".*/topics/([^/]+)/review/([^/]+)", path)
    if m:
        return {"topicId": m.group(1), "runId": m.group(2)}
    m = re.match(r".*/topics/([^/]+)/review$", path)
    if m:
        return {"topicId": m.group(1)}
    return {}


def lambda_handler(event: dict, _context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    path = event.get("rawPath", "")
    params = {**(event.get("pathParameters") or {}), **_parse_path_params(path)}

    topic_id = params.get("topicId")
    run_id = params.get("runId")

    # GET /admin/reviews — list all pending reviews
    if method == "GET" and path.rstrip("/").endswith("/admin/reviews"):
        return _handle_list_reviews()

    # GET /admin/topics/{topicId}/review/{runId}
    if method == "GET" and topic_id and run_id:
        return _handle_get_review(topic_id, run_id)

    # POST /admin/topics/{topicId}/review/{runId}
    if method == "POST" and topic_id and run_id:
        return _handle_submit_review(event, topic_id, run_id)

    return _err("NOT_FOUND", f"No route matched: {method} {path}", 404)

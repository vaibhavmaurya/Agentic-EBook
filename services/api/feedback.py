"""
Admin Feedback Lambda handler — M8.

Routes:
  GET /admin/feedback/summary  — aggregated feedback grouped by topic
  GET /admin/topics/{topicId}/feedback — all feedback items for a topic
"""
from __future__ import annotations

import json
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
_AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
_GSI5 = "GSI5-FeedbackTopic-CreatedAt"


def _table():
    return boto3.resource("dynamodb", region_name=_AWS_REGION).Table(_TABLE_NAME)


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


# ── GET /admin/topics/{topicId}/feedback ─────────────────────────────────────

def _handle_list_topic_feedback(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    qp = event.get("queryStringParameters") or {}
    feedback_type = qp.get("type", "").upper() or None  # COMMENT | HIGHLIGHT | None (all)
    limit = min(int(qp.get("limit", "100")), 500)

    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}") & Key("SK").begins_with("FEEDBACK#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = resp.get("Items", [])

    if feedback_type:
        items = [i for i in items if i.get("feedback_type") == feedback_type]

    feedback = [
        {
            "feedback_id": item.get("feedback_id"),
            "feedback_type": item.get("feedback_type"),
            "topic_id": item.get("topic_id"),
            "section_id": item.get("section_id"),
            "comment_text": item.get("comment_text"),
            "selected_text": item.get("selected_text"),
            "highlight_id": item.get("highlight_id"),
            "moderation_status": item.get("moderation_status"),
            "created_at": item.get("CREATED_AT"),
        }
        for item in items
    ]
    return _ok({"feedback": feedback, "count": len(feedback)})


# ── GET /admin/feedback/summary ───────────────────────────────────────────────

def _handle_feedback_summary(event: dict) -> dict:
    """
    Scans all FEEDBACK entities across all topics, groups by topic_id.
    Returns counts per type and recent items per topic.
    Acceptable for MVP — topic count is small.
    """
    from boto3.dynamodb.conditions import Attr

    resp = _table().scan(
        FilterExpression=Attr("ENTITY_TYPE").eq("FEEDBACK"),
        ProjectionExpression=(
            "topic_id, feedback_id, feedback_type, section_id, "
            "comment_text, selected_text, moderation_status, CREATED_AT"
        ),
        Limit=1000,
    )
    items = resp.get("Items", [])

    # Group by topic_id
    by_topic: dict[str, dict] = {}
    for item in items:
        tid = item.get("topic_id", "unknown")
        if tid not in by_topic:
            by_topic[tid] = {
                "topic_id": tid,
                "comment_count": 0,
                "highlight_count": 0,
                "pending_count": 0,
                "recent": [],
            }
        ft = item.get("feedback_type", "")
        if ft == "COMMENT":
            by_topic[tid]["comment_count"] += 1
        elif ft == "HIGHLIGHT":
            by_topic[tid]["highlight_count"] += 1
        if item.get("moderation_status") == "PENDING":
            by_topic[tid]["pending_count"] += 1
        by_topic[tid]["recent"].append({
            "feedback_id": item.get("feedback_id"),
            "feedback_type": ft,
            "section_id": item.get("section_id"),
            "comment_text": (item.get("comment_text") or "")[:120],
            "selected_text": (item.get("selected_text") or "")[:80],
            "moderation_status": item.get("moderation_status"),
            "created_at": item.get("CREATED_AT"),
        })

    # Sort recent items per topic by created_at descending, keep top 10
    for t in by_topic.values():
        t["recent"] = sorted(
            t["recent"],
            key=lambda x: x.get("created_at") or "",
            reverse=True,
        )[:10]

    summary = sorted(by_topic.values(), key=lambda x: x["topic_id"])
    return _ok({
        "topics": summary,
        "topic_count": len(summary),
        "total_feedback": len(items),
    })


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict, _context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    path = event.get("rawPath", "")
    params = event.get("pathParameters") or {}

    if method == "GET" and path.endswith("/admin/feedback/summary"):
        return _handle_feedback_summary(event)

    if method == "GET" and "feedback" in path and params.get("topicId"):
        return _handle_list_topic_feedback(event)

    return _err("NOT_FOUND", f"No route matched: {method} {path}", 404)

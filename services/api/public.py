"""
Public API Lambda handler — M7.

Routes:
  GET  /public/toc                  — table of contents (reads toc.json from S3)
  GET  /public/topics/{topicId}     — topic content + manifest (reads from S3)
  GET  /public/search-index         — Lunr.js search index JSON (reads from S3)
  GET  /public/releases/latest      — recently published topics (from DDB)
  POST /public/comments             — reader comment on a topic/section
  POST /public/highlights           — text selection highlight
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
_S3_BUCKET = os.environ.get("S3_ARTIFACT_BUCKET", "")
_AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
_MAX_COMMENT_LEN = 2000
_MAX_HIGHLIGHT_LEN = 500
_MAX_RELEASES = 20


def _table():
    return boto3.resource("dynamodb", region_name=_AWS_REGION).Table(_TABLE_NAME)


def _s3():
    return boto3.client("s3", region_name=_AWS_REGION)


def _read_s3_json(key: str) -> dict | list:
    resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
    return json.loads(resp["Body"].read())


def _read_s3_text(key: str) -> str:
    resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
    return resp["Body"].read().decode("utf-8")


def _ok(body: Any, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def _err(code: str, message: str, status: int) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": code, "message": message}),
    }


def _parse_body(event: dict) -> dict:
    body = event.get("body") or "{}"
    if isinstance(body, str):
        return json.loads(body)
    return body


# ── GET /public/toc ──────────────────────────────────────────────────────────

def _handle_get_toc() -> dict:
    try:
        data = _read_s3_json("site/current/toc.json")
        return _ok(data)
    except Exception:
        return _ok({"generated_at": "", "topic_count": 0, "topics": []})


# ── GET /public/search-index ──────────────────────────────────────────────────

def _handle_get_search_index() -> dict:
    try:
        data = _read_s3_json("site/current/search/index.json")
        return _ok(data)
    except Exception:
        return _ok({"generated_at": "", "topic_count": 0, "documents": []})


# ── GET /public/topics/{topicId} ──────────────────────────────────────────────

def _handle_get_topic(topic_id: str) -> dict:
    """
    Returns the latest published content + manifest for a topic.
    Reads current_published_version from DynamoDB META, then fetches
    content.md and manifest.json from S3.
    """
    meta = _table().get_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": "META"}
    ).get("Item")

    if not meta or not meta.get("current_published_version"):
        return _err("NOT_FOUND", "Topic not found or not yet published.", 404)

    version = meta["current_published_version"]
    prefix = f"published/topics/{topic_id}/{version}"

    try:
        manifest = _read_s3_json(f"{prefix}/manifest.json")
        content = _read_s3_text(f"{prefix}/content.md")
        return _ok({**manifest, "content": content, "version": version})
    except Exception as exc:
        return _err("CONTENT_UNAVAILABLE", f"Could not read topic content: {exc}", 503)


# ── POST /public/comments ─────────────────────────────────────────────────────

def _handle_post_comment(event: dict) -> dict:
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _err("INVALID_JSON", "Request body must be valid JSON.", 400)

    topic_id = (body.get("topic_id") or "").strip()
    comment_text = (body.get("comment_text") or "").strip()
    section_id = (body.get("section_id") or "").strip() or None
    highlight_id = (body.get("highlight_id") or "").strip() or None

    if not topic_id:
        return _err("MISSING_FIELD", "topic_id is required.", 400)
    if not comment_text:
        return _err("MISSING_FIELD", "comment_text is required.", 400)
    if len(comment_text) > _MAX_COMMENT_LEN:
        return _err("TOO_LONG", f"comment_text must be under {_MAX_COMMENT_LEN} characters.", 400)

    feedback_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    _table().put_item(Item={
        "PK": f"TOPIC#{topic_id}",
        "SK": f"FEEDBACK#{feedback_id}",
        "ENTITY_TYPE": "FEEDBACK",
        "FEEDBACK_TOPIC": f"FEEDBACK_TOPIC#{topic_id}",
        "feedback_id": feedback_id,
        "feedback_type": "COMMENT",
        "topic_id": topic_id,
        "section_id": section_id,
        "comment_text": comment_text,
        "highlight_id": highlight_id,
        "moderation_status": "PENDING",
        "CREATED_AT": now,
        "UPDATED_AT": now,
    })

    return _ok({"comment_id": feedback_id, "status": "PENDING"}, 201)


# ── POST /public/highlights ───────────────────────────────────────────────────

def _handle_post_highlight(event: dict) -> dict:
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _err("INVALID_JSON", "Request body must be valid JSON.", 400)

    topic_id = (body.get("topic_id") or "").strip()
    selected_text = (body.get("selected_text") or "").strip()
    section_id = (body.get("section_id") or "").strip() or None

    if not topic_id:
        return _err("MISSING_FIELD", "topic_id is required.", 400)
    if not selected_text:
        return _err("MISSING_FIELD", "selected_text is required.", 400)
    if len(selected_text) > _MAX_HIGHLIGHT_LEN:
        return _err("TOO_LONG", f"selected_text must be under {_MAX_HIGHLIGHT_LEN} characters.", 400)

    highlight_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    _table().put_item(Item={
        "PK": f"TOPIC#{topic_id}",
        "SK": f"FEEDBACK#{highlight_id}",
        "ENTITY_TYPE": "FEEDBACK",
        "FEEDBACK_TOPIC": f"FEEDBACK_TOPIC#{topic_id}",
        "feedback_id": highlight_id,
        "feedback_type": "HIGHLIGHT",
        "topic_id": topic_id,
        "section_id": section_id,
        "selected_text": selected_text,
        "moderation_status": "PENDING",
        "CREATED_AT": now,
        "UPDATED_AT": now,
    })

    return _ok({"highlight_id": highlight_id, "status": "PENDING"}, 201)


# ── GET /public/releases/latest ───────────────────────────────────────────────

def _handle_get_releases() -> dict:
    """
    Returns the most recently published topic versions from DynamoDB.
    Queries all PUBLISHED_VERSION entities via a scan with filter — acceptable
    for MVP scale (topics count is small).
    """
    resp = _table().scan(
        FilterExpression=Attr("ENTITY_TYPE").eq("PUBLISHED_VERSION"),
        ProjectionExpression=(
            "topic_id, #ver, title, published_at, release_notes, word_count"
        ),
        ExpressionAttributeNames={"#ver": "version"},
        Limit=200,
    )
    items = sorted(
        resp.get("Items", []),
        key=lambda x: x.get("published_at", ""),
        reverse=True,
    )[:_MAX_RELEASES]

    return _ok({
        "releases": [
            {
                "topic_id": item.get("topic_id"),
                "version": item.get("version"),
                "title": item.get("title"),
                "published_at": item.get("published_at"),
                "release_notes": item.get("release_notes"),
                "word_count": item.get("word_count"),
            }
            for item in items
        ],
        "count": len(items),
    })


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event: dict, _context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    path = event.get("rawPath", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }

    if method == "POST" and path.endswith("/public/comments"):
        return _handle_post_comment(event)

    if method == "POST" and path.endswith("/public/highlights"):
        return _handle_post_highlight(event)

    if method == "GET" and path.endswith("/public/releases/latest"):
        return _handle_get_releases()

    if method == "GET" and path.endswith("/public/toc"):
        return _handle_get_toc()

    if method == "GET" and path.endswith("/public/search-index"):
        return _handle_get_search_index()

    # GET /public/topics/{topicId}
    if method == "GET" and "/public/topics/" in path:
        parts = path.rstrip("/").split("/public/topics/")
        if len(parts) == 2 and parts[1]:
            topic_id = parts[1].split("/")[0]
            return _handle_get_topic(topic_id)

    return _err("NOT_FOUND", f"No route matched: {method} {path}", 404)

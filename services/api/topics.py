"""
Topic management Lambda handler — covers UC-01 through UC-03 and the manual trigger.

Routes handled (API Gateway HTTP API, payload format 2.0):
  GET    /admin/topics
  POST   /admin/topics
  GET    /admin/topics/{topicId}
  PUT    /admin/topics/{topicId}
  DELETE /admin/topics/{topicId}
  PUT    /admin/topics/reorder
  POST   /admin/topics/{topicId}/trigger
  GET    /admin/topics/{topicId}/runs
  GET    /admin/topics/{topicId}/runs/{runId}
"""
from __future__ import annotations

import json
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from pydantic import ValidationError

from shared_types.models import (
    RunStatus,
    ScheduleType,
    TopicCreate,
    TopicReorderRequest,
    TopicUpdate,
    TriggerSource,
    new_id,
    utc_now,
)
from shared_types.tracer import run_triggered, topic_event

# ── AWS clients ───────────────────────────────────────────────────────────────

_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
_SFN_ARN = os.environ["STEP_FUNCTIONS_ARN"]
_AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")
_S3_BUCKET = os.environ.get("S3_ARTIFACT_BUCKET", "")


def _table():
    return boto3.resource("dynamodb", region_name=_AWS_REGION).Table(_TABLE_NAME)


def _s3():
    return boto3.client("s3", region_name=_AWS_REGION)


def _sfn():
    endpoint = os.environ.get("STEP_FUNCTIONS_ENDPOINT", "").strip()
    kwargs = {"region_name": _AWS_REGION}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("stepfunctions", **kwargs)


def _scheduler():
    return boto3.client("scheduler", region_name=_AWS_REGION)


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
    """Extract the Cognito username from the JWT claims injected by API Gateway."""
    ctx = event.get("requestContext", {})
    authorizer = ctx.get("authorizer", {})
    jwt_claims = authorizer.get("jwt", {}).get("claims", {})
    return jwt_claims.get("email") or jwt_claims.get("sub") or "unknown"


# ── DynamoDB helpers ──────────────────────────────────────────────────────────


def _get_topic_meta(topic_id: str) -> dict | None:
    resp = _table().get_item(Key={"PK": f"TOPIC#{topic_id}", "SK": "META"})
    return resp.get("Item")


def _list_topics() -> list[dict]:
    """Query GSI1 for all active topics, sorted by ORDER_KEY."""
    resp = _table().query(
        IndexName="GSI1-EntityType-OrderKey",
        KeyConditionExpression=Key("ENTITY_TYPE").eq("TOPIC"),
        FilterExpression=Attr("active").eq(True),
    )
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: int(x.get("order", 0)))


def _next_order() -> int:
    topics = _list_topics()
    if not topics:
        return 1
    return max(int(t.get("order", 0)) for t in topics) + 1


# ── EventBridge Scheduler helpers ─────────────────────────────────────────────


def _upsert_schedule(topic_id: str, schedule_type: ScheduleType, cron_expression: str | None) -> None:
    if schedule_type == ScheduleType.manual:
        _delete_schedule(topic_id)
        return

    schedule_name = f"topic-{topic_id}"
    scheduler_role_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")

    if schedule_type == ScheduleType.daily:
        expression = "cron(0 6 * * ? *)"  # 06:00 UTC daily
    elif schedule_type == ScheduleType.weekly:
        expression = "cron(0 6 ? * MON *)"  # Monday 06:00 UTC
    else:
        expression = cron_expression  # custom — caller validated it exists

    payload = json.dumps({
        "topic_id": topic_id,
        "trigger_source": "schedule",
    })

    try:
        _scheduler().create_schedule(
            Name=schedule_name,
            GroupName=os.environ.get("SCHEDULE_GROUP_NAME", "ebook-platform-dev-topics"),
            ScheduleExpression=expression,
            ScheduleExpressionTimezone="UTC",
            FlexibleTimeWindow={"Mode": "OFF"},
            Target={
                "Arn": _SFN_ARN,
                "RoleArn": scheduler_role_arn,
                "Input": payload,
            },
            State="ENABLED",
        )
    except _scheduler().exceptions.ConflictException:
        _scheduler().update_schedule(
            Name=schedule_name,
            GroupName=os.environ.get("SCHEDULE_GROUP_NAME", "ebook-platform-dev-topics"),
            ScheduleExpression=expression,
            ScheduleExpressionTimezone="UTC",
            FlexibleTimeWindow={"Mode": "OFF"},
            Target={
                "Arn": _SFN_ARN,
                "RoleArn": scheduler_role_arn,
                "Input": payload,
            },
            State="ENABLED",
        )


def _delete_schedule(topic_id: str) -> None:
    try:
        _scheduler().delete_schedule(
            Name=f"topic-{topic_id}",
            GroupName=os.environ.get("SCHEDULE_GROUP_NAME", "ebook-platform-dev-topics"),
        )
    except Exception:
        pass  # schedule may not exist — idempotent


# ── Route handlers ────────────────────────────────────────────────────────────


def list_topics(event: dict) -> dict:
    topics = _list_topics()
    # Enrich with last run summary
    result = []
    for t in topics:
        topic_id = t["topic_id"]
        runs = _table().query(
            KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}") & Key("SK").begins_with("RUN#"),
            ScanIndexForward=False,
            Limit=1,
        ).get("Items", [])
        last_run = None
        if runs:
            r = runs[0]
            last_run = {
                "run_id": r.get("run_id"),
                "status": r.get("status"),
                "started_at": r.get("started_at"),
                "cost_usd": float(r.get("cost_usd", 0)),
            }
        result.append({
            "topic_id": topic_id,
            "title": t.get("title"),
            "description": t.get("description"),
            "order": int(t.get("order", 0)),
            "active": t.get("active", True),
            "schedule_type": t.get("schedule_type", "manual"),
            "last_run": last_run,
        })
    return _ok({"topics": result})


def create_topic(event: dict) -> dict:
    try:
        req = TopicCreate(**_parse_body(event))
    except ValidationError as e:
        return _err("VALIDATION_ERROR", str(e), 400)

    topic_id = new_id()
    now = utc_now()
    order = _next_order()

    item = {
        "PK": f"TOPIC#{topic_id}",
        "SK": "META",
        "topic_id": topic_id,
        "title": req.title,
        "description": req.description,
        "instructions": req.instructions,
        "subtopics": req.subtopics,
        "order": order,
        "active": True,
        "schedule_type": req.schedule_type.value,
        "cron_expression": req.cron_expression,
        "created_at": now,
        "updated_at": now,
        # GSI1 fields
        "ENTITY_TYPE": "TOPIC",
        "ORDER_KEY": str(order).zfill(6),
    }

    _table().put_item(Item=item)

    if req.schedule_type != ScheduleType.manual:
        _upsert_schedule(topic_id, req.schedule_type, req.cron_expression)

    topic_event(topic_id, "TOPIC_CREATED", topic_id, title=req.title)

    return _ok({"topic_id": topic_id}, status=201)


def get_topic(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    item = _get_topic_meta(topic_id)
    if not item or not item.get("active", True):
        return _err("TOPIC_NOT_FOUND", f"Topic {topic_id} does not exist.", 404)

    # Last run summary
    runs = _table().query(
        KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}") & Key("SK").begins_with("RUN#"),
        ScanIndexForward=False,
        Limit=1,
    ).get("Items", [])
    last_run = None
    if runs:
        r = runs[0]
        last_run = {
            "run_id": r.get("run_id"),
            "status": r.get("status"),
            "started_at": r.get("started_at"),
            "cost_usd": float(r.get("cost_usd", 0)),
        }

    return _ok({
        "topic_id": item["topic_id"],
        "title": item["title"],
        "description": item["description"],
        "instructions": item["instructions"],
        "subtopics": item.get("subtopics", []),
        "order": int(item.get("order", 0)),
        "active": item.get("active", True),
        "schedule_type": item.get("schedule_type", "manual"),
        "cron_expression": item.get("cron_expression"),
        "current_published_version": item.get("current_published_version"),
        "published_at": item.get("published_at"),
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
        "last_run": last_run,
    })


def update_topic(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    item = _get_topic_meta(topic_id)
    if not item or not item.get("active", True):
        return _err("TOPIC_NOT_FOUND", f"Topic {topic_id} does not exist.", 404)

    try:
        req = TopicUpdate(**_parse_body(event))
    except ValidationError as e:
        return _err("VALIDATION_ERROR", str(e), 400)

    now = utc_now()
    updates: dict[str, Any] = {"updated_at": now}
    if req.title is not None:
        updates["title"] = req.title
    if req.description is not None:
        updates["description"] = req.description
    if req.instructions is not None:
        updates["instructions"] = req.instructions
    if req.subtopics is not None:
        updates["subtopics"] = req.subtopics
    if req.schedule_type is not None:
        updates["schedule_type"] = req.schedule_type.value
    if req.cron_expression is not None:
        updates["cron_expression"] = req.cron_expression

    if not updates:
        return _ok({"topic_id": topic_id, "updated_at": item["updated_at"]})

    expr_parts = ["#updated_at = :updated_at"]
    expr_names = {"#updated_at": "updated_at"}
    expr_values: dict[str, Any] = {":updated_at": now}

    field_map = {
        "title": ("title", "title"),
        "description": ("description", "description"),
        "instructions": ("instructions", "instructions"),
        "subtopics": ("subtopics", "subtopics"),
        "schedule_type": ("schedule_type", "schedule_type"),
        "cron_expression": ("cron_expression", "cron_expression"),
    }
    for py_field, (ddb_name, alias) in field_map.items():
        if py_field in updates:
            expr_parts.append(f"#{alias} = :{alias}")
            expr_names[f"#{alias}"] = ddb_name
            expr_values[f":{alias}"] = updates[py_field]

    _table().update_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": "META"},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    new_schedule_type = req.schedule_type or ScheduleType(item.get("schedule_type", "manual"))
    new_cron = req.cron_expression or item.get("cron_expression")
    _upsert_schedule(topic_id, new_schedule_type, new_cron)

    topic_event(topic_id, "TOPIC_UPDATED", topic_id, changed_fields=list(updates.keys()))

    return _ok({"topic_id": topic_id, "updated_at": now})


def _delete_s3_prefix(prefix: str) -> int:
    """Delete all S3 objects under a given key prefix. Returns count deleted."""
    if not _S3_BUCKET:
        return 0
    s3 = _s3()
    deleted = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
        objects = page.get("Contents", [])
        if not objects:
            continue
        s3.delete_objects(
            Bucket=_S3_BUCKET,
            Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
        )
        deleted += len(objects)
    return deleted


def _rebuild_site_indexes_without(topic_id: str) -> None:
    """
    Rebuild toc.json, search/index.json, and sitemap.json excluding the deleted topic.
    Triggers an Amplify redeploy so the public site reflects the removal immediately.
    """
    if not _S3_BUCKET:
        return
    import re
    import urllib.request
    from datetime import datetime, timezone

    s3 = _s3()
    now = datetime.now(timezone.utc).isoformat()

    def _get_json(key: str) -> Any:
        try:
            resp = s3.get_object(Bucket=_S3_BUCKET, Key=key)
            return json.loads(resp["Body"].read())
        except Exception:
            return {}

    def _put_json(key: str, data: Any) -> None:
        s3.put_object(
            Bucket=_S3_BUCKET,
            Key=key,
            Body=json.dumps(data, default=str).encode(),
            ContentType="application/json",
        )

    # Load existing toc and filter out the deleted topic
    toc = _get_json("site/current/toc.json")
    topics = [t for t in toc.get("topics", []) if t.get("topic_id") != topic_id]

    # Rebuild toc.json
    _put_json("site/current/toc.json", {
        "generated_at": now,
        "topic_count": len(topics),
        "topics": topics,
    })

    # Rebuild search index
    search = _get_json("site/current/search/index.json")
    docs = [d for d in search.get("documents", []) if d.get("id") != topic_id]
    _put_json("site/current/search/index.json", {
        "generated_at": now,
        "topic_count": len(docs),
        "documents": docs,
    })

    # Rebuild sitemap
    sitemap = _get_json("site/current/sitemap.json")
    sitemap_topics = [t for t in sitemap.get("topics", []) if t.get("topic_id") != topic_id]
    _put_json("site/current/sitemap.json", {
        "generated_at": now,
        "topics": sitemap_topics,
    })

    # Trigger Amplify redeploy using the pre-built zip
    app_id = os.environ.get("AMPLIFY_APP_ID", "")
    branch = os.environ.get("AMPLIFY_BRANCH", "dev")
    if not app_id:
        return
    try:
        dist_zip = s3.get_object(Bucket=_S3_BUCKET, Key="deployments/public-site.zip")["Body"].read()
        amplify = boto3.client("amplify", region_name=_AWS_REGION)
        resp = amplify.create_deployment(appId=app_id, branchName=branch)
        req = urllib.request.Request(resp["zipUploadUrl"], data=dist_zip, method="PUT")
        req.add_header("Content-Type", "application/zip")
        urllib.request.urlopen(req)
        amplify.start_deployment(appId=app_id, branchName=branch, jobId=resp["jobId"])
        print(f"[delete_topic] Amplify redeploy triggered: jobId={resp['jobId']}")
    except Exception as exc:
        print(f"[delete_topic] Amplify redeploy failed (non-fatal): {exc}")


def delete_topic(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    item = _get_topic_meta(topic_id)
    if not item:
        return _err("TOPIC_NOT_FOUND", f"Topic {topic_id} does not exist.", 404)

    now = utc_now()

    # 1. Soft-delete the DynamoDB META record
    _table().update_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": "META"},
        UpdateExpression="SET active = :f, updated_at = :now",
        ExpressionAttributeValues={":f": False, ":now": now},
    )

    # 2. Cancel the EventBridge schedule
    _delete_schedule(topic_id)

    # 3. Delete all published S3 artifacts for this topic
    published_deleted = _delete_s3_prefix(f"published/topics/{topic_id}/")
    print(f"[delete_topic] Deleted {published_deleted} published S3 objects for {topic_id}")

    # 4. Rebuild site indexes (toc.json, search index, sitemap) excluding this topic,
    #    then trigger an Amplify redeploy so the public site reflects the removal.
    try:
        _rebuild_site_indexes_without(topic_id)
    except Exception as exc:
        print(f"[delete_topic] Index rebuild failed (non-fatal): {exc}")

    topic_event(topic_id, "TOPIC_DELETED", topic_id)

    return _ok({"topic_id": topic_id, "active": False, "published_objects_deleted": published_deleted})


def reorder_topics(event: dict) -> dict:
    try:
        req = TopicReorderRequest(**_parse_body(event))
    except ValidationError as e:
        return _err("VALIDATION_ERROR", str(e), 400)

    now = utc_now()
    table = _table()
    with table.batch_writer() as batch:
        for idx, topic_id in enumerate(req.order):
            order = idx + 1
            table.update_item(
                Key={"PK": f"TOPIC#{topic_id}", "SK": "META"},
                UpdateExpression="SET #order = :order, ORDER_KEY = :ok, updated_at = :now",
                ExpressionAttributeNames={"#order": "order"},
                ExpressionAttributeValues={
                    ":order": order,
                    ":ok": str(order).zfill(6),
                    ":now": now,
                },
            )

    return _ok({"updated": len(req.order)})


def trigger_run(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    item = _get_topic_meta(topic_id)
    if not item or not item.get("active", True):
        return _err("TOPIC_NOT_FOUND", f"Topic {topic_id} does not exist.", 404)

    # Check for an already-running execution
    existing = _table().query(
        KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}") & Key("SK").begins_with("RUN#"),
        FilterExpression=Attr("status").is_in([RunStatus.PENDING.value, RunStatus.RUNNING.value, RunStatus.WAITING_APPROVAL.value]),
        ScanIndexForward=False,
        Limit=5,
    ).get("Items", [])
    if existing:
        return _err("CONFLICT", "A run is already in progress for this topic.", 409)

    run_id = new_id()
    now = utc_now()
    actor = _caller_identity(event)

    sfn_input = json.dumps({
        "topic_id": topic_id,
        "run_id": run_id,
        "trigger_source": TriggerSource.admin_manual.value,
        "triggered_by": actor,
    })

    sfn_resp = _sfn().start_execution(
        stateMachineArn=_SFN_ARN,
        name=run_id,
        input=sfn_input,
    )
    execution_arn = sfn_resp["executionArn"]

    _table().put_item(Item={
        "PK": f"TOPIC#{topic_id}",
        "SK": f"RUN#{run_id}",
        "topic_id": topic_id,
        "run_id": run_id,
        "status": RunStatus.PENDING.value,
        "trigger_source": TriggerSource.admin_manual.value,
        "triggered_by": actor,
        "execution_arn": execution_arn,
        "started_at": now,
        "cost_usd": "0",
        # GSI2 fields
        "RUN_STATUS": f"RUN_STATUS#{RunStatus.PENDING.value}",
        "UPDATED_AT": now,
    })

    run_triggered(run_id, topic_id, TriggerSource.admin_manual.value, triggered_by=actor)

    return _ok({"run_id": run_id, "execution_arn": execution_arn}, status=202)


# ── GET /admin/topics/{topicId}/runs ─────────────────────────────────────────

def list_runs(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}") & Key("SK").begins_with("RUN#"),
        ScanIndexForward=False,
    )
    items = resp.get("Items", [])
    runs = [
        {
            "run_id": item.get("run_id"),
            "status": item.get("status"),
            "trigger_source": item.get("trigger_source"),
            "triggered_by": item.get("triggered_by"),
            "execution_arn": item.get("execution_arn"),
            "started_at": item.get("started_at"),
            "completed_at": item.get("completed_at"),
            "cost_usd": str(item.get("cost_usd", "0")),
            "content_score": str(item.get("content_score", "")) if item.get("content_score") is not None else None,
        }
        for item in items
    ]
    return _ok({"runs": runs, "count": len(runs)})


# ── GET /admin/topics/{topicId}/runs/{runId} ──────────────────────────────────

def get_run(event: dict) -> dict:
    topic_id = event["pathParameters"]["topicId"]
    run_id = event["pathParameters"]["runId"]

    # Fetch the RUN record
    run_item = _table().get_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": f"RUN#{run_id}"}
    ).get("Item")
    if not run_item:
        return _err("NOT_FOUND", f"Run {run_id} not found.", 404)

    # Fetch all trace events for this run
    events_resp = _table().query(
        KeyConditionExpression=Key("PK").eq(f"RUN#{run_id}") & Key("SK").begins_with("EVENT#"),
        ScanIndexForward=True,
    )
    trace_events = [
        {
            "sk": ev.get("SK"),
            "event_type": ev.get("event_type"),
            "stage": ev.get("stage"),
            "agent_name": ev.get("agent_name"),
            "model_name": ev.get("model_name"),
            "token_usage": ev.get("token_usage"),
            "cost_usd": str(ev.get("cost_usd", "0")),
            "error_message": ev.get("error_message"),
            "error_classification": ev.get("error_classification"),
            "timestamp": ev.get("timestamp"),
        }
        for ev in events_resp.get("Items", [])
    ]

    # Compute per-stage cost totals from trace events
    stage_costs: dict[str, float] = {}
    for ev in trace_events:
        stage = ev.get("stage") or ""
        try:
            cost = float(ev.get("cost_usd") or 0)
        except (TypeError, ValueError):
            cost = 0.0
        stage_costs[stage] = stage_costs.get(stage, 0.0) + cost

    return _ok({
        "run": {
            "run_id": run_item.get("run_id"),
            "topic_id": run_item.get("topic_id", topic_id),
            "status": run_item.get("status"),
            "trigger_source": run_item.get("trigger_source"),
            "triggered_by": run_item.get("triggered_by"),
            "execution_arn": run_item.get("execution_arn"),
            "started_at": run_item.get("started_at"),
            "completed_at": run_item.get("completed_at"),
            "cost_usd": str(run_item.get("cost_usd", "0")),
            "content_score": str(run_item.get("content_score", "")) if run_item.get("content_score") is not None else None,
        },
        "trace_events": trace_events,
        "stage_costs": stage_costs,
    })


# ── Lambda entry point ────────────────────────────────────────────────────────

# Route table: (method, path_pattern) → handler
_ROUTES: list[tuple[str, str, Any]] = [
    ("GET",    "/admin/topics",                              list_topics),
    ("POST",   "/admin/topics",                              create_topic),
    ("PUT",    "/admin/topics/reorder",                      reorder_topics),
    ("GET",    "/admin/topics/{topicId}",                    get_topic),
    ("PUT",    "/admin/topics/{topicId}",                    update_topic),
    ("DELETE", "/admin/topics/{topicId}",                    delete_topic),
    ("POST",   "/admin/topics/{topicId}/trigger",            trigger_run),
    ("GET",    "/admin/topics/{topicId}/runs",               list_runs),
    ("GET",    "/admin/topics/{topicId}/runs/{runId}",       get_run),
]


def _match_route(method: str, path: str):
    for route_method, route_path, handler in _ROUTES:
        if method != route_method:
            continue
        # Exact match
        if route_path == path:
            return handler, {}
        # Parameterised match — replace {param} segments
        route_parts = route_path.split("/")
        path_parts = path.split("/")
        if len(route_parts) != len(path_parts):
            continue
        params = {}
        matched = True
        for rp, pp in zip(route_parts, path_parts):
            if rp.startswith("{") and rp.endswith("}"):
                params[rp[1:-1]] = pp
            elif rp != pp:
                matched = False
                break
        if matched:
            return handler, params
    return None, {}


def lambda_handler(event: dict, context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")

    handler, path_params = _match_route(method, path)
    if handler is None:
        return _err("NOT_FOUND", f"No route for {method} {path}", 404)

    if path_params:
        event.setdefault("pathParameters", {}).update(path_params)

    try:
        return handler(event)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return _err("INTERNAL_ERROR", str(exc), 500)

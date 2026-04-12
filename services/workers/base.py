"""
Shared utilities for all Step Functions Lambda workers.

Every worker:
  1. Extracts topic_id / run_id from the SFN execution context (Payload.$ = "$$")
  2. Calls stage_started() at the top of the handler
  3. Does its work
  4. Calls stage_completed() on success
  5. Calls stage_failed() in the except block and re-raises (so SFN marks the
     state as Failed and can retry or transition to a Catch handler)

SFN execution context structure (passed when "Payload.$": "$$"):
    event["Execution"]["Input"]  →  original start_execution input
    event["State"]["Name"]       →  current state name

To run a worker in isolation (no SFN):
    python services/workers/topic_loader.py --topic-id <id> --run-id <id>
"""
from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from shared_types.models import RunStatus, utc_now

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
_S3_BUCKET = os.environ.get("S3_ARTIFACT_BUCKET", "ebook-platform-artifacts-dev")
_AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))


# ── AWS client factories ──────────────────────────────────────────────────────

def get_table():
    return boto3.resource("dynamodb", region_name=_AWS_REGION).Table(_TABLE_NAME)


def get_s3():
    return boto3.client("s3", region_name=_AWS_REGION)


# ── SFN context extraction ────────────────────────────────────────────────────

def extract_execution_input(event: dict) -> dict:
    """
    Extract the original SFN start_execution input from the event.

    The state machine passes the full accumulated state to each Lambda using
    "Payload.$": "$".  The original start_execution input fields (topic_id,
    run_id) are at the top level of the state alongside all intermediate
    *_result keys from prior stages.

    When a worker is invoked directly (local testing / CLI), the event is
    already the input dict — same behaviour.

    Backwards-compat: if the old "Payload.$": "$$" pattern is detected
    (event has an "Execution" key from the context object), fall back to
    reading from Execution.Input.
    """
    if "Execution" in event:
        # Legacy: state machine passed the context object ($$) as payload.
        return event["Execution"].get("Input", {})
    # Normal path: full accumulated state ($) is the payload.
    return event


def current_state_name(event: dict) -> str:
    """Return the SFN state name, or 'LOCAL' when running directly."""
    return event.get("State", {}).get("Name", "LOCAL")


# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def get_topic_meta(topic_id: str) -> dict | None:
    resp = get_table().get_item(Key={"PK": f"TOPIC#{topic_id}", "SK": "META"})
    return resp.get("Item")


def set_run_status(topic_id: str, run_id: str, status: RunStatus, **extra_attrs: Any) -> None:
    """Update the run record's status and any additional attributes."""
    now = utc_now()
    set_parts = ["#status = :status", "UPDATED_AT = :now", "RUN_STATUS = :rskey"]
    names = {"#status": "status"}
    values: dict[str, Any] = {
        ":status": status.value,
        ":now": now,
        ":rskey": f"RUN_STATUS#{status.value}",
    }

    for k, v in extra_attrs.items():
        set_parts.append(f"#{k} = :{k}")
        names[f"#{k}"] = k
        values[f":{k}"] = v

    get_table().update_item(
        Key={"PK": f"TOPIC#{topic_id}", "SK": f"RUN#{run_id}"},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


# ── S3 helpers ────────────────────────────────────────────────────────────────

def s3_key(topic_id: str, run_id: str, subfolder: str, filename: str) -> str:
    return f"topics/{topic_id}/runs/{run_id}/{subfolder}/{filename}"


def put_s3_json(topic_id: str, run_id: str, subfolder: str, filename: str, data: Any) -> str:
    """Write JSON to S3 and return the s3:// URI."""
    import json
    key = s3_key(topic_id, run_id, subfolder, filename)
    get_s3().put_object(
        Bucket=_S3_BUCKET,
        Key=key,
        Body=json.dumps(data, default=str).encode(),
        ContentType="application/json",
    )
    return f"s3://{_S3_BUCKET}/{key}"


def get_s3_json(uri: str) -> Any:
    """Read a JSON object from an s3:// URI."""
    import json
    assert uri.startswith("s3://"), f"Expected s3:// URI, got: {uri}"
    rest = uri[5:]
    bucket, key = rest.split("/", 1)
    resp = get_s3().get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read())

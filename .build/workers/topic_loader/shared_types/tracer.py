"""
Trace event writer — every pipeline worker and API handler calls these functions
to write structured trace events to DynamoDB.

PK: RUN#<run_id>   SK: EVENT#<iso_timestamp>#<event_type>
"""
from __future__ import annotations

import os
from typing import Optional

import boto3
from boto3.dynamodb.types import TypeSerializer

from .models import TokenUsage, TraceEvent, utc_now

_serializer = TypeSerializer()

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ebook-platform-dev")


def _get_table():
    endpoint = os.environ.get("DYNAMODB_ENDPOINT")
    kwargs = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.resource("dynamodb", **kwargs).Table(_TABLE_NAME)


def _write(event: TraceEvent) -> None:
    table = _get_table()
    pk = f"RUN#{event.run_id}"
    sk = f"EVENT#{event.timestamp}#{event.event_type}"

    item: dict = {
        "PK": pk,
        "SK": sk,
        "event_type": event.event_type,
        "run_id": event.run_id,
        "timestamp": event.timestamp,
    }

    if event.stage:
        item["stage"] = event.stage
    if event.agent_name:
        item["agent_name"] = event.agent_name
    if event.model_name:
        item["model_name"] = event.model_name
    if event.token_usage:
        item["token_usage"] = event.token_usage.model_dump()
    if event.cost_usd is not None:
        item["cost_usd"] = str(event.cost_usd)  # DynamoDB Decimal-safe
    if event.error_message:
        item["error_message"] = event.error_message
    if event.error_classification:
        item["error_classification"] = event.error_classification
    if event.metadata:
        item["metadata"] = event.metadata

    # GSI2 fields for operational monitoring
    item["RUN_STATUS"] = f"RUN_STATUS#{event.event_type}"
    item["UPDATED_AT"] = event.timestamp

    table.put_item(Item=item)


# ── Public functions called by workers ───────────────────────────────────────


def stage_started(run_id: str, stage: str, agent_name: Optional[str] = None, **meta) -> None:
    _write(TraceEvent(
        run_id=run_id,
        event_type="STAGE_STARTED",
        stage=stage,
        agent_name=agent_name,
        metadata=meta,
    ))


def stage_completed(
    run_id: str,
    stage: str,
    agent_name: Optional[str] = None,
    model_name: Optional[str] = None,
    token_usage: Optional[TokenUsage] = None,
    cost_usd: Optional[float] = None,
    **meta,
) -> None:
    _write(TraceEvent(
        run_id=run_id,
        event_type="STAGE_COMPLETED",
        stage=stage,
        agent_name=agent_name,
        model_name=model_name,
        token_usage=token_usage,
        cost_usd=cost_usd,
        metadata=meta,
    ))


def stage_failed(
    run_id: str,
    stage: str,
    error_message: str,
    error_classification: str = "UNKNOWN",
    **meta,
) -> None:
    _write(TraceEvent(
        run_id=run_id,
        event_type="STAGE_FAILED",
        stage=stage,
        error_message=error_message,
        error_classification=error_classification,
        metadata=meta,
    ))


def run_triggered(run_id: str, topic_id: str, trigger_source: str, triggered_by: Optional[str] = None) -> None:
    _write(TraceEvent(
        run_id=run_id,
        event_type=f"RUN_TRIGGERED_{trigger_source.upper()}",
        metadata={"topic_id": topic_id, "triggered_by": triggered_by or ""},
    ))


def topic_event(run_id: str, event_type: str, topic_id: str, **meta) -> None:
    """General topic-level event: TOPIC_CREATED, TOPIC_UPDATED, TOPIC_DELETED, etc."""
    _write(TraceEvent(
        run_id=run_id,
        event_type=event_type,
        metadata={"topic_id": topic_id, **meta},
    ))

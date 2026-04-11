"""
Shared Pydantic models used by API handlers, workers, and the test harness.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────


class ScheduleType(str, Enum):
    manual = "manual"
    daily = "daily"
    weekly = "weekly"
    custom = "custom"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"


class ReviewDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class ModerationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TriggerSource(str, Enum):
    admin_manual = "admin_manual"
    schedule = "schedule"


# ── Topic models ──────────────────────────────────────────────────────────────


class TopicCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    instructions: str = Field(..., min_length=10)
    subtopics: list[str] = Field(default_factory=list)
    schedule_type: ScheduleType = ScheduleType.manual
    cron_expression: Optional[str] = None

    @field_validator("cron_expression")
    @classmethod
    def cron_required_for_custom(cls, v, info):
        if info.data.get("schedule_type") == ScheduleType.custom and not v:
            raise ValueError("cron_expression is required when schedule_type is 'custom'")
        return v


class TopicUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    instructions: Optional[str] = Field(None, min_length=10)
    subtopics: Optional[list[str]] = None
    schedule_type: Optional[ScheduleType] = None
    cron_expression: Optional[str] = None


class TopicRecord(BaseModel):
    """Full topic record as stored in DynamoDB META item."""
    topic_id: str
    title: str
    description: str
    instructions: str
    subtopics: list[str] = Field(default_factory=list)
    order: int = 0
    active: bool = True
    schedule_type: ScheduleType = ScheduleType.manual
    cron_expression: Optional[str] = None
    current_published_version: Optional[str] = None
    published_at: Optional[str] = None
    created_at: str
    updated_at: str


class TopicReorderRequest(BaseModel):
    order: list[str] = Field(..., min_length=1, description="Topic IDs in desired display order")


# ── Run models ────────────────────────────────────────────────────────────────


class RunRecord(BaseModel):
    run_id: str
    topic_id: str
    status: RunStatus = RunStatus.PENDING
    trigger_source: TriggerSource = TriggerSource.admin_manual
    triggered_by: Optional[str] = None
    execution_arn: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    cost_usd: float = 0.0


# ── Review models ─────────────────────────────────────────────────────────────


class ReviewRecord(BaseModel):
    run_id: str
    topic_id: str
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    task_token: Optional[str] = None
    draft_artifact_uri: Optional[str] = None
    diff_summary_uri: Optional[str] = None
    notes: Optional[str] = None
    reviewer: Optional[str] = None
    staged_at: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    timeout_at: Optional[str] = None


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecision
    notes: Optional[str] = Field(None, max_length=2000)


# ── Feedback models ───────────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    topic_id: str
    section_id: str
    comment_text: str = Field(..., min_length=1, max_length=5000)
    highlight_id: Optional[str] = None


class HighlightCreate(BaseModel):
    topic_id: str
    section_id: str
    selected_text: str = Field(..., min_length=1, max_length=2000)
    offset_start: int = Field(..., ge=0)
    offset_end: int = Field(..., ge=0)


class FeedbackRecord(BaseModel):
    feedback_id: str
    topic_id: str
    section_id: str
    feedback_type: str  # "comment" | "highlight"
    content: str
    moderation_status: ModerationStatus = ModerationStatus.PENDING
    created_at: str


# ── Trace event models ────────────────────────────────────────────────────────


class TokenUsage(BaseModel):
    prompt: int = 0
    completion: int = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion


class TraceEvent(BaseModel):
    run_id: str
    event_type: str  # STAGE_STARTED | STAGE_COMPLETED | STAGE_FAILED | RUN_TRIGGERED_* | etc.
    stage: Optional[str] = None
    agent_name: Optional[str] = None
    model_name: Optional[str] = None
    token_usage: Optional[TokenUsage] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    error_classification: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: dict = Field(default_factory=dict)


# ── Helper ────────────────────────────────────────────────────────────────────


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"

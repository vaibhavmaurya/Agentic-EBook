"""
Local development server — wraps all Lambda handlers as FastAPI routes.
Runs the exact same handler code that deploys to AWS Lambda.

Usage:
    cd services/api
    uvicorn local_dev_server:app --reload --port 8000

OpenAPI (Swagger) UI:  http://localhost:8000/docs
ReDoc UI:              http://localhost:8000/redoc
Raw OpenAPI JSON:      http://localhost:8000/openapi.json

AWS base URL (dev):    https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com
Auth: all /admin/* routes require  Authorization: Bearer <Cognito ID token>
      /public/* routes require no auth
"""
from __future__ import annotations

import os
from typing import Any, List, Literal, Optional

from dotenv import load_dotenv

# Load .env.local from repo root before importing handlers
_repo_root = os.path.join(os.path.dirname(__file__), "../..")
load_dotenv(os.path.join(_repo_root, ".env.local"))

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi  # noqa: F401 — used in custom_openapi()
from pydantic import BaseModel, Field

from topics import lambda_handler as topics_handler
from reviews import lambda_handler as reviews_handler
from public import lambda_handler as public_handler
from feedback import lambda_handler as feedback_handler


# ── Pydantic request / response models ───────────────────────────────────────

class SubtopicModel(BaseModel):
    id: str = Field(..., description="Unique subtopic identifier")
    title: str = Field(..., description="Subtopic heading")
    description: Optional[str] = None


class TopicCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Topic title shown in the ebook TOC")
    description: Optional[str] = Field(None, description="Brief summary of the topic")
    instructions: Optional[str] = Field(None, description="Agent instructions for researching and writing this topic")
    subtopics: Optional[List[SubtopicModel]] = Field(default_factory=list, description="Sub-sections within the topic")
    schedule_type: Literal["manual", "daily", "weekly", "custom"] = Field(
        "manual", description="How often the pipeline should run for this topic"
    )
    cron_expression: Optional[str] = Field(None, description="Required when schedule_type=custom. EventBridge cron syntax e.g. cron(0 6 ? * MON *)")

    model_config = {"json_schema_extra": {"example": {
        "title": "Introduction to Retrieval-Augmented Generation",
        "description": "A practical guide to RAG architectures, embedding models, and vector databases.",
        "instructions": "Focus on real-world production use-cases. Include code examples. Target audience: senior ML engineers.",
        "subtopics": [
            {"id": "sub-01", "title": "What is RAG?"},
            {"id": "sub-02", "title": "Choosing an embedding model"},
            {"id": "sub-03", "title": "Vector database comparison"},
        ],
        "schedule_type": "weekly",
    }}}


class TopicUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    subtopics: Optional[List[SubtopicModel]] = None
    schedule_type: Optional[Literal["manual", "daily", "weekly", "custom"]] = None
    cron_expression: Optional[str] = None
    active: Optional[bool] = None


class ReorderEntry(BaseModel):
    topic_id: str
    order: int = Field(..., ge=1)


class TopicReorderRequest(BaseModel):
    topics: List[ReorderEntry] = Field(..., min_length=1)

    model_config = {"json_schema_extra": {"example": {
        "topics": [
            {"topic_id": "abc123", "order": 1},
            {"topic_id": "def456", "order": 2},
        ]
    }}}


class TopicResponse(BaseModel):
    topic_id: str
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    subtopics: List[Any] = []
    schedule_type: str
    cron_expression: Optional[str] = None
    active: bool
    order: int
    created_at: str
    updated_at: str
    current_published_version: Optional[str] = None
    last_run_id: Optional[str] = None
    last_run_status: Optional[str] = None


class TopicCreateResponse(BaseModel):
    topic_id: str
    message: str = "Topic created."


class TriggerResponse(BaseModel):
    run_id: str
    execution_arn: str
    message: str = "Pipeline triggered."


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"] = Field(..., description="Approve or reject the staged draft")
    notes: Optional[str] = Field(None, max_length=2000, description="Optional reviewer notes stored with the decision")

    model_config = {"json_schema_extra": {"example": {"decision": "approve", "notes": "Content looks good. Minor typos fixed."}}}


class ReviewResponse(BaseModel):
    review_id: str
    topic_id: str
    run_id: str
    review_status: str
    draft_artifact_uri: Optional[str] = None
    diff_summary_uri: Optional[str] = None
    scorecard: Optional[Any] = None
    notes: Optional[str] = None
    reviewer: Optional[str] = None
    created_at: str
    updated_at: str
    timeout_at: Optional[str] = None


class CommentRequest(BaseModel):
    topic_id: str = Field(..., description="ID of the topic being commented on")
    comment_text: str = Field(..., min_length=1, max_length=2000)
    section_id: Optional[str] = Field(None, description="Anchor ID of the section in the rendered HTML")
    highlight_id: Optional[str] = Field(None, description="Linked highlight ID if this comment annotates a selection")

    model_config = {"json_schema_extra": {"example": {
        "topic_id": "abc123",
        "comment_text": "Great explanation of vector quantization — could use a diagram.",
        "section_id": "vector-quantization",
    }}}


class CommentResponse(BaseModel):
    comment_id: str
    status: Literal["PENDING"] = "PENDING"


class HighlightRequest(BaseModel):
    topic_id: str = Field(..., description="ID of the topic being highlighted")
    selected_text: str = Field(..., min_length=1, max_length=500, description="The exact text the reader selected")
    section_id: Optional[str] = Field(None, description="Anchor ID of the containing section")
    offset_start: Optional[int] = Field(None, description="Character offset of selection start within the section")
    offset_end: Optional[int] = Field(None, description="Character offset of selection end within the section")

    model_config = {"json_schema_extra": {"example": {
        "topic_id": "abc123",
        "selected_text": "RAG combines parametric and non-parametric memory",
        "section_id": "what-is-rag",
        "offset_start": 42,
        "offset_end": 90,
    }}}


class HighlightResponse(BaseModel):
    highlight_id: str
    status: Literal["PENDING"] = "PENDING"


class ReleaseItem(BaseModel):
    topic_id: str
    title: str
    version: str
    published_at: str
    release_notes: Optional[str] = None


class ReleasesResponse(BaseModel):
    releases: List[ReleaseItem]
    count: int


class RunSummary(BaseModel):
    run_id: str
    status: str
    trigger_source: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cost_usd_total: Optional[float] = None
    error_message: Optional[str] = None


class TraceEvent(BaseModel):
    event_type: str
    stage: Optional[str] = None
    timestamp: str
    token_usage: Optional[Any] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    error_classification: Optional[str] = None


class RunDetailResponse(BaseModel):
    run_id: str
    topic_id: str
    status: str
    trigger_source: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cost_usd_total: Optional[float] = None
    stage_costs: Optional[Any] = None
    events: List[TraceEvent] = []


class FeedbackItem(BaseModel):
    feedback_id: str
    feedback_type: Literal["COMMENT", "HIGHLIGHT"]
    topic_id: str
    section_id: Optional[str] = None
    comment_text: Optional[str] = None
    selected_text: Optional[str] = None
    moderation_status: str
    created_at: str


class TopicFeedbackSummary(BaseModel):
    topic_id: str
    comment_count: int
    highlight_count: int
    pending_count: int
    recent_items: List[FeedbackItem] = []


class FeedbackSummaryResponse(BaseModel):
    topics: List[TopicFeedbackSummary]
    total_feedback: int


class ErrorResponse(BaseModel):
    error: str
    message: str


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agentic Ebook Platform API",
    description="""
## Overview

REST API for the Agentic Ebook Platform. Manages topic lifecycle, AI-driven
content pipelines, admin review/approval, incremental publishing, and reader feedback.

## Authentication

All `/admin/*` routes require a **Cognito ID token** passed as a Bearer token:

```
Authorization: Bearer <id_token>
```

Obtain a token via the Cognito hosted UI or:

```bash
aws cognito-idp initiate-auth \\
  --auth-flow USER_PASSWORD_AUTH \\
  --auth-parameters USERNAME=<email>,PASSWORD=<pass> \\
  --client-id <client_id> \\
  --region us-east-1 \\
  --query 'AuthenticationResult.IdToken' --output text
```

`/public/*` routes require no authentication.

## Environments

| Environment | Base URL |
|---|---|
| **Local dev** | `http://localhost:8000` |
| **AWS dev** | `https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com` |

## Pipeline Flow

`POST /admin/topics/{topicId}/trigger` → Step Functions executes the AI pipeline
→ pauses at **WaitForApproval** → admin reviews at `GET /admin/topics/{topicId}/review/{runId}`
→ `POST` with `decision: approve` → content published → appears in `GET /public/releases/latest`
""",
    version="1.0.0",
    servers=[
        {"url": "http://localhost:8000", "description": "Local dev (uvicorn)"},
        {"url": "https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com", "description": "AWS dev"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Custom OpenAPI schema — adds CognitoJWT security to all /admin/* routes ──

def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["CognitoJWT"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Cognito ID token — obtain via `aws cognito-idp initiate-auth`",
    }
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/admin"):
            for operation in methods.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"CognitoJWT": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[method-assign]


# ── Lambda event builder ──────────────────────────────────────────────────────

def _build_lambda_event(request: Request, body: bytes, path_params: dict) -> dict:
    """Convert a FastAPI request into an API Gateway HTTP API payload format 2.0 event."""
    return {
        "rawPath": request.url.path,
        "rawQueryString": str(request.url.query),
        "headers": dict(request.headers),
        "pathParameters": path_params,
        "queryStringParameters": dict(request.query_params),
        "body": body.decode("utf-8") if body else None,
        "isBase64Encoded": False,
        "requestContext": {
            "http": {
                "method": request.method,
                "path": request.url.path,
            },
            # Simulate a logged-in admin for local dev — real JWT validation in AWS
            "authorizer": {
                "jwt": {
                    "claims": {
                        "email": os.environ.get("ADMIN_USERNAME", "dev@local"),
                        "sub": "local-dev-user",
                    }
                }
            },
        },
    }


def _lambda_response(result: dict) -> Response:
    return Response(
        content=result.get("body", ""),
        status_code=result.get("statusCode", 200),
        headers={k: v for k, v in (result.get("headers") or {}).items()},
        media_type="application/json",
    )


# ── Admin — Topic CRUD ────────────────────────────────────────────────────────

@app.get(
    "/admin/topics",
    response_model=dict,
    tags=["Topics"],
    summary="List all active topics",
    description="Returns all active topics sorted by their display order.",
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def list_topics(request: Request):
    body = await request.body()
    return _lambda_response(topics_handler(_build_lambda_event(request, body, {}), None))


@app.post(
    "/admin/topics",
    response_model=TopicCreateResponse,
    status_code=201,
    tags=["Topics"],
    summary="Create a new topic",
    description="Creates a topic and optionally registers an EventBridge schedule if `schedule_type` is not `manual`.",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def create_topic(payload: TopicCreateRequest, request: Request):
    event = _build_lambda_event(request, b"", {})
    event["body"] = payload.model_dump_json()
    return _lambda_response(topics_handler(event, None))


@app.get(
    "/admin/topics/{topic_id}",
    response_model=TopicResponse,
    tags=["Topics"],
    summary="Get a single topic",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_topic(topic_id: str, request: Request):
    body = await request.body()
    return _lambda_response(topics_handler(_build_lambda_event(request, body, {"topicId": topic_id}), None))


@app.put(
    "/admin/topics/{topic_id}",
    response_model=TopicResponse,
    tags=["Topics"],
    summary="Update a topic",
    description="Partial update — only supplied fields are changed. Updating `schedule_type` upserts the EventBridge schedule.",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_topic(topic_id: str, payload: TopicUpdateRequest, request: Request):
    event = _build_lambda_event(request, b"", {"topicId": topic_id})
    event["body"] = payload.model_dump_json(exclude_none=True)
    return _lambda_response(topics_handler(event, None))


@app.delete(
    "/admin/topics/{topic_id}",
    tags=["Topics"],
    summary="Soft-delete a topic",
    description="Sets `active=false`. The topic is retained in DynamoDB and excluded from future runs and publishing.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_topic(topic_id: str, request: Request):
    body = await request.body()
    return _lambda_response(topics_handler(_build_lambda_event(request, body, {"topicId": topic_id}), None))


@app.put(
    "/admin/topics/reorder",
    tags=["Topics"],
    summary="Reorder topics",
    description="Updates the display order of multiple topics in a single call.",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def reorder_topics(payload: TopicReorderRequest, request: Request):
    event = _build_lambda_event(request, b"", {})
    event["body"] = payload.model_dump_json()
    return _lambda_response(topics_handler(event, None))


# ── Admin — Pipeline trigger ──────────────────────────────────────────────────

@app.post(
    "/admin/topics/{topic_id}/trigger",
    response_model=TriggerResponse,
    status_code=202,
    tags=["Pipeline"],
    summary="Manually trigger the AI pipeline for a topic",
    description="""Starts a Step Functions execution for the topic.

The pipeline runs through these stages:
1. **LoadTopicConfig** — loads topic metadata
2. **AssembleTopicContext** — builds research context
3. **PlanTopic** → **ResearchTopic** → **VerifyEvidence** (AI agents)
4. **PersistEvidenceArtifacts** — writes raw research to S3
5. **DraftChapter** → **EditorialReview** (AI agents)
6. **BuildDraftArtifact** — stages HTML/JSON to S3
7. **GenerateDiffReleaseNotes** — compares to prior published version
8. **NotifyAdminForReview** — sends email, pauses pipeline
9. **WaitForApproval** — pipeline pauses here until admin approves/rejects

Use `GET /admin/topics/{topicId}/review/{runId}` to review the draft.
""",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def trigger_run(topic_id: str, request: Request):
    body = await request.body()
    return _lambda_response(topics_handler(_build_lambda_event(request, body, {"topicId": topic_id}), None))


# ── Admin — Run history ───────────────────────────────────────────────────────

@app.get(
    "/admin/topics/{topic_id}/runs",
    response_model=dict,
    tags=["Run History"],
    summary="List pipeline runs for a topic",
    description="Returns all runs for the topic, newest first, with status and total cost.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_runs(topic_id: str, request: Request):
    body = await request.body()
    return _lambda_response(topics_handler(_build_lambda_event(request, body, {"topicId": topic_id}), None))


@app.get(
    "/admin/topics/{topic_id}/runs/{run_id}",
    response_model=RunDetailResponse,
    tags=["Run History"],
    summary="Get run detail with trace events",
    description="Returns the full trace event log for a single run, including per-stage token usage and cost.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_run(topic_id: str, run_id: str, request: Request):
    body = await request.body()
    return _lambda_response(topics_handler(_build_lambda_event(request, body, {"topicId": topic_id, "runId": run_id}), None))


# ── Admin — Review and approval ───────────────────────────────────────────────

@app.get(
    "/admin/reviews",
    tags=["Review & Approval"],
    summary="List all pending reviews",
    description="Returns all drafts currently waiting for admin approval across all topics.",
    responses={401: {"model": ErrorResponse}},
)
async def list_reviews(request: Request):
    body = await request.body()
    return _lambda_response(reviews_handler(_build_lambda_event(request, body, {}), None))


@app.get(
    "/admin/topics/{topic_id}/review/{run_id}",
    response_model=ReviewResponse,
    tags=["Review & Approval"],
    summary="Get a draft review",
    description="""Returns the staged draft for admin inspection before approve/reject.

Response includes:
- `draft_artifact_uri` — S3 URI of the staged HTML/JSON to render in the UI
- `diff_summary_uri` — S3 URI of the diff vs prior published version
- `scorecard` — editorial quality scores from the Editor agent
""",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_review(topic_id: str, run_id: str, request: Request):
    body = await request.body()
    return _lambda_response(reviews_handler(_build_lambda_event(request, body, {"topicId": topic_id, "runId": run_id}), None))


@app.post(
    "/admin/topics/{topic_id}/review/{run_id}",
    tags=["Review & Approval"],
    summary="Approve or reject a draft",
    description="""Resumes the paused Step Functions execution.

- **approve**: pipeline continues to `PublishTopic` → `RebuildIndexes`
- **reject**: pipeline ends without publishing; draft is retained in S3

The `notes` field is stored with the review record and visible in the run history UI.
""",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def submit_review(topic_id: str, run_id: str, payload: ReviewDecisionRequest, request: Request):
    event = _build_lambda_event(request, b"", {"topicId": topic_id, "runId": run_id})
    event["body"] = payload.model_dump_json()
    return _lambda_response(reviews_handler(event, None))


# ── Admin — Feedback ──────────────────────────────────────────────────────────

@app.get(
    "/admin/feedback/summary",
    response_model=FeedbackSummaryResponse,
    tags=["Feedback"],
    summary="Feedback summary across all topics",
    description="Returns comment and highlight counts per topic, with up to 10 recent items each.",
    responses={401: {"model": ErrorResponse}},
)
async def feedback_summary(request: Request):
    body = await request.body()
    return _lambda_response(feedback_handler(_build_lambda_event(request, body, {}), None))


@app.get(
    "/admin/topics/{topic_id}/feedback",
    tags=["Feedback"],
    summary="List feedback for a topic",
    description="Returns all comments and highlights for a topic, newest first.",
    responses={401: {"model": ErrorResponse}},
)
async def list_topic_feedback(
    topic_id: str,
    request: Request,
    _feedback_type: Optional[Literal["COMMENT", "HIGHLIGHT"]] = Query(None, alias="type", description="Filter by feedback type"),
    _limit: int = Query(100, ge=1, le=500, description="Maximum items to return"),
):
    body = await request.body()
    return _lambda_response(feedback_handler(_build_lambda_event(request, body, {"topicId": topic_id}), None))


# ── Public routes ─────────────────────────────────────────────────────────────

@app.post(
    "/public/comments",
    response_model=CommentResponse,
    status_code=201,
    tags=["Public (no auth)"],
    summary="Submit a reader comment",
    description="Stores a reader comment with `moderation_status=PENDING`. Comments are visible to admins via `/admin/topics/{topicId}/feedback`.",
    responses={400: {"model": ErrorResponse}},
)
async def post_comment(payload: CommentRequest, request: Request):
    event = _build_lambda_event(request, b"", {})
    event["body"] = payload.model_dump_json()
    return _lambda_response(public_handler(event, None))


@app.post(
    "/public/highlights",
    response_model=HighlightResponse,
    status_code=201,
    tags=["Public (no auth)"],
    summary="Submit a text highlight",
    description="Stores a reader text selection with `moderation_status=PENDING`.",
    responses={400: {"model": ErrorResponse}},
)
async def post_highlight(payload: HighlightRequest, request: Request):
    event = _build_lambda_event(request, b"", {})
    event["body"] = payload.model_dump_json()
    return _lambda_response(public_handler(event, None))


@app.get(
    "/public/releases/latest",
    response_model=ReleasesResponse,
    tags=["Public (no auth)"],
    summary="Get recently published topics",
    description=f"Returns up to 20 most recently published topic versions. No authentication required.",
    responses={500: {"model": ErrorResponse}},
)
async def get_releases(request: Request):
    body = await request.body()
    return _lambda_response(public_handler(_build_lambda_event(request, body, {}), None))


# ── Health check ──────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Returns `{status: ok}`. Useful for load balancer health probes.",
)
async def health():
    return {"status": "ok", "env": os.environ.get("ENV", "local")}

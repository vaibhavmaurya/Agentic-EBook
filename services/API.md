# API Reference — Agentic Ebook Platform V3

All requests go through API Gateway at the base URL stored in `.env.local` as `ADMIN_API_BASE_URL` (local) or the Terraform output `api_endpoint` (AWS).

---

## Authentication

All `/admin/*` endpoints require a Cognito JWT in the `Authorization` header.

### Get a token (local dev / notebook)

```python
import boto3, os

cognito = boto3.client("cognito-idp", region_name=os.environ["AWS_REGION"])
resp = cognito.initiate_auth(
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={
        "USERNAME": os.environ["ADMIN_USERNAME"],
        "PASSWORD": os.environ["ADMIN_PASSWORD"],
    },
    ClientId=os.environ["COGNITO_CLIENT_ID"],
)
token = resp["AuthenticationResult"]["IdToken"]
headers = {"Authorization": f"Bearer {token}"}
```

### Get a token (curl)

```bash
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=vaibhavmaurya1986@gmail.com,PASSWORD=EbookAdmin2026! \
  --client-id 5g3o4juiad2ils16v48iuu119i \
  --query "AuthenticationResult.IdToken" --output text)
```

---

## Base URLs

| Environment | Base URL |
|---|---|
| Local dev | `http://localhost:8000` |
| AWS dev | `https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com` |

---

## Admin API — Topics

### `GET /admin/topics`

List all active topics sorted by `order`.

**Auth:** Required

**Response 200:**
```json
{
  "topics": [
    {
      "topic_id": "uuid",
      "title": "Introduction to LLMs",
      "description": "...",
      "order": 1,
      "active": true,
      "schedule_type": "manual",
      "last_run_status": "APPROVED",
      "last_run_at": "2026-04-10T12:00:00Z"
    }
  ]
}
```

**Test (curl):**
```bash
curl -H "Authorization: Bearer $TOKEN" $BASE_URL/admin/topics
```

---

### `POST /admin/topics`

Create a new topic.

**Auth:** Required

**Request body:**
```json
{
  "title": "Introduction to LLMs",
  "description": "A comprehensive overview of large language models.",
  "instructions": "Focus on practical applications. Avoid heavy math. Use diagrams.",
  "subtopics": ["Transformer architecture", "Training at scale", "Prompt engineering"],
  "schedule_type": "manual",
  "cron_expression": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | Yes | 3–200 chars |
| `description` | string | Yes | 10–2000 chars |
| `instructions` | string | Yes | Injected into agent prompts |
| `subtopics` | list[string] | No | Suggested section headings |
| `schedule_type` | string | Yes | `manual`, `daily`, `weekly`, `custom` |
| `cron_expression` | string | No | Required when `schedule_type=custom` |

**Response 201:**
```json
{ "topic_id": "uuid" }
```

**Test (curl):**
```bash
curl -X POST $BASE_URL/admin/topics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Topic","description":"A test topic.","instructions":"Be concise.","schedule_type":"manual"}'
```

---

### `GET /admin/topics/{topicId}`

Get a single topic with its last run summary.

**Auth:** Required

**Response 200:**
```json
{
  "topic_id": "uuid",
  "title": "...",
  "description": "...",
  "instructions": "...",
  "subtopics": [],
  "order": 1,
  "active": true,
  "schedule_type": "manual",
  "cron_expression": null,
  "created_at": "2026-04-10T12:00:00Z",
  "updated_at": "2026-04-10T12:00:00Z",
  "last_run": {
    "run_id": "uuid",
    "status": "APPROVED",
    "started_at": "2026-04-10T12:00:00Z",
    "cost_usd": 0.12
  }
}
```

---

### `PUT /admin/topics/{topicId}`

Update an existing topic. Only fields included in the body are updated.

**Auth:** Required

**Request body:** Same fields as `POST /admin/topics` (all optional).

**Response 200:**
```json
{ "topic_id": "uuid", "updated_at": "2026-04-10T12:05:00Z" }
```

---

### `DELETE /admin/topics/{topicId}`

Soft-delete a topic — sets `active=false`. The topic is retained in DynamoDB and excluded from future pipeline runs and publishing.

**Auth:** Required

**Response 200:**
```json
{ "topic_id": "uuid", "active": false }
```

---

### `PUT /admin/topics/reorder`

Update the display order of multiple topics in one call.

**Auth:** Required

**Request body:**
```json
{
  "order": ["topic-uuid-1", "topic-uuid-3", "topic-uuid-2"]
}
```

The array position determines the new `order` value (index 0 = order 1).

**Response 200:**
```json
{ "updated": 3 }
```

---

## Admin API — Trigger

### `POST /admin/topics/{topicId}/trigger`

Manually trigger a pipeline run for a topic.

**Auth:** Required

**Response 202:**
```json
{
  "run_id": "uuid",
  "execution_arn": "arn:aws:states:us-east-1:...:execution:...:uuid"
}
```

---

## Admin API — Review

### `GET /admin/topics/{topicId}/review/{runId}`

Fetch the staged draft, diff summary, and run metadata for admin review.

**Auth:** Required

**Response 200:**
```json
{
  "run_id": "uuid",
  "topic_id": "uuid",
  "review_status": "PENDING_REVIEW",
  "draft_artifact_uri": "s3://ebook-platform-artifacts-dev/topics/.../review/draft.html",
  "diff_summary_uri": "s3://ebook-platform-artifacts-dev/topics/.../diff/summary.json",
  "staged_at": "2026-04-10T14:00:00Z",
  "timeout_at": "2026-04-13T14:00:00Z"
}
```

---

### `POST /admin/topics/{topicId}/review/{runId}`

Approve or reject a staged draft. Resumes the Step Functions execution via task token callback.

**Auth:** Required

**Request body:**
```json
{
  "decision": "approve",
  "notes": "Looks good, publish it."
}
```

`decision` must be `"approve"` or `"reject"`.

**Response 200:**
```json
{ "decision": "approve", "run_id": "uuid" }
```

---

## Admin API — History & Feedback

### `GET /admin/topics/{topicId}/runs`

List all pipeline runs for a topic.

**Auth:** Required

**Response 200:**
```json
{
  "runs": [
    {
      "run_id": "uuid",
      "status": "APPROVED",
      "trigger_source": "admin_manual",
      "started_at": "2026-04-10T12:00:00Z",
      "completed_at": "2026-04-10T12:45:00Z",
      "cost_usd": 0.14
    }
  ]
}
```

---

### `GET /admin/topics/{topicId}/runs/{runId}`

Get full trace event timeline for a run (stage-by-stage breakdown).

**Auth:** Required

**Response 200:**
```json
{
  "run_id": "uuid",
  "status": "APPROVED",
  "cost_usd": 0.14,
  "events": [
    {
      "event_type": "STAGE_COMPLETED",
      "stage": "PlanTopic",
      "agent_name": "planner",
      "model": "gpt-4o-mini",
      "token_usage": { "prompt": 800, "completion": 200 },
      "cost_usd": 0.001,
      "timestamp": "2026-04-10T12:01:00Z"
    }
  ]
}
```

---

### `GET /admin/feedback/summary`

Aggregated reader feedback grouped by topic.

**Auth:** Required

**Response 200:**
```json
{
  "topics": [
    {
      "topic_id": "uuid",
      "title": "Introduction to LLMs",
      "comment_count": 4,
      "highlight_count": 12,
      "pending_moderation": 2
    }
  ]
}
```

---

## Public API — Reader Feedback

No authentication required. Rate-limited at API Gateway level.

### `POST /public/comments`

Submit a reader comment on a topic section.

**Request body:**
```json
{
  "topic_id": "uuid",
  "section_id": "transformer-architecture",
  "comment_text": "Great explanation of attention heads!",
  "highlight_id": "uuid-optional"
}
```

**Response 201:**
```json
{ "comment_id": "uuid" }
```

---

### `POST /public/highlights`

Submit a text highlight from a topic section.

**Request body:**
```json
{
  "topic_id": "uuid",
  "section_id": "transformer-architecture",
  "selected_text": "The attention mechanism allows the model to...",
  "offset_start": 142,
  "offset_end": 198
}
```

**Response 201:**
```json
{ "highlight_id": "uuid" }
```

---

### `GET /public/releases/latest`

Get the most recently published topics (for the release notes page).

**Response 200:**
```json
{
  "releases": [
    {
      "topic_id": "uuid",
      "title": "Introduction to LLMs",
      "version": "v002",
      "published_at": "2026-04-10T15:00:00Z",
      "changelog": "Added section on RLHF. Updated references."
    }
  ]
}
```

---

## Running the Local Dev Server

```bash
# From repo root
cd services/api
pip install -r requirements.txt
uvicorn local_dev_server:app --reload --port 8000
```

The local server wraps the same Lambda handler functions — no code differences between local and AWS.

Once running, the OpenAPI docs are available at: `http://localhost:8000/docs`

---

## Testing with the Jupyter Notebook

The full end-to-end test sequence (UC-01 → UC-15) is in `notebooks/ebook_platform_test_harness.ipynb`.

Run it in order:
```bash
cd notebooks
pip install -r requirements.txt
jupyter notebook ebook_platform_test_harness.ipynb
```

Each cell group maps to one use case. Cell Group 16 (PURGE) cleans up all test data.

---

## Error Response Format

All errors return a consistent JSON body:

```json
{
  "error": "TOPIC_NOT_FOUND",
  "message": "Topic uuid does not exist or has been deleted.",
  "request_id": "..."
}
```

| HTTP Status | Error code | Meaning |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid request body |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 404 | `TOPIC_NOT_FOUND` | Topic/run/review not found |
| 409 | `CONFLICT` | Run already in progress for topic |
| 422 | `INVALID_DECISION` | Review decision not approve/reject |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

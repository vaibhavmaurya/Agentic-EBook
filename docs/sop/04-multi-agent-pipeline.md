# SOP 04 — Multi-Agent Pipeline Design

## Purpose

Building a reliable multi-agent AI pipeline requires more than prompt engineering. This SOP covers the architecture decisions — provider isolation, model routing, tracing, error handling, and human-in-the-loop — that make a pipeline debuggable, maintainable, and cost-controlled.

---

## Provider Isolation — The Single Most Important Pattern

**Rule: Only one module may import the AI provider SDK. All other code calls stable internal functions.**

```
services/
  openai-runtime/
    __init__.py        ← exports: run_planner_agent(), run_research_agent(), ...
    adapter.py         ← wraps OpenAI Responses API
    agents/
      planner.py
      research.py
      writer.py
      editor.py
      verifier.py
      diff.py
  workers/
    planner_worker.py  ← calls run_planner_agent() — NO openai import
    research_worker.py ← calls run_research_agent() — NO openai import
```

**Why this matters:**
- OpenAI → Anthropic swap requires changing exactly one module
- Workers are testable without an OpenAI key by mocking the `openai_runtime` functions
- Dependency management: `openai` package is listed in one `requirements.txt`
- Clear ownership: if something is wrong with the AI call, it's in `openai_runtime/`

**Enforcement:** add this to `CLAUDE.md` as a non-negotiable rule with the exact phrasing "Never add `import openai` or `from openai import ...` anywhere except `services/openai-runtime/`."

### The Internal API Contract

The functions exposed by `openai_runtime/__init__.py` are the stable contract:

```python
def run_planner_agent(topic_context: dict) -> dict:          ...
def run_research_agent(research_plan: dict) -> dict:         ...
def run_verifier_agent(evidence_set: dict) -> dict:          ...
def run_writer_agent(evidence: dict, style_guide: str) -> dict: ...
def run_editor_agent(draft: dict, instructions: str) -> dict:   ...
def run_diff_agent(prior_version: dict, new_draft: dict) -> dict: ...
```

These signatures are simple Python dicts — not OpenAI-specific types. Workers never deal with OpenAI response objects.

---

## Model Routing

Not all pipeline stages need the same model. Misrouting is expensive.

| Agent | Model | Reason |
|---|---|---|
| Planner | `gpt-4o-mini` | Structured output, limited token volume, not quality-critical |
| Research | `gpt-4o` | Long context, multi-step web research, quality matters |
| Verifier | `gpt-4o-mini` | Structured output, evidence scoring — mechanical task |
| Writer | `gpt-4o` | Long-form content generation, quality-critical |
| Editor | `gpt-4o` | Long context (reads entire draft), quality-critical |
| Diff / Release Notes | `gpt-4o-mini` | Structural comparison, low creativity required |

**Decision framework:**
- Use cheaper model if: task is structured, output is JSON/schema-constrained, quality is not reader-facing
- Use expensive model if: task produces long-form text readers will read, requires nuanced judgment, or processes long documents

**Make model routing configurable.** Store model assignments in a `model_config.yaml` uploaded to S3, not hardcoded. This lets you change routing without a code deploy.

---

## Structured Outputs — The Pipeline Contract

Every agent should return a typed, schema-validated output. This provides a verifiable contract between pipeline stages.

**Pattern:**

```python
from pydantic import BaseModel

class ResearchPlan(BaseModel):
    subtopics: list[str]
    source_classes: list[str]
    estimated_sources: int
    instructions: str

# In the research agent
response = client.responses.parse(
    model="gpt-4o",
    input=[...],
    text_format=ResearchPlan,
)
plan: ResearchPlan = response.output_parsed
```

Step Functions receives the serialized plan as JSON. The next stage deserializes it. If a stage outputs malformed JSON, the pipeline fails fast with a clear error — not silently corrupted data 3 stages later.

---

## Trace Events — Non-Negotiable for Debugging

Every pipeline worker must emit three trace event types. This is the primary debugging tool when a run fails.

```python
# At the very top of the handler — before any work
write_trace_event(table, run_id, "STAGE_STARTED", {
    "stage_name": "ResearchTopic",
    "agent_name": "ResearchAgent",
    "model_name": "gpt-4o"
})

# After successful agent call
write_trace_event(table, run_id, "STAGE_COMPLETED", {
    "stage_name": "ResearchTopic",
    "token_usage_prompt": usage.input_tokens,
    "token_usage_completion": usage.output_tokens,
    "cost_usd": calculate_cost(usage),
    "duration_ms": elapsed_ms
})

# In the exception handler
write_trace_event(table, run_id, "STAGE_FAILED", {
    "stage_name": "ResearchTopic",
    "error_message": str(e),
    "error_classification": classify_error(e)  # RATE_LIMIT, TIMEOUT, INVALID_OUTPUT, etc.
})
```

**DynamoDB trace event schema:**
- PK: `RUN#<run_id>`
- SK: `EVENT#<iso_timestamp>#<event_type>`

The timestamp in the SK ensures events sort chronologically. The event_type in the SK allows filtering without a scan.

**Without trace events, you cannot debug a failed run.** Step Functions shows which state failed, but not why. CloudWatch shows Lambda logs, but they're unstructured. Trace events give you a structured timeline with context.

---

## Cost Tracking Per Run

Track token usage and cost in every trace event. This enables:
- Run history cost dashboard
- Per-topic cost analysis
- Budget alerting

```python
# OpenAI pricing (verify current prices)
COST_PER_1K_TOKENS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_1K_TOKENS.get(model, {"input": 0, "output": 0})
    return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])
```

Store `cost_usd` as a number (not string) in DynamoDB so you can sum it across stages.

---

## Error Classification

Don't just log the raw exception. Classify errors so they're actionable.

```python
def classify_error(e: Exception) -> str:
    msg = str(e).lower()
    if "rate limit" in msg or "429" in msg:
        return "RATE_LIMIT"
    if "timeout" in msg or "timed out" in msg:
        return "TIMEOUT"
    if "invalid" in msg and "json" in msg:
        return "INVALID_OUTPUT"
    if "context length" in msg or "token" in msg:
        return "CONTEXT_OVERFLOW"
    return "UNKNOWN"
```

Error classification enables:
- Automatic retry logic for RATE_LIMIT (with exponential backoff)
- Different admin notification messages per error type
- Error trend analysis across runs

---

## Step Functions Pipeline Design

### State Naming Convention

Use `PascalCase` verb-noun for state names: `LoadTopicConfig`, `ResearchTopic`, `NotifyAdminForReview`. This matches Step Functions console display and makes ASL readable.

### Result Path Configuration

Use `ResultPath` to add each stage's output to the pipeline state without overwriting previous outputs:

```json
{
  "LoadTopicConfig": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:...:function:ebook-topic-loader",
    "ResultPath": "$.topic_config",
    "Next": "AssembleTopicContext"
  }
}
```

This accumulates context through the pipeline. Later stages can reference `$.topic_config.instructions` from an earlier stage.

### Error Handling at the State Level

```json
{
  "ResearchTopic": {
    "Type": "Task",
    "Resource": "...",
    "Catch": [{
      "ErrorEquals": ["States.ALL"],
      "Next": "HandleFailure",
      "ResultPath": "$.error"
    }],
    "Retry": [{
      "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
      "IntervalSeconds": 2,
      "MaxAttempts": 3,
      "BackoffRate": 2
    }]
  }
}
```

Add retry for transient Lambda errors (cold start failures, rate limits). Route all uncaught errors to a `HandleFailure` state that writes a `STAGE_FAILED` trace event and marks the run as FAILED in DynamoDB.

---

## Human-in-the-Loop — Complete Implementation Pattern

### Step 1: WaitForApproval State in ASL

```json
{
  "WaitForApproval": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
    "Parameters": {
      "FunctionName": "ebook-approval-worker",
      "Payload": {
        "task_token.$": "$$.Task.Token",
        "input.$": "$"
      }
    },
    "TimeoutSeconds": 259200,
    "HeartbeatSeconds": 3600,
    "Next": "CheckApprovalResult"
  }
}
```

### Step 2: Approval Worker Stores Token

```python
def handler(event, context):
    # IMPORTANT: unwrap the input — SFN wraps it
    task_token = event["task_token"]
    payload = event["input"]          # ← event["input"], not event directly

    topic_id = payload["topic_id"]
    run_id = payload["run_id"]

    # Store token in DynamoDB for the approval API to retrieve
    table.put_item(Item={
        "PK": f"TOPIC#{topic_id}",
        "SK": f"REVIEW#{run_id}",
        "task_token": task_token,
        "review_status": "PENDING",
        "timeout_at": (datetime.utcnow() + timedelta(hours=72)).isoformat(),
    })

    # Notify admin via SES
    send_review_notification(topic_id, run_id)
```

### Step 3: Approval API Sends Token Result

```python
def approve_run(topic_id, run_id, decision, notes):
    # Read the stored token
    review = table.get_item(Key={"PK": f"TOPIC#{topic_id}", "SK": f"REVIEW#{run_id}"})["Item"]
    token = review["task_token"]

    try:
        if decision == "approve":
            sfn.send_task_success(
                taskToken=token,
                output=json.dumps({"approved": True, "notes": notes})
            )
        else:
            sfn.send_task_failure(
                taskToken=token,
                error="REJECTED",
                cause=notes
            )
    except sfn.exceptions.TaskTimedOut:
        return response_409("TASK_EXPIRED")
    except sfn.exceptions.InvalidToken:
        return response_409("INVALID_TOKEN")
```

---

## Cost Control in Development

- Set `max_search_results=3` in Research Agent for dev runs (not the production default of 10-15)
- Use `gpt-4o-mini` for ALL dev runs regardless of agent role (switch to proper routing for integration tests only)
- Set an OpenAI spend limit in the OpenAI dashboard — this catches runaway loops
- Use Step Functions Local (`docker run -p 8083:8083 amazon/aws-stepfunctions-local`) to iterate on ASL without Step Functions API costs
- Purge test run data after every notebook test cycle to avoid orphaned resources accumulating cost

---

## Research Agent Tool Design

The Research Agent needs web tools. Design them as thin wrappers with clear contracts:

```python
def search_web(query: str, max_results: int = 10) -> list[dict]:
    """Returns list of {url, title, snippet, published_date}"""

def fetch_url(url: str) -> dict:
    """Returns {url, content_markdown, word_count, fetch_timestamp}"""

def score_source(metadata: dict) -> float:
    """Returns 0.0-1.0 authority + freshness score"""

def extract_content(html: str) -> str:
    """Returns cleaned markdown from raw HTML"""
```

**Each tool should be independently testable** without running the full agent. Write unit tests for each tool function.

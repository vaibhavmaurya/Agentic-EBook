# SOP 02 — AWS Architecture & Service Selection

## Purpose

Make the right AWS service choices upfront and avoid the class of bugs that only surface after deployment — especially IAM permission gaps, Lambda runtime quirks, and service integration edge cases.

---

## Service Selection Decision Framework

### API Layer: API Gateway HTTP API (not REST API)

**Use HTTP API when:**
- You need JWT authorization with Cognito (built-in JWT authorizer)
- You have simple routing (Lambda proxy integration)
- You want lower cost and lower latency than REST API

**Use REST API when:**
- You need request/response transformation
- You need API keys with usage plans
- You need WAF integration at the API level

**For this project:** HTTP API with JWT authorizer. `/admin/*` requires JWT; `/public/*` is open.

### Orchestration: Step Functions Standard (not Express)

**Always use Standard workflow when:**
- You need `.waitForTaskToken` (human-in-the-loop, async callbacks)
- Execution duration > 5 minutes
- You need execution history and visual debugging in the console

**Use Express workflow only for:**
- High-volume, short-duration (<5 min) event processing
- When you don't need execution history per-run

**Critical:** Express workflows do NOT support `.waitForTaskToken`. If you need a human approval gate, you must use Standard.

### Scheduling: EventBridge Scheduler (not EventBridge Rules)

**Use Scheduler when:**
- One-time or recurring schedules per resource (per-topic schedules)
- You need a schedule group to manage related schedules
- Rate/cron expressions needed per entity

**Key pattern for dynamic per-entity schedules:**
- Terraform provisions the schedule **group** only
- The application API creates/updates/deletes individual schedules at runtime
- Do NOT put per-entity schedules in Terraform — they change too frequently

### Storage: DynamoDB + S3 Split

**DynamoDB for:** metadata, configuration, trace events, status flags, anything queryable
**S3 for:** large artifacts (research content, drafts, HTML, JSON indexes), anything > 400KB

Never store large blobs in DynamoDB. The 400KB item size limit will hit you in production.

### Frontend Hosting: Amplify Hosting

**Amplify Hosting is appropriate when:**
- Static site or SPA
- You want CDN distribution without managing CloudFront manually
- You need environment variable injection at build time

**Important:** Amplify apps created by Terraform must be managed carefully. If Terraform decides to replace the Amplify app (due to attribute changes), it will destroy the existing deployment. Use `terraform apply -target` when reconciling IAM or environment variable changes post-deploy to avoid accidental app replacement.

---

## IAM — The Most Common Source of Post-Deployment Bugs

### Rule: One IAM Role Per Lambda Function

Never share a role between Lambda functions. Least-privilege requires per-function roles. Shared roles create two problems:
1. One function can call resources it has no business touching
2. When you add permissions for one function, you inadvertently grant them to others

### The IAM Gap Pattern

**IAM gaps are almost never caught by Terraform.** Terraform validates syntax and resource existence — it does not validate that the permissions are sufficient for the code to run. Gaps only surface at runtime when you get `AccessDeniedException`.

**How to find gaps systematically:**
1. For every cross-service call in your Lambda code, list the IAM action required
2. Check the role's attached policies against that list
3. After deployment, test every code path and watch CloudWatch logs for `AccessDeniedException`

**Common gaps encountered in this project:**

| Cross-service call | Required IAM action | Lambda role that needed it |
|---|---|---|
| `sfn.send_task_success()` | `states:SendTaskSuccess` | API Lambda (approval endpoint) |
| `sfn.send_task_failure()` | `states:SendTaskFailure` | API Lambda (rejection endpoint) |
| `amplify.create_deployment()` | `amplify:CreateDeployment` | Worker Lambda (post-publish) |
| `amplify.start_deployment()` | `amplify:StartDeployment` | Worker Lambda (post-publish) |

**Fix pattern when you find a gap:**
1. Add the missing action to the Terraform IAM policy
2. Also apply it immediately via AWS CLI if the environment is live:
```bash
aws iam put-role-policy \
  --role-name ebook-api-lambda-role-dev \
  --policy-name inline-missing-permission \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["states:SendTaskSuccess","states:SendTaskFailure"],"Resource":"*"}]}'
```
3. Reconcile to Terraform state on the next planned `terraform apply`

---

## Lambda Runtime Quirks

### Python Path Resolution

**The bug:** code that works locally fails in Lambda with `FileNotFoundError` or `ModuleNotFoundError`.

**Root cause:** Lambda's working directory is not the same as your local project root. Relative paths from `__file__` resolve differently.

**Wrong pattern:**
```python
config_path = Path(__file__).parent / "openai_runtime" / "config.yaml"
# In Lambda: __file__ is /var/task/handler.py
# .parent = /var/task
# Result: /var/task/openai_runtime/config.yaml ← correct
# BUT if handler is nested: .parent resolves to wrong level
```

**Safe pattern — always resolve from `__file__` and check both locations:**
```python
_HERE = Path(__file__).parent
# Check the Lambda path first (handler is at root of zip)
config_path = _HERE / "openai_runtime" / "config.yaml"
if not config_path.exists():
    # Fallback: local dev path (handler is in services/api/)
    config_path = _HERE.parent / "openai_runtime" / "config.yaml"
```

### Lambda Zip Packaging for Python

**The bug:** native Python packages (pydantic, cryptography) fail in Lambda with `ImportError` because they were compiled for macOS or Windows.

**Rule:** always build Lambda zips using Linux-compatible (manylinux) wheels.

```bash
# Wrong: installs for your local OS
pip install pydantic -t ./package/

# Correct: force Linux platform
pip install pydantic \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  -t ./package/
```

See `scripts/deploy_workers.sh` for the full packaging pattern.

### Lambda Timeout Configuration

| Function type | Recommended timeout | Reason |
|---|---|---|
| API handlers | 30 seconds | API Gateway max is 29s |
| Pipeline workers (AI calls) | 15 minutes | OpenAI calls can take 60-120s; full stage needs headroom |
| Digest / batch workers | 5-10 minutes | SES calls + DynamoDB scans |

---

## Step Functions — The WaitForTaskToken Pattern

This is the human-in-the-loop approval mechanism. Get it exactly right.

### How It Works

1. The pipeline reaches the `WaitForApproval` state
2. Step Functions generates a task token and passes it to the approval Lambda
3. The Lambda stores the token in DynamoDB (`REVIEW#<run_id>` item)
4. The execution pauses — it does not time out for up to 1 year (or configured heartbeat)
5. Admin calls the approval API → API reads token from DynamoDB → calls `SendTaskSuccess` or `SendTaskFailure`
6. Step Functions resumes the execution

### The Input Wrapping Bug

**The bug:** the state before `WaitForApproval` outputs a result, but the `WaitForApproval` state wraps it:

```json
{
  "task_token": "AQCgAAAAKgAAAA...",
  "input": {
    "topic_id": "abc123",
    "run_id": "run-xyz",
    "draft_uri": "s3://..."
  }
}
```

**The handler must unwrap `input`:**
```python
# Wrong — causes KeyError: 'topic_id'
topic_id = event["topic_id"]

# Correct
task_token = event["task_token"]
payload = event["input"]
topic_id = payload["topic_id"]
```

### Task Token Expiry — Return 409, Not 500

If the admin tries to approve/reject after the token has expired (72h timeout), `SendTaskSuccess` throws `TaskTimedOut`. This must be caught and returned as a 409, not allowed to bubble up as a 500.

```python
try:
    sfn.send_task_success(taskToken=token, output=json.dumps(result))
except sfn.exceptions.TaskTimedOut:
    return {"statusCode": 409, "body": json.dumps({"error": "TASK_EXPIRED", "message": "This run's approval window has closed."})}
except sfn.exceptions.InvalidToken:
    return {"statusCode": 409, "body": json.dumps({"error": "INVALID_TOKEN"})}
```

---

## DynamoDB — Single-Table Design

### SK Ordering for Time-Sorted Queries

**The bug:** using a UUID or random string as SK causes `query()` to return items in arbitrary (UUID-sorted) order rather than time order.

**Rule:** if you need time-ordered results (e.g. "latest run"), use an ISO timestamp or padded numeric sequence in the SK:

```python
# Wrong — UUID SK, unsortable by time
SK = f"RUN#{uuid4()}"

# Correct — ISO timestamp SK, sorts chronologically
SK = f"RUN#{datetime.utcnow().isoformat()}#{run_id}"

# Or: store run_id in the item, sort by a `started_at` attribute
runs = sorted(items, key=lambda x: x.get("started_at", ""), reverse=True)
```

### Query vs Scan

**Never use `scan()` in a production hot path.** Scans read every item in the table and charge full read capacity.

- `scan()` is acceptable in: purge/cleanup scripts, one-time data migrations, notebook test teardown
- Everything else uses `query()` with a partition key (PK) or GSI

### Batch Operations for Cleanup

```python
# Batch delete — 25 items max per batch
with table.batch_writer() as batch:
    for pk, sk in items_to_delete:
        batch.delete_item(Key={"PK": pk, "SK": sk})
```

---

## S3 Artifact Layout Convention

Always use a consistent prefix hierarchy. This enables lifecycle rules, cost attribution, and scoped cleanup.

```
topics/<topic_id>/runs/<run_id>/{raw,extracted,verified,draft,review,diff}/
published/topics/<topic_id>/v001/
site/current/search/index.json
site/current/toc.json
config/model_config.yaml
config/prompts.yaml
```

**Never put per-run artifacts under `published/`.** Published is the promoted, approved output. Runs are ephemeral and can be archived or deleted.

**Upload default configs to S3 immediately after provisioning.** If your application reads config from S3 at startup and the file doesn't exist, you'll get cryptic errors. Add config upload to your deployment checklist.

---

## Common Post-Deployment Verification Steps

After every `terraform apply` or Lambda deploy:

```bash
# 1. Check Lambda function exists and has correct role
aws lambda get-function-configuration --function-name <name> | jq '{Role, Timeout, MemorySize}'

# 2. Check IAM role has expected policies
aws iam list-role-policies --role-name <role-name>
aws iam list-attached-role-policies --role-name <role-name>

# 3. Tail Lambda logs after a test invocation
aws logs tail /aws/lambda/<function-name> --follow

# 4. Verify S3 bucket has correct lifecycle rules
aws s3api get-bucket-lifecycle-configuration --bucket <bucket-name>
```

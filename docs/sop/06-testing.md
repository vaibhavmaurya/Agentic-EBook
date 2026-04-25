# SOP 06 — Testing & Deployment Workflow

## Purpose

Define how to test reliably, deploy safely, and avoid the class of bugs that only appear in real AWS environments. The approach here is deliberately different from standard "mock everything" testing philosophy.

---

## The No-Mock-AWS Principle

**Never mock AWS services in development or integration tests.**

The reason this matters: mock/real divergence masks real failures. A test suite that mocks DynamoDB will pass even if:
- The DynamoDB table has the wrong GSI attribute names
- The IAM role lacks `dynamodb:Query` on the correct index
- The query's `KeyConditionExpression` uses wrong attribute names
- The item was written with a different schema than you expected

These failures only surface in production. With real AWS resources in dev, they surface immediately and cheaply.

**What you mock:** pure logic functions with no AWS/external calls (string formatting, calculation utilities, data transformation).

**What you never mock:** DynamoDB, S3, Step Functions, SFN, Cognito, SES, Lambda invocations.

**What you need for this to work:**
- A dev AWS account with real resources (not shared with prod)
- AWS credentials in `.env.local` pointing at the dev account
- Discipline to clean up test data after each test run

---

## Jupyter Notebook as Integration Test Harness

The notebook is the primary integration test for the full end-to-end system. It replaces a traditional API test suite.

**Why a notebook:**
- Tests run in use-case order (UC-01 creates topic; UC-04 triggers it; UC-07 approves it)
- IDs are tracked in a `created_resources` dict and passed between cells — no manual copy-paste
- Output is human-readable (markdown, print statements) so you can watch the pipeline progress
- The PURGE cell resets the dev environment — idempotent, scoped to test IDs only

### `created_resources` Dictionary Pattern

```python
# Cell 0 — initialized at the top, never reset mid-run
created_resources = {
    "topic_ids": [],
    "run_ids": [],
    "execution_arns": [],
    "schedule_names": [],
}

# Cell 1 — create topic, store its ID
res = requests.post(f"{ADMIN_API}/admin/topics", json=topic_payload, headers=auth)
topic_id = res.json()["topic_id"]
created_resources["topic_ids"].append(topic_id)
print(f"✓ Topic created: {topic_id}")

# Cell 4 — trigger run, store run_id and execution ARN
res = requests.post(f"{ADMIN_API}/admin/topics/{topic_id}/trigger", headers=auth)
run_id = res.json()["run_id"]
execution_arn = res.json()["execution_arn"]
created_resources["run_ids"].append(run_id)
created_resources["execution_arns"].append(execution_arn)
```

Never use hardcoded IDs between cells. If a cell fails and you re-run, the `created_resources` dict ensures the new IDs are tracked.

### Pipeline Polling Helper

```python
import time

def poll_until(condition_fn, timeout=300, interval=10):
    """Poll until condition_fn() returns True or timeout expires."""
    elapsed = 0
    while elapsed < timeout:
        result = condition_fn()
        if result:
            return result
        print(f"  Waiting... ({elapsed}s elapsed)")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Condition not met after {timeout}s")

# Usage: poll until run reaches WaitForApproval
def check_review_pending():
    res = requests.get(f"{ADMIN_API}/admin/topics/{topic_id}/review/{run_id}", headers=auth)
    if res.status_code == 200:
        return res.json()
    return None

review = poll_until(check_review_pending, timeout=600, interval=15)
print(f"✓ Review ready: {review['review_status']}")
```

### PURGE Cell Design Rules

The PURGE cell must follow these rules:
1. **Only delete IDs in `created_resources`** — never blindly wipe the table or bucket
2. **Try/except per step** — a failed S3 delete should not prevent DynamoDB cleanup
3. **Idempotent** — safe to run twice; second run should succeed or skip cleanly
4. **Assert clean state** at the end — verify zero items remain for test keys

```python
# PURGE sequence
print("=== PURGE START ===")

# 1. Stop any running Step Functions executions
for arn in created_resources["execution_arns"]:
    try:
        sfn.stop_execution(executionArn=arn, error="PURGE", cause="Test cleanup")
        print(f"  Stopped execution: {arn[-8:]}")
    except sfn.exceptions.ExecutionDoesNotExist:
        pass  # Already stopped

# 2. Delete per-topic EventBridge schedules
for name in created_resources["schedule_names"]:
    try:
        scheduler.delete_schedule(Name=name, GroupName=SCHEDULE_GROUP)
        print(f"  Deleted schedule: {name}")
    except scheduler.exceptions.ResourceNotFoundException:
        pass

# 3. Batch-delete DynamoDB items
with table.batch_writer() as batch:
    for topic_id in created_resources["topic_ids"]:
        # Query all items for this topic and delete them
        items = table.query(KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}"))["Items"]
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

# 4. Delete S3 artifacts
s3 = boto3.resource("s3")
bucket = s3.Bucket(S3_ARTIFACT_BUCKET)
for topic_id in created_resources["topic_ids"]:
    bucket.objects.filter(Prefix=f"topics/{topic_id}/").delete()
    bucket.objects.filter(Prefix=f"published/topics/{topic_id}/").delete()

# 5. Assert clean state
for topic_id in created_resources["topic_ids"]:
    items = table.query(KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}"))["Items"]
    assert len(items) == 0, f"DynamoDB not clean for {topic_id}: {len(items)} items remain"

print("=== PURGE COMPLETE ===")
```

---

## Local Dev Cycle

### Lambda Handler + FastAPI Pattern

Every Lambda handler also runs locally via FastAPI. This is the key pattern that allows local testing without deploying to Lambda.

```python
# services/api/local_dev_server.py
from fastapi import FastAPI, Request
from topics import handler as topics_handler
from public import handler as public_handler

app = FastAPI()

@app.api_route("/admin/topics/{path:path}", methods=["GET","POST","PUT","DELETE"])
async def admin_topics_route(request: Request, path: str):
    event = await build_lambda_event(request)
    return topics_handler(event, {})

@app.api_route("/public/{path:path}", methods=["GET","POST"])
async def public_route(request: Request, path: str):
    event = await build_lambda_event(request)
    return public_handler(event, {})
```

The same handler function (`topics_handler`) runs both in Lambda (triggered by API Gateway) and locally (triggered by FastAPI). The `build_lambda_event()` helper converts an HTTP request into the API Gateway proxy event format.

**Start the local API server:**
```bash
cd services/api
source ../../.env.local
uvicorn local_dev_server:app --reload --port 8000
```

**Test it:**
```bash
curl http://localhost:8000/admin/topics \
  -H "Authorization: Bearer $(python -c 'from auth import get_dev_token; print(get_dev_token())')"
```

### Worker Direct Execution

Each worker can be run directly for isolated testing:

```bash
source .env.local
python services/workers/research_worker.py \
  --topic-id abc123 \
  --run-id run-xyz \
  --event '{"research_plan": {...}}'
```

Add CLI argument parsing to every worker with `argparse`. This lets you test a single stage without running the full pipeline.

---

## Lambda Deployment Workflow

### Worker Deploy Script Pattern

Lambda zips must be built with Linux-compatible (manylinux) wheels. The deploy script handles this:

```bash
#!/bin/bash
# scripts/deploy_workers.sh

FUNCTION_PREFIX="ebook-platform-dev"
WORKERS_DIR="services/workers"
BUILD_DIR="/tmp/lambda-build"

for worker in topic_loader research_worker planner_worker; do
    echo "Building $worker..."
    rm -rf $BUILD_DIR && mkdir -p $BUILD_DIR

    # Install Linux-compatible dependencies
    pip install -r $WORKERS_DIR/requirements.txt \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.12 \
        --only-binary=:all: \
        -t $BUILD_DIR/

    # Copy worker code
    cp $WORKERS_DIR/${worker}.py $BUILD_DIR/lambda_function.py
    cp -r services/openai-runtime $BUILD_DIR/
    cp -r packages/shared-types $BUILD_DIR/

    # Zip and deploy
    cd $BUILD_DIR && zip -r /tmp/${worker}.zip . && cd -
    aws lambda update-function-code \
        --function-name ${FUNCTION_PREFIX}-${worker} \
        --zip-file fileb:///tmp/${worker}.zip

    echo "Deployed $worker"
done
```

**Always verify deployment:**
```bash
aws lambda get-function-configuration \
  --function-name ebook-platform-dev-research-worker \
  --query '{CodeSize: CodeSize, LastModified: LastModified}'
```

### Checking Lambda Logs After Deployment

```bash
# Tail logs in real-time during a test
aws logs tail /aws/lambda/ebook-platform-dev-research-worker --follow

# Get recent logs for a specific time window
aws logs get-log-events \
  --log-group-name /aws/lambda/ebook-platform-dev-research-worker \
  --log-stream-name $(aws logs describe-log-streams \
    --log-group-name /aws/lambda/ebook-platform-dev-research-worker \
    --order-by LastEventTime --descending \
    --query 'logStreams[0].logStreamName' --output text) \
  --start-from-head \
  --query 'events[*].message' \
  --output text
```

---

## Pre-Commit Checklist (for every milestone)

Before committing, verify:

```
Backend:
[ ] Start local API server: cd services/api && uvicorn local_dev_server:app --reload
[ ] Make real HTTP calls against every new endpoint (not just happy path)
[ ] Check CloudWatch logs for any unexpected errors
[ ] ruff check services/ --fix (0 linting errors)

Frontend:
[ ] npm run build passes with 0 TypeScript errors and 0 build errors
[ ] Smoke-test the critical paths in browser (login, create, trigger, approve)

Infrastructure:
[ ] terraform fmt -recursive
[ ] terraform validate
[ ] terraform plan shows no unexpected destroys

Cross-cutting:
[ ] No hardcoded credentials or API keys anywhere
[ ] No new imports of openai package outside openai_runtime/
[ ] New Lambda functions have per-function IAM roles
[ ] All new API routes under /admin/* have JWT auth
```

---

## Step Functions Local for Pipeline Iteration

When iterating on the Step Functions ASL (state machine definition), use the local emulator to avoid API costs:

```bash
# Start local emulator
docker run -p 8083:8083 amazon/aws-stepfunctions-local

# In .env.local
STEP_FUNCTIONS_ENDPOINT=http://localhost:8083
```

All other services (DynamoDB, S3, Lambda) remain real AWS. Only Step Functions execution is local.

**Note:** the local emulator does not support `.waitForTaskToken`. Test the approval flow against real Step Functions.

---

## Deployment Order

When deploying for the first time or after major changes, follow this order:

1. `terraform apply` — infrastructure first
2. Upload config files to S3 (`config/model_config.yaml`, `config/prompts.yaml`)
3. Deploy Lambda workers (`scripts/deploy_workers.sh`)
4. Deploy API Lambda (if changed)
5. Build and deploy public site to Amplify
6. Build and deploy admin site to Amplify
7. Run notebook cells 0-4 (setup + topic create + trigger)
8. Verify pipeline reaches WaitForApproval
9. Run approval flow
10. Verify published content appears on public site

Never skip steps 2-3. Missing config files cause cryptic Lambda errors that look like code bugs.

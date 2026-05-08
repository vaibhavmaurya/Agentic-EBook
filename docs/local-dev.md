# Local Development Guide — Agentic Ebook Platform V3

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend Lambda handlers and workers |
| Node.js | 20+ | Frontend (React admin, Astro public site), GitHub MCP server |
| Terraform | 1.7+ | AWS infrastructure provisioning |
| Docker | Latest | AWS Step Functions Local emulator |
| AWS CLI | 2.x | Credential validation and resource inspection |
| uv | Latest | Python package runner for MCP servers |
| Jupyter | Latest | API test harness notebook |

Install uv:
```bash
pip install uv
```

## Step 1 — Clone and Configure Credentials

```bash
git clone <repo-url> ebook-platform
cd ebook-platform
cp .env.local.example .env.local
```

Edit `.env.local` and fill in:
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` — dev account IAM user credentials
- `AWS_REGION` — e.g. `us-east-1`
- `AWS_ACCOUNT_ID` — your dev AWS account number
- `OWNER_EMAIL` and `SES_SENDER_EMAIL` — verified SES email addresses
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — your dev Cognito admin user credentials

> The IAM user should have permissions for: DynamoDB, S3, Step Functions, EventBridge Scheduler, Lambda (invoke), SES, Secrets Manager (read), Cognito (initiate-auth). Attach the least-privilege policy defined in `infra/terraform/modules/iam/dev_developer_policy.json` once Terraform has run.

## Step 2 — Provision Dev AWS Infrastructure

```bash
cd infra/terraform/envs/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

After `apply` completes, Terraform outputs the resource names. Copy these into your `.env.local`:
- `DYNAMODB_TABLE_NAME`
- `S3_ARTIFACT_BUCKET`
- `STEP_FUNCTIONS_ARN`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`

## Step 3 — Install Python Dependencies

A single virtual environment at the **repo root** covers all services.

```bash
# From the repo root
python -m venv .venv

# Activate (run this every terminal session before using Python tools)
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Install API + worker dependencies
pip install -r services/api/requirements.txt

# Install shared-types as an editable local package
pip install -e packages/shared-types
```

> **Windows tip:** If you see `'uvicorn' is not recognized`, the venv is not activated or you need to use `python -m uvicorn` instead of `uvicorn` directly. Both work identically.

## Step 4 — Start the Local API Server

The server reads `.env.local` automatically via `python-dotenv` — no need to source it manually.

```bash
# Option A: with venv activated (recommended)
cd services/api
uvicorn local_dev_server:app --reload --port 8000

# Option B: without activating venv (always works on Windows)
cd services/api
../../.venv/Scripts/python -m uvicorn local_dev_server:app --reload --port 8000
```

The local server maps all HTTP routes to the same Lambda handler functions that run in AWS. No stubs — it hits real DynamoDB, S3, and Step Functions in your dev account.

Test that it's working:
```bash
curl http://localhost:8000/health
# Expects: {"status": "ok", "env": "dev"}

curl http://localhost:8000/admin/topics \
  -H "Authorization: Bearer <cognito_token>"
# Expects: {"topics": []}
```

## Step 5 — (Optional) Run Step Functions Locally

For pipeline development without incurring Step Functions API costs:

```bash
docker run -p 8083:8083 \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  amazon/aws-stepfunctions-local
```

Then set in `.env.local`:
```
STEP_FUNCTIONS_ENDPOINT=http://localhost:8083
```

The local Step Functions emulator still calls the real Lambda functions (or you can configure mock integrations for faster iteration).

## Step 6 — Run the Jupyter Notebook Test Harness

```bash
# With venv activated:
pip install -r notebooks/requirements.txt
jupyter notebook notebooks/ebook_platform_test_harness.ipynb

# Or with explicit venv path:
.venv/Scripts/pip install -r notebooks/requirements.txt
.venv/Scripts/jupyter notebook notebooks/ebook_platform_test_harness.ipynb
```

Run cells top-to-bottom for a full UC-01 → UC-15 end-to-end test.
Run Cell Group 16 (PURGE) after any exploratory testing session to clean up dev state.

## Step 7 — (Optional) Start Frontend Dev Servers

### Admin UI
```bash
cd apps/admin-site
npm install
npm run dev
# Serves at http://localhost:3000
# (proxies /admin/* and /public/* to localhost:8000 automatically)
```

### Public Site
```bash
cd apps/public-site
npm install
npm run dev
# Serves at http://localhost:4321
```

## Managing LLM Configuration and Prompts

All model configuration and agent prompts are stored in two YAML files:

| File | Purpose |
|---|---|
| `services/openai_runtime/model_config.yaml` | Provider selection, model IDs, pricing, per-agent parameters |
| `services/openai_runtime/prompts.yaml` | All agent system/user prompts with template variables |

### How workers load config

Workers use a priority chain to find these files at runtime:

```
1. Explicit env var (MODEL_CONFIG_PATH or PROMPTS_CONFIG_PATH)
   ├─ If value starts with s3://  → download from S3
   └─ Otherwise                  → read as a local file path

2. Auto-load from S3 (if S3_ARTIFACT_BUCKET is set)
   └─ s3://<S3_ARTIFACT_BUCKET>/config/model_config.yaml
   └─ s3://<S3_ARTIFACT_BUCKET>/config/prompts.yaml

3. Bundled local file (always available as fallback)
   └─ services/openai_runtime/model_config.yaml
   └─ services/openai_runtime/prompts.yaml
```

In production (Lambda), `S3_ARTIFACT_BUCKET` is always set, so workers automatically pull the live config from S3 on every cold start — **no Lambda redeployment required** when you change models or prompts.

### Changing the active LLM provider

Edit `services/openai_runtime/model_config.yaml`:

```yaml
active_provider: openai   # ← change to: anthropic | gemini
```

Then upload to S3 and changes take effect on the next Lambda invocation:

```bash
source .env.local
python scripts/upload_configs.py
```

Supported providers and their secrets:

| Provider | Secret name in Secrets Manager | High model | Low model |
|---|---|---|---|
| `openai` | `ebook-platform/openai-key` | `gpt-4o-2024-11-20` | `gpt-4o-mini-2024-07-18` |
| `anthropic` | `ebook-platform/anthropic-key` | `claude-opus-4-6` | `claude-haiku-4-5-20251001` |
| `gemini` | `ebook-platform/gemini-key` | `gemini-2.0-pro` | `gemini-2.0-flash` |

### Changing model IDs or pricing

Edit the provider block in `model_config.yaml`:

```yaml
providers:
  openai:
    models:
      high_capability: gpt-4o-2024-11-20    # ← change model ID here
      low_capability:  gpt-4o-mini-2024-07-18
    pricing_per_million_tokens:
      high_capability:
        input:  2.50
        output: 10.00
```

### Changing per-agent parameters

Each agent has its own block under `agents:`:

```yaml
agents:
  writer:
    capability: high        # high → uses high_capability model; low → uses low_capability
    max_tokens: 8192        # max output tokens
    temperature: 0.6        # 0.0 deterministic, 1.0 creative
    timeout_sec: 180        # hard timeout for the LLM API call
```

`capability` maps directly to the provider's `high_capability` or `low_capability` model ID.
To force a specific model regardless of capability tier, add:

```yaml
    model_override: gpt-4o-mini-2024-07-18
```

### Changing prompts

Edit `services/openai_runtime/prompts.yaml`. Each agent has `system` and `user` keys.
Template variables use `${variable_name}` syntax:

```yaml
planner:
  system: |
    You are a research planner...
  user: |
    Topic: ${title}
    Description: ${description}
    ...
```

Available variables per agent are listed in the header comment of `prompts.yaml`.

After editing, upload to S3:

```bash
source .env.local
python scripts/upload_configs.py
```

### Applying changes locally (without S3)

When running workers locally, the bundled file is used unless `S3_ARTIFACT_BUCKET` is set.
To test a config change locally without uploading to S3:

```bash
# Option A: unset the bucket var so local file is always used
unset S3_ARTIFACT_BUCKET
python scripts/run_pipeline_local.py --create-topic --auto-approve

# Option B: point to a specific local file via env var
MODEL_CONFIG_PATH=/path/to/my-test-config.yaml \
python scripts/run_pipeline_local.py --create-topic --auto-approve
```

### Verifying which config was loaded

Add a quick check to confirm S3 loading is active:

```python
source .env.local
source .venv/Scripts/activate
python - <<'EOF'
from services.openai_runtime.config import load_config, _S3_BUCKET
cfg = load_config()
print(f"Provider : {cfg.active_provider}")
print(f"S3 bucket: {_S3_BUCKET or '(not set — using local file)'}")
print(f"Writer   : {cfg.agents['writer'].capability} / max_tokens={cfg.agents['writer'].max_tokens}")
EOF
```

### upload_configs.py reference

```
Usage:  python scripts/upload_configs.py [--bucket BUCKET] [--region REGION]

Uploads:
  services/openai_runtime/model_config.yaml  →  s3://<bucket>/config/model_config.yaml
  services/openai_runtime/prompts.yaml       →  s3://<bucket>/config/prompts.yaml

Defaults from .env.local:
  --bucket  S3_ARTIFACT_BUCKET
  --region  AWS_REGION
```

---

## Running the Full Local Pipeline

To run the complete 13-stage pipeline locally (no Step Functions required):

```bash
source .env.local
source .venv/Scripts/activate

# Create a new topic + run all stages + auto-approve + publish
python scripts/run_pipeline_local.py --create-topic --auto-approve

# Resume from a specific stage (for debugging a failed stage)
python scripts/run_pipeline_local.py \
  --topic-id <existing_topic_id> \
  --run-id <existing_run_id> \
  --start-from DraftChapter

# Use an existing topic but create a new run
python scripts/run_pipeline_local.py \
  --topic-id <existing_topic_id> \
  --auto-approve
```

> **Note:** The `--start-from` flag skips earlier stages entirely. Only use it for stages
> that do not do web research (ResearchTopic). Skipping web research reuses whatever
> evidence is already in the DynamoDB/S3 state from the prior run.

Stages in order:
```
LoadTopicConfig → AssembleTopicContext → PlanTopic → ResearchTopic → VerifyEvidence
→ PersistEvidenceArtifacts → DraftChapter → EditorialReview → BuildDraftArtifact
→ GenerateDiffReleaseNotes → NotifyAdminForReview → [auto-approve] → PublishTopic
→ RebuildIndexes
```

---

## Running Individual Workers

Workers (Step Functions Lambda tasks) can be invoked directly as Python scripts:

```bash
source .env.local
python services/workers/topic_loader.py \
  --topic-id <topic_id> \
  --run-id <run_id>
```

This is useful for testing a single pipeline stage in isolation without triggering a full Step Functions execution.

## Useful Dev Commands

```bash
# Check what's in DynamoDB for a topic
aws dynamodb query \
  --table-name ebook_platform \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "TOPIC#<topic_id>"}}' \
  --region us-east-1

# List S3 artifacts for a run
aws s3 ls s3://<bucket>/topics/<topic_id>/runs/<run_id>/ --recursive

# Check Step Functions execution status
aws stepfunctions describe-execution \
  --execution-arn <execution_arn> \
  --region us-east-1

# List running Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn <state_machine_arn> \
  --status-filter RUNNING \
  --region us-east-1
```

## Deploying the Admin Site to Amplify

The admin site (`apps/admin-site`) is deployed manually to Amplify — there is no GitHub auto-deploy. Follow these steps exactly after any frontend change.

### Step 1 — Build

```bash
cd apps/admin-site
npm run build   # reads apps/admin-site/.env.production for VITE_* vars
```

`.env.production` is gitignored and must exist locally with:
```
VITE_API_BASE_URL=https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com
VITE_COGNITO_USER_POOL_ID=us-east-1_R4FK1QHyr
VITE_COGNITO_CLIENT_ID=5g3o4juiad2ils16v48iuu119i
VITE_AWS_REGION=us-east-1
```

These values come from `terraform output` in `infra/terraform/envs/dev`.

### Step 2 — Zip (use Python — NOT PowerShell Compress-Archive)

**Critical:** PowerShell `Compress-Archive` uses Windows backslash paths (`assets\index.js`). AWS CloudFront/Amplify treats these as literal filenames, so `assets/` never becomes a real directory and all JS/CSS 404s. Always use the Python zip script:

```bash
python3 -c "
import zipfile, os
dist = 'apps/admin-site/dist'
out  = 'apps/admin-site/dist.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(dist):
        for f in files:
            full = os.path.join(root, f)
            arcname = os.path.relpath(full, dist).replace(os.sep, '/')
            zf.write(full, arcname)
print('Zipped')
"
```

### Step 3 — Create deployment slot, upload, and start

```bash
# Create slot
JOB=$(aws amplify create-deployment --app-id d200xw9mmlu4wj --branch-name dev --region us-east-1 --output json)
JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['jobId'])")
UPLOAD_URL=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['zipUploadUrl'])")

# Upload
curl -s -o /dev/null -w "Upload: %{http_code}\n" \
  -X PUT -H "Content-Type: application/zip" \
  --data-binary @apps/admin-site/dist.zip "$UPLOAD_URL"

# Start deployment
aws amplify start-deployment \
  --app-id d200xw9mmlu4wj --branch-name dev \
  --job-id $JOB_ID --region us-east-1

# Poll until done (takes ~15-30s)
aws amplify get-job --app-id d200xw9mmlu4wj --branch-name dev \
  --job-id $JOB_ID --region us-east-1 \
  --query 'job.summary.status' --output text
```

### Step 4 — Verify

```bash
# Should return 200
curl -s -o /dev/null -w "%{http_code}" https://dev.d200xw9mmlu4wj.amplifyapp.com

# Should contain the API URL (confirms env vars were baked in)
curl -s https://dev.d200xw9mmlu4wj.amplifyapp.com/assets/index-*.js | grep -c "gcqq4kkov1"
```

### Amplify branch environment variables

The Amplify branch must also have these env vars set (they're used if Amplify ever runs its own build). They were set with:

```bash
aws amplify update-branch \
  --app-id d200xw9mmlu4wj --branch-name dev --region us-east-1 \
  --environment-variables '{"VITE_API_BASE_URL":"https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com","VITE_COGNITO_USER_POOL_ID":"us-east-1_R4FK1QHyr","VITE_COGNITO_CLIENT_ID":"5g3o4juiad2ils16v48iuu119i","VITE_AWS_REGION":"us-east-1"}'
```

If env vars are missing, verify with:
```bash
aws amplify get-branch --app-id d200xw9mmlu4wj --branch-name dev \
  --region us-east-1 --query 'branch.environmentVariables'
```

---

## Environment Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `NoCredentialsError` | `.env.local` not sourced | `source .env.local` before running |
| `ResourceNotFoundException` on DynamoDB | Terraform not applied | Run `terraform apply` in `infra/terraform/envs/dev` |
| `AccessDeniedException` | IAM policy too restrictive | Check IAM policy in Terraform outputs |
| OpenAI key not found | Secret not created in Secrets Manager | Create secret manually or via Terraform, update `OPENAI_SECRET_NAME` |
| Step Functions execution fails immediately | ASL definition error | Check CloudWatch logs for the state machine |
| Notebook auth fails | Cognito user not created | Create admin user in Cognito console or via AWS CLI |
| Admin site topics not loading / API calls fail | `VITE_API_BASE_URL` empty in build | Ensure `apps/admin-site/.env.production` exists with correct API URL, rebuild and redeploy |
| Admin site JS/CSS 404 after Amplify deploy | Zip created with Windows backslash paths | Use the Python zip script above — never `PowerShell Compress-Archive` |

## MCP Server Setup (for Claude Code productivity)

The `.claude/settings.json` in the project root configures three MCP servers. To enable them:

```bash
# 1. GitHub MCP (requires Node.js)
npm install -g @modelcontextprotocol/server-github
# Set GITHUB_TOKEN in your shell profile (not .env.local)
export GITHUB_TOKEN=ghp_...

# 2. AWS Docs MCP + Terraform MCP (requires uv)
pip install uv
# First run of each server will auto-download via uvx
```

Restart Claude Code after configuring the token. Verify MCP servers are connected via `/mcp` in Claude Code.

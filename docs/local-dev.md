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

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Repeat for `services/workers/` and `services/openai-runtime/`.

Or use a root `pyproject.toml` with a single venv covering all services (recommended as the project matures).

## Step 4 — Start the Local API Server

```bash
cd services/api
source .env.local      # loads AWS credentials into the shell
uvicorn local_dev_server:app --reload --port 8000
```

The local server maps all HTTP routes to the same Lambda handler functions that run in AWS. No stubs — it hits real DynamoDB, S3, and Step Functions in your dev account.

Test that it's working:
```bash
curl http://localhost:8000/admin/topics
# Expects: 200 with empty list []
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
cd notebooks
pip install -r requirements.txt
jupyter notebook ebook_platform_test_harness.ipynb
```

Run cells top-to-bottom for a full UC-01 → UC-15 end-to-end test.
Run Cell Group 16 (PURGE) after any exploratory testing session to clean up dev state.

## Step 7 — (Optional) Start Frontend Dev Servers

### Admin UI
```bash
cd apps/admin-site
npm install
npm run dev
# Serves at http://localhost:5173
```

### Public Site
```bash
cd apps/public-site
npm install
npm run dev
# Serves at http://localhost:4321
```

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

## Environment Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `NoCredentialsError` | `.env.local` not sourced | `source .env.local` before running |
| `ResourceNotFoundException` on DynamoDB | Terraform not applied | Run `terraform apply` in `infra/terraform/envs/dev` |
| `AccessDeniedException` | IAM policy too restrictive | Check IAM policy in Terraform outputs |
| OpenAI key not found | Secret not created in Secrets Manager | Create secret manually or via Terraform, update `OPENAI_SECRET_NAME` |
| Step Functions execution fails immediately | ASL definition error | Check CloudWatch logs for the state machine |
| Notebook auth fails | Cognito user not created | Create admin user in Cognito console or via AWS CLI |

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

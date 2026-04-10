# Agentic Ebook Platform V3

A dynamic, per-topic publishing platform where AI agents research, draft, and stage content for each topic. A human admin reviews and approves before incremental publish to a public ebook website. Runs entirely on AWS.

---

## How it works

1. Admin creates a **topic** (title, instructions, schedule) via the admin UI
2. A **pipeline** is triggered manually or on a schedule
3. Six AI agents run in sequence: Planner → Research → Verifier → Writer → Editor → Diff
4. Admin receives a notification and **reviews the staged draft** — approve or reject
5. On approval, the chapter is **published** to the public ebook site
6. Readers browse, search, highlight, and comment on published content

---

## Repository layout

```
repo/
  apps/
    admin-site/        React + Vite SPA (admin console)
    public-site/       Astro static site (reader-facing — M7)
  services/
    api/               Lambda handlers (topics CRUD, trigger, review, public)
    workers/           Step Functions Lambda workers (pipeline stages)
    openai-runtime/    OpenAI SDK adapter (only place openai is imported)
    content-build/     Search index + TOC builder
  packages/
    shared-types/      Pydantic models + DynamoDB trace writer
    prompt-policies/   Agent prompt style guide
  infra/
    terraform/
      modules/         One module per AWS resource group (13 modules)
      envs/dev/        Dev environment composition
  notebooks/           Jupyter end-to-end test harness (UC-01 → UC-15)
  docs/                Local dev guide, architecture notes
```

---

## Prerequisites

| Tool | Min version | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://www.python.org/downloads/) |
| Node.js | 20 | [nodejs.org](https://nodejs.org/) |
| Terraform | 1.7 | `choco install terraform` (Windows) · `brew install terraform` (Mac) |
| AWS CLI | 2.x | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| Docker | Latest | [docker.com](https://www.docker.com/) — optional, for Step Functions Local |

---

## Quick start — local development

### 1. Clone and configure credentials

```bash
git clone https://github.com/vaibhavmaurya/Agentic-EBook.git
cd Agentic-EBook
cp .env.local.example .env.local
```

Open `.env.local` and fill in your AWS dev credentials and resource names:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your_account_id

DYNAMODB_TABLE_NAME=ebook-platform-dev
S3_ARTIFACT_BUCKET=ebook-platform-artifacts-dev
STEP_FUNCTIONS_ARN=arn:aws:states:us-east-1:<account>:stateMachine:ebook-platform-dev-topic-pipeline

COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX

SES_SENDER_EMAIL=you@example.com
OWNER_EMAIL=you@example.com

OPENAI_SECRET_NAME=ebook-platform/openai-key
ADMIN_API_BASE_URL=http://localhost:8000
PUBLIC_API_BASE_URL=http://localhost:8000
ADMIN_USERNAME=you@example.com
ADMIN_PASSWORD=YourPassword
```

> All values are filled in automatically after you run `terraform apply` — see Step 2.

---

### 2. Provision AWS infrastructure

The dev environment is fully managed by Terraform. One `apply` creates all 83 AWS resources.

```bash
cd infra/terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set aws_account_id, ses_sender_email, owner_email
```

```bash
terraform init
terraform plan     # review — should show ~83 resources to create
terraform apply
```

After apply, note the outputs — copy them into `.env.local`:

```
api_endpoint         = "https://xxxx.execute-api.us-east-1.amazonaws.com"
cognito_user_pool_id = "us-east-1_XXXXXXX"
cognito_client_id    = "XXXXXXXXXXXXXXXXXXXXXXXXXX"
dynamodb_table_name  = "ebook-platform-dev"
s3_artifact_bucket   = "ebook-platform-artifacts-dev"
state_machine_arn    = "arn:aws:states:..."
```

**Create your admin user (one-time):**

```bash
# Create user
aws cognito-idp admin-create-user \
  --user-pool-id <cognito_user_pool_id> \
  --username you@example.com \
  --message-action SUPPRESS \
  --user-attributes Name=email,Value=you@example.com Name=email_verified,Value=true

# Set a permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <cognito_user_pool_id> \
  --username you@example.com \
  --password "YourPassword123!" \
  --permanent

# Add to admins group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <cognito_user_pool_id> \
  --username you@example.com \
  --group-name admins
```

**Set your OpenAI API key:**

```bash
aws secretsmanager put-secret-value \
  --secret-id ebook-platform/openai-key \
  --secret-string '{"api_key": "sk-..."}'
```

**Verify your SES sender email:**

Go to AWS Console → SES → Verified identities → verify `you@example.com`.
In the SES sandbox, the owner email also needs to be verified before digests can be sent.

---

### 3. Set up the Python environment

A single virtual environment at the repo root covers all services.

```bash
# From the repo root
python -m venv .venv

# Activate — choose your shell:
.venv\Scripts\activate.bat       # Windows CMD
.venv\Scripts\Activate.ps1       # Windows PowerShell
source .venv/bin/activate        # macOS / Linux

# Install all backend dependencies
pip install -r services/api/requirements.txt
pip install -e packages/shared-types
```

---

### 4. Start the API server

The server reads `.env.local` automatically — no need to export variables manually.

```bash
# With venv activated:
cd services/api
uvicorn local_dev_server:app --reload --port 8000

# Without activating venv (always works on Windows):
cd services/api
../../.venv/Scripts/python -m uvicorn local_dev_server:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
# → {"status": "ok", "env": "dev"}
```

Interactive API docs: **http://localhost:8000/docs**

---

### 5. Start the Admin UI

In a **separate terminal**:

```bash
cd apps/admin-site
npm install       # first time only
npm run dev
```

Open **http://localhost:3000** and sign in with your Cognito admin credentials.

The Vite dev server automatically proxies `/admin/*` and `/public/*` to `localhost:8000`.

---

### 6. (Optional) Run Step Functions locally

To develop pipeline workers without AWS Step Functions API costs:

```bash
docker run -p 8083:8083 \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  amazon/aws-stepfunctions-local
```

Then set `STEP_FUNCTIONS_ENDPOINT=http://localhost:8083` in `.env.local` and restart the API server.

---

### 7. Run the Jupyter test harness

The notebook exercises every API in use-case order (UC-01 through UC-15).

```bash
# With venv activated:
pip install -r notebooks/requirements.txt
jupyter notebook notebooks/ebook_platform_test_harness.ipynb
```

Run cells top-to-bottom for a full end-to-end test. Run **Cell Group 16 (PURGE)** at the end to clean up all test data from DynamoDB and S3.

---

## Running individual pipeline workers

Workers can be tested in isolation without running the full Step Functions pipeline:

```bash
# With venv activated and .env.local values exported:
source .env.local    # macOS/Linux
# Windows: run the server (which auto-loads .env.local) or set vars manually

python services/workers/topic_loader.py --topic-id <id> --run-id <run_id>
```

---

## Tearing down the dev environment

To destroy all AWS resources and stop incurring costs:

```bash
cd infra/terraform/envs/dev
terraform destroy
```

> The S3 artifact bucket has `force_destroy = true` in dev, so all objects are deleted automatically. See `infra/AWS.md` for details on cost and teardown options.

---

## Project documentation

| Document | Contents |
|---|---|
| `plan.md` | Full MVP plan — milestones, DynamoDB schema, pipeline stages, API endpoints |
| `DevelopmentPlan.md` | Stack decisions, MCP tools, environment variables reference |
| `action-item.md` | Session resume tracker — current milestone, what's next |
| `infra/AWS.md` | AWS service cost guide, Terraform provisioning + teardown |
| `services/API.md` | Full API reference with request/response examples and curl commands |
| `apps/UI.md` | Admin SPA design decisions, local dev guide, page map, test checklist |
| `docs/local-dev.md` | Detailed local development guide |
| `packages/prompt-policies/style_guide.md` | Agent prompt style guide |

---

## Milestone status

| # | Milestone | Status |
|---|---|---|
| 1 | Terraform Infrastructure Foundation | ✅ Complete |
| 2 | Topic CRUD API + Admin UI | ✅ Complete |
| 3 | Scheduling + Manual Trigger | ⏳ Pending |
| 4 | Multi-Agent Pipeline | ⏳ Pending |
| 5 | Admin Review + Approval | ⏳ Pending |
| 6 | Incremental Publishing | ⏳ Pending |
| 7 | Public Website | ⏳ Pending |
| 8 | Run History + Feedback UI | ⏳ Pending |
| 9 | Weekly Digest | ⏳ Pending |
| 10 | Jupyter Notebook Test Harness | ⏳ Pending |

---

## Tech stack

| Layer | Technology |
|---|---|
| Admin UI | React 19 + Vite 8 + TypeScript 6 |
| Public site | Astro (M7) |
| Auth | Amazon Cognito |
| API | API Gateway HTTP API + AWS Lambda (Python 3.12) |
| Orchestration | AWS Step Functions Standard Workflow |
| Scheduling | Amazon EventBridge Scheduler |
| AI | OpenAI Responses API (gpt-4o / gpt-4o-mini) |
| Metadata store | Amazon DynamoDB (single-table) |
| Artifact store | Amazon S3 |
| Secrets | AWS Secrets Manager |
| Email | Amazon SES |
| Hosting | AWS Amplify |
| IaC | Terraform 1.7+ |

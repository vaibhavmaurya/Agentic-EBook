# Local Development Guide — Agentic Ebook Platform V3

This guide walks you through setting up and running the entire application on your own
machine. Even in local mode, the application connects to **real AWS resources** (DynamoDB,
S3, Step Functions, Cognito) in a dev AWS account — there is no local mock of AWS.

---

## What You Will Have Running

| Service | URL | What it is |
|---|---|---|
| API Server | `http://localhost:8000` | Backend — handles all data operations |
| API Docs (Swagger) | `http://localhost:8000/docs` | Interactive API explorer |
| Admin UI | `http://localhost:3000` | Admin console — manage topics, review drafts |
| Public Site | `http://localhost:4321` | Reader-facing ebook website |

---

## Prerequisites

Install all of these before starting.

### 1. Python 3.12+
Download from [python.org](https://www.python.org/downloads/).
Verify: `python --version` → must show `3.12.x` or higher.

### 2. Node.js 20+
Download from [nodejs.org](https://nodejs.org/).
Verify: `node --version` → must show `v20.x` or higher.

### 3. AWS CLI v2
Download from [aws.amazon.com/cli](https://aws.amazon.com/cli/).
Verify: `aws --version` → must show `aws-cli/2.x`.

### 4. Terraform 1.7+
Download from [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform/downloads).
Verify: `terraform --version` → must show `1.7.x` or higher.

### 5. Git
Download from [git-scm.com](https://git-scm.com/).
Verify: `git --version`.

### 6. A Terminal
- **Windows**: Use Git Bash (installed with Git). Do **not** use Command Prompt or PowerShell for the shell scripts.
- **macOS / Linux**: Any terminal.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/vaibhavmaurya/Agentic-EBook.git
cd Agentic-EBook
```

All commands in this guide are run from the **repository root** (`Agentic-EBook/`) unless
stated otherwise.

---

## Step 2 — Get AWS Credentials

You need an AWS account with a dev IAM user. If you already have credentials skip to Step 3.

### 2a. Create an IAM User (AWS Console)

1. Open the [AWS IAM Console](https://console.aws.amazon.com/iam/).
2. Go to **Users → Create user**.
3. Name it `ebook-platform-dev`.
4. On the **Permissions** screen, choose **Attach policies directly** and attach:
   - `AmazonDynamoDBFullAccess`
   - `AmazonS3FullAccess`
   - `AWSStepFunctionsFullAccess`
   - `AmazonEventBridgeSchedulerFullAccess`
   - `AWSLambda_FullAccess`
   - `AmazonSESFullAccess`
   - `SecretsManagerReadWrite`
   - `AmazonCognitoPowerUser`
   - `IAMFullAccess` *(needed for Terraform to create IAM roles)*
5. After creating the user, go to **Security credentials → Create access key**.
6. Choose **Application running outside AWS** and download the CSV.

You now have an **Access Key ID** and **Secret Access Key**.

### 2b. Configure the AWS CLI

```bash
aws configure
# Enter:
#   AWS Access Key ID:     <your access key>
#   AWS Secret Access Key: <your secret key>
#   Default region:        us-east-1
#   Default output format: json
```

Verify it works:
```bash
aws sts get-caller-identity
# Should print your account ID and user ARN — no error
```

---

## Step 3 — Configure Environment Variables

```bash
cp .env.local.example .env.local
```

Open `.env.local` in any text editor and fill in the following. Leave everything else blank
for now — you will fill in more values after Terraform runs in Step 4.

```
AWS_ACCESS_KEY_ID=<your access key ID>
AWS_SECRET_ACCESS_KEY=<your secret access key>
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=<your 12-digit AWS account ID>
```

> Find your account ID: `aws sts get-caller-identity --query Account --output text`

---

## Step 4 — Provision AWS Infrastructure with Terraform

This step creates all the AWS resources the application needs (DynamoDB table, S3 bucket,
Lambda functions, Step Functions state machine, Cognito user pool, API Gateway, etc.).
**You only do this once per environment.**

```bash
cd infra/terraform/envs/dev

# Copy the example variables file
cp terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` and fill in these required values:
```hcl
aws_account_id  = "135671745449"      # your 12-digit account ID
aws_region      = "us-east-1"
ses_sender_email = "you@example.com"  # email you will verify with AWS SES
owner_email     = "you@example.com"   # where weekly digest emails go
alarm_email     = "you@example.com"   # where CloudWatch alarm emails go
```

Now provision:
```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

This takes 3–5 minutes. When it finishes you will see output like:
```
api_endpoint           = "https://abc123.execute-api.us-east-1.amazonaws.com"
cognito_user_pool_id   = "us-east-1_XXXXXXXX"
cognito_client_id      = "xxxxxxxxxxxxxxxxxxxx"
dynamodb_table_name    = "ebook-platform-dev"
s3_artifact_bucket     = "ebook-platform-artifacts-dev"
state_machine_arn      = "arn:aws:states:us-east-1:..."
schedule_group_name    = "ebook-platform-dev-topics"
```

Go back to the repo root and update `.env.local` with these values:
```
DYNAMODB_TABLE_NAME=ebook-platform-dev
S3_ARTIFACT_BUCKET=ebook-platform-artifacts-dev
STEP_FUNCTIONS_ARN=arn:aws:states:us-east-1:<account>:stateMachine:ebook-platform-dev-topic-pipeline
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
SCHEDULE_GROUP_NAME=ebook-platform-dev-topics
SCHEDULER_ROLE_ARN=arn:aws:iam::<account>:role/ebook-platform-dev-scheduler
ADMIN_API_BASE_URL=http://localhost:8000
PUBLIC_API_BASE_URL=http://localhost:8000
```

```bash
# Return to repo root
cd ../../../..
```

---

## Step 5 — Create the Cognito Admin User

The admin UI requires a login. Create your admin account with these three commands,
replacing `<POOL_ID>`, `<CLIENT_ID>`, and `<your-email>`:

```bash
# 1. Create the user
aws cognito-idp admin-create-user \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --temporary-password "TempPass123!" \
  --region us-east-1

# 2. Add to the admins group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --group-name admins \
  --region us-east-1

# 3. Set a permanent password (avoids the forced-reset flow)
aws cognito-idp admin-set-user-password \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --password "YourPassword123!" \
  --permanent \
  --region us-east-1
```

Add these to `.env.local`:
```
ADMIN_USERNAME=<your-email>
ADMIN_PASSWORD=YourPassword123!
```

---

## Step 6 — Store the OpenAI API Key

The AI pipeline uses OpenAI. Store the key securely in AWS Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id ebook-platform/openai-key \
  --secret-string '{"api_key": "sk-..."}' \
  --region us-east-1
```

Add to `.env.local`:
```
OPENAI_SECRET_NAME=ebook-platform/openai-key
```

---

## Step 7 — Verify Your SES Sender Email

AWS SES requires email verification before it can send:

```bash
aws sesv2 create-email-identity \
  --email-identity <your-email> \
  --region us-east-1
```

Check your inbox and click the verification link AWS sends you. Until you do this,
the pipeline's approval notification emails will fail.

Also add to `.env.local`:
```
SES_SENDER_EMAIL=<your-email>
OWNER_EMAIL=<your-email>
```

---

## Step 8 — Install Python Dependencies

```bash
# Create a virtual environment at the repo root
python -m venv .venv

# Activate it (do this every new terminal session)
# Git Bash / macOS / Linux:
source .venv/Scripts/activate     # Windows Git Bash
# source .venv/bin/activate       # macOS / Linux

# Install API and worker dependencies
pip install -r services/api/requirements.txt

# Install shared-types as an editable local package
pip install -e packages/shared-types
```

> **Windows tip:** If you see `uvicorn: command not found`, run `python -m uvicorn` instead.

---

## Step 9 — Start the API Server

Open a **dedicated terminal** for this and keep it running:

```bash
# Make sure the venv is activated first
cd services/api
uvicorn local_dev_server:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

Verify it works:
```bash
# In a new terminal tab
curl http://localhost:8000/health
# Expected: {"status":"ok","env":"local"}
```

**Swagger UI** is now live at [http://localhost:8000/docs](http://localhost:8000/docs) —
open this in your browser to explore and try all API endpoints interactively.

---

## Step 10 — Start the Admin UI

Open a **second dedicated terminal**:

```bash
cd apps/admin-site
npm install
npm run dev
```

You should see:
```
  VITE v5.x ready in xxx ms
  ➜  Local:   http://localhost:3000/
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

**Login:** Use the email and password you set in Step 5.

> The admin UI automatically proxies all API calls (`/admin/*`, `/public/*`) to your local
> API server on port 8000 — no extra configuration needed.

---

## Step 11 — Start the Public Site

Open a **third dedicated terminal**:

```bash
cd apps/public-site
npm install
npm run dev
```

You should see:
```
 astro  v4.x  ready in xxx ms
  🚀  http://localhost:4321/
```

Open [http://localhost:4321](http://localhost:4321) in your browser.

The public site shows the ebook content — it starts empty until you publish a topic.

---

## How to Test the Full Application Flow

With all three servers running, follow this sequence to exercise the complete pipeline.

### Step A — Create a Topic (Admin UI or API)

**Via Admin UI:** Go to [http://localhost:3000](http://localhost:3000), log in, click
**New Topic**, fill in Title and Instructions, click **Save**.

**Via API (Swagger UI):**
1. Open [http://localhost:8000/docs](http://localhost:8000/docs).
2. Click **Authorize** (top right), paste your Cognito token (see below for how to get one).
3. Expand `POST /admin/topics`, click **Try it out**, paste the example body, click **Execute**.

Getting a Cognito token for the Swagger UI:
```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=<your-email>,PASSWORD=<your-password> \
  --client-id <COGNITO_CLIENT_ID> \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

### Step B — Trigger the AI Pipeline

In the Admin UI, find your topic and click **Run Now**. This starts the Step Functions
pipeline which runs through all AI agent stages. The pipeline takes 3–10 minutes depending
on topic complexity.

**What happens during the pipeline:**
1. Loads your topic configuration
2. Plans a research strategy (AI)
3. Searches the web and collects evidence (AI)
4. Verifies evidence quality (AI)
5. Writes a chapter draft (AI)
6. Edits and scores the draft (AI)
7. Compares to prior published version (AI)
8. Sends you an approval email and **pauses**

### Step C — Review and Approve

When the pipeline pauses, the Admin UI shows the draft in the **Review Queue**. Click on
it to see:
- The full draft content
- A diff vs the previous published version
- Editorial quality scorecard

Click **Approve** to publish, or **Reject** with notes to discard.

### Step D — See the Published Content

After approval, the public site at [http://localhost:4321](http://localhost:4321) rebuilds
its index and the new topic appears. Readers can search, highlight text, and add comments.

---

## Running the Jupyter Notebook Test Harness

The notebook runs the complete UC-01 → UC-15 test sequence automatically:

```bash
# Install notebook dependencies (one time)
pip install -r notebooks/requirements.txt

# Launch Jupyter
jupyter notebook notebooks/ebook_platform_test_harness.ipynb
```

Run all cells top-to-bottom. After testing, run **Cell Group 16 (PURGE)** to clean up all
test data from your dev AWS account.

---

## Useful Diagnostic Commands

```bash
# Check what topics exist in DynamoDB
aws dynamodb scan \
  --table-name ebook-platform-dev \
  --filter-expression "ENTITY_TYPE = :t" \
  --expression-attribute-values '{":t":{"S":"TOPIC"}}' \
  --region us-east-1 \
  --query 'Items[].{id:topic_id.S,title:title.S}' \
  --output table

# List S3 artifacts for a topic run
aws s3 ls s3://ebook-platform-artifacts-dev/topics/<topic_id>/ --recursive

# Check a Step Functions execution
aws stepfunctions describe-execution \
  --execution-arn <execution_arn> \
  --region us-east-1 \
  --query '{status:status,started:startDate,stopped:stopDate}'

# Get a fresh Cognito token
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=$ADMIN_USERNAME,PASSWORD=$ADMIN_PASSWORD \
  --client-id $COGNITO_CLIENT_ID \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `NoCredentialsError` on startup | `.env.local` not loaded | Make sure you're running from `services/api/` — dotenv loads from repo root automatically |
| `ResourceNotFoundException` on DynamoDB | Terraform not applied | Run `terraform apply` in `infra/terraform/envs/dev` |
| `AccessDeniedException` on DynamoDB | IAM permissions missing | Verify your IAM user has DynamoDB permissions |
| Admin UI login fails | Wrong credentials or Cognito user not created | Redo Step 5 |
| Admin UI shows blank / 502 errors | API server not running | Start the API server (Step 9) and check its terminal for errors |
| Pipeline fails at NotifyAdmin | SES email not verified | Complete Step 7 and click the verification link in your inbox |
| OpenAI calls fail | Secret not stored | Run the `secretsmanager put-secret-value` command in Step 6 |
| Port 3000/4321 already in use | Another process is using it | Kill the other process or change the port in `vite.config.ts` / `astro.config.mjs` |
| `uvicorn: command not found` | venv not activated | Run `source .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Mac/Linux) |
| Step Functions execution stuck | Pipeline paused at WaitForApproval | This is normal — go to Admin UI and approve/reject the draft |

---

## Summary of Running Services

Keep these three terminals open while developing:

| Terminal | Command | URL |
|---|---|---|
| 1 — API | `cd services/api && uvicorn local_dev_server:app --reload --port 8000` | http://localhost:8000 |
| 2 — Admin UI | `cd apps/admin-site && npm run dev` | http://localhost:3000 |
| 3 — Public Site | `cd apps/public-site && npm run dev` | http://localhost:4321 |

# AWS Deployment Guide — Agentic Ebook Platform V3

This guide walks you through deploying the complete application to AWS from scratch and
verifying that it works end-to-end. Follow every step in order.

---

## What You Will Have Running

| Component | AWS Service | Live URL (dev) |
|---|---|---|
| Admin UI | AWS Amplify | `https://dev.d200xw9mmlu4wj.amplifyapp.com` |
| Public Site | AWS Amplify | `https://dev.djcvgu9ysuar.amplifyapp.com` |
| API | API Gateway + Lambda | `https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com` |
| AI Pipeline | Step Functions + Lambda | AWS Console only |
| Data | DynamoDB + S3 | AWS Console only |

> URLs above are for the existing dev deployment. If you are setting up a fresh account,
> your URLs will be different — Terraform outputs them after `apply`.

---

## Prerequisites

Install these tools on your local machine before starting.

| Tool | Version | How to install |
|---|---|---|
| AWS CLI | 2.x | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| Python | 3.12+ | [python.org/downloads](https://www.python.org/downloads/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| Terraform | 1.7+ | [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform/downloads) |
| Git | Any | [git-scm.com](https://git-scm.com/) |
| Git Bash | Any | Included with Git on Windows |

> **Windows users:** All shell commands in this guide must be run in **Git Bash**, not
> PowerShell or Command Prompt.

Verify each tool is installed:
```bash
aws --version       # aws-cli/2.x
python --version    # Python 3.12.x
node --version      # v20.x
terraform --version # Terraform v1.7.x
git --version
```

---

## Part 1 — One-Time AWS Account Setup

Do Part 1 only once per AWS account. If you are redeploying to an existing account, skip
to Part 2.

### Step 1 — Clone the Repository

```bash
git clone https://github.com/vaibhavmaurya/Agentic-EBook.git
cd Agentic-EBook
```

All commands are run from the **repository root** (`Agentic-EBook/`) unless stated otherwise.

### Step 2 — Create an IAM User for Deployments

The deploy scripts and Terraform need AWS credentials with sufficient permissions.

1. Sign in to the [AWS Console](https://console.aws.amazon.com/).
2. Go to **IAM → Users → Create user**.
3. Name it `ebook-platform-deployer`.
4. On the **Permissions** screen choose **Attach policies directly** and attach:
   - `AmazonDynamoDBFullAccess`
   - `AmazonS3FullAccess`
   - `AWSStepFunctionsFullAccess`
   - `AmazonEventBridgeSchedulerFullAccess`
   - `AWSLambda_FullAccess`
   - `AmazonSESFullAccess`
   - `SecretsManagerReadWrite`
   - `AmazonCognitoPowerUser`
   - `AmazonAPIGatewayAdministrator`
   - `IAMFullAccess` *(Terraform creates IAM roles)*
   - `AmplifyBackendDeployFullAccess`
5. After creating the user, go to **Security credentials → Create access key**.
6. Select **Application running outside AWS** and download the CSV file.

### Step 3 — Configure AWS CLI

```bash
aws configure
```

Enter when prompted:
```
AWS Access Key ID:     <from the CSV>
AWS Secret Access Key: <from the CSV>
Default region name:   us-east-1
Default output format: json
```

Verify:
```bash
aws sts get-caller-identity
# Prints: Account, UserId, Arn — no error
```

### Step 4 — Create the Environment File

```bash
cp .env.local.example .env.local
```

Open `.env.local` and fill in the credentials section:
```
AWS_ACCESS_KEY_ID=<your access key ID>
AWS_SECRET_ACCESS_KEY=<your secret access key>
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=<your 12-digit account ID>
```

Find your account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### Step 5 — Provision AWS Infrastructure with Terraform

This creates every AWS resource the application needs.

```bash
cd infra/terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` and set these required values:
```hcl
aws_account_id   = "<your 12-digit account ID>"
aws_region       = "us-east-1"
ses_sender_email = "you@example.com"   # must be an email you own
owner_email      = "you@example.com"   # receives weekly digest
alarm_email      = "you@example.com"   # receives CloudWatch alerts
```

Apply:
```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

This takes 3–5 minutes. When complete, note the output values:
```
api_endpoint           = "https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com"
cognito_user_pool_id   = "us-east-1_XXXXXXXXX"
cognito_client_id      = "xxxxxxxxxxxxxxxxxxxx"
dynamodb_table_name    = "ebook-platform-dev"
s3_artifact_bucket     = "ebook-platform-artifacts-dev"
state_machine_arn      = "arn:aws:states:us-east-1:<account>:stateMachine:ebook-platform-dev-topic-pipeline"
schedule_group_name    = "ebook-platform-dev-topics"
```

Go back to the repo root and add these to `.env.local`:
```bash
cd ../../../..
```

```
DYNAMODB_TABLE_NAME=ebook-platform-dev
S3_ARTIFACT_BUCKET=ebook-platform-artifacts-dev
STEP_FUNCTIONS_ARN=arn:aws:states:us-east-1:<account>:stateMachine:ebook-platform-dev-topic-pipeline
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
SCHEDULE_GROUP_NAME=ebook-platform-dev-topics
SCHEDULER_ROLE_ARN=arn:aws:iam::<account>:role/ebook-platform-dev-scheduler
```

### Step 6 — Create the Admin Cognito User

Replace `<POOL_ID>`, and `<your-email>` with your values:

```bash
# Create the user account
aws cognito-idp admin-create-user \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --temporary-password "TempPass123!" \
  --region us-east-1

# Add to the admins group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --group-name admins \
  --region us-east-1

# Set a permanent password (skips the forced-reset on first login)
aws cognito-idp admin-set-user-password \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --password "YourPassword123!" \
  --permanent \
  --region us-east-1
```

Add to `.env.local`:
```
ADMIN_USERNAME=<your-email>
ADMIN_PASSWORD=YourPassword123!
```

### Step 7 — Store the OpenAI API Key

```bash
aws secretsmanager put-secret-value \
  --secret-id ebook-platform/openai-key \
  --secret-string '{"api_key": "sk-...your-key..."}' \
  --region us-east-1
```

Add to `.env.local`:
```
OPENAI_SECRET_NAME=ebook-platform/openai-key
```

### Step 8 — Verify the SES Sender Email

AWS SES must verify your email address before it can send notifications:

```bash
aws sesv2 create-email-identity \
  --email-identity <your-email> \
  --region us-east-1
```

Check your inbox for a verification email from AWS and click the link. The pipeline's
approval notification emails will fail until this is done.

Add to `.env.local`:
```
SES_SENDER_EMAIL=<your-email>
OWNER_EMAIL=<your-email>
```

---

## Part 2 — Deploy Application Code

Run these steps whenever you want to deploy or redeploy code to AWS.

### Step 9 — Load Environment Variables

Before running any deploy script, load your environment variables into the shell session:

```bash
# Git Bash / Linux / macOS
export $(cat .env.local | grep -v '#' | grep -v '^$' | xargs)

# Verify the variables loaded
echo $AWS_REGION        # should print: us-east-1
echo $S3_ARTIFACT_BUCKET  # should print: ebook-platform-artifacts-dev
```

> You must do this once per terminal session. If you open a new terminal, run this command
> again before deploying.

### Step 10 — Deploy the API Lambda

The API Lambda handles all backend routes (`/admin/*` and `/public/*`).

```bash
bash scripts/deploy_api.sh
```

Expected output:
```
── Building API Lambda → ebook-platform-dev-api ──
Created .build/api/api.zip (2589 KB, 181 files)
  Uploading to s3://ebook-platform-artifacts-dev/deployments/api.zip …
ebook-platform-dev-api
  ✓ ebook-platform-dev-api deployed

✓ API deployment complete.
```

**Verify it works:**
```bash
# Should return 401 (auth is working), not 502 (Lambda is broken)
curl -s https://<your-api-id>.execute-api.us-east-1.amazonaws.com/admin/topics \
  -H "Authorization: Bearer invalid"
# Expected: {"message":"Unauthorized"}

# Public endpoint — no auth required
curl -s https://<your-api-id>.execute-api.us-east-1.amazonaws.com/public/releases/latest
# Expected: {"releases":[],"count":0}
```

### Step 11 — Deploy the Worker Lambdas

Workers run the AI pipeline stages inside Step Functions.

```bash
# Deploy all 14 workers (takes ~10 minutes)
bash scripts/deploy_workers.sh

# Or deploy a single worker during development
bash scripts/deploy_workers.sh topic_loader
```

Expected output for each worker:
```
── Building topic_loader → ebook-platform-dev-topic-loader ──
Created .build/workers/topic_loader.zip (2631 KB, 180 files)
  ✓ ebook-platform-dev-topic-loader deployed
```

### Step 12 — Deploy the Frontend Applications

This builds and deploys both the Admin UI and Public Site to AWS Amplify.

```bash
# Deploy both sites (takes ~5 minutes total)
bash scripts/deploy_frontend.sh

# Or deploy one site at a time
bash scripts/deploy_frontend.sh admin    # Admin UI only
bash scripts/deploy_frontend.sh public   # Public Site only
```

Expected output:
```
── Admin SPA ──────────────────────────────────────────────────────────
  App ID: d200xw9mmlu4wj  Branch: dev
  Zipped dist → /tmp/ebook-platform-admin-dev-deploy.zip
  HTTP 200
  Waiting for deployment to complete…
  Status: SUCCEED
  ✓ Deployed: https://dev.d200xw9mmlu4wj.amplifyapp.com

── Public Site ────────────────────────────────────────────────────────
  App ID: djcvgu9ysuar  Branch: dev
  ...
  ✓ Deployed: https://dev.djcvgu9ysuar.amplifyapp.com

✓ Frontend deployment complete.
```

---

## Part 3 — Verify the Deployment

Run these checks after every deployment to confirm everything is working.

### Check 1 — API Gateway

```bash
API_URL="https://<your-api-id>.execute-api.us-east-1.amazonaws.com"

# Public endpoint — no token needed
curl -s "$API_URL/public/releases/latest"
# Expected: {"releases":[],"count":0}
```

### Check 2 — Get a Cognito Token and Call the Admin API

```bash
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=$ADMIN_USERNAME,PASSWORD=$ADMIN_PASSWORD \
  --client-id $COGNITO_CLIENT_ID \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text)

curl -s "$API_URL/admin/topics" \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"topics":[],"count":0}
```

### Check 3 — Amplify Sites

```bash
# Admin UI — should return 200
curl -s -o /dev/null -w "%{http_code}" \
  https://dev.d200xw9mmlu4wj.amplifyapp.com
# Expected: 200

# Public Site — should return 200
curl -s -o /dev/null -w "%{http_code}" \
  https://dev.djcvgu9ysuar.amplifyapp.com
# Expected: 200
```

### Check 4 — Lambda Package Size (not the skeleton)

```bash
aws lambda get-function-configuration \
  --function-name ebook-platform-dev-api \
  --query '{LastModified:LastModified,CodeSize:CodeSize}' \
  --region us-east-1
# CodeSize should be ~2.5MB or larger — the skeleton is only ~1KB
```

---

## Part 4 — Test the Complete Application Flow

Log in to the Admin UI and walk through the full content lifecycle.

### Step A — Log In to the Admin UI

Open `https://dev.d200xw9mmlu4wj.amplifyapp.com` in your browser.

Enter your Cognito credentials (the email and password from Step 6). You should see the
topic management dashboard.

### Step B — Create a Topic

1. Click **New Topic**.
2. Fill in:
   - **Title**: e.g. `Introduction to Large Language Models`
   - **Description**: A brief summary of what this topic covers.
   - **Instructions**: Detailed guidance for the AI agents — audience, tone, length, areas to cover.
   - **Schedule**: Leave as `Manual` for testing.
3. Click **Save**.

The topic appears in the list with status **Idle**.

### Step C — Trigger the AI Pipeline

1. Click the **Run Now** button next to your topic.
2. The status changes to **Running**.
3. Go to **AWS Console → Step Functions** to watch the pipeline progress in real time.

The pipeline runs these stages automatically (takes 5–15 minutes):

```
LoadTopicConfig
  └── AssembleTopicContext
        └── PlanTopic        (AI — gpt-4o-mini)
              └── ResearchTopic   (AI — gpt-4o, searches the web)
                    └── VerifyEvidence  (AI — gpt-4o-mini)
                          └── PersistEvidenceArtifacts
                                └── DraftChapter     (AI — gpt-4o)
                                      └── EditorialReview  (AI — gpt-4o)
                                            └── BuildDraftArtifact
                                                  └── GenerateDiffReleaseNotes  (AI)
                                                        └── NotifyAdminForReview
                                                              └── ★ WaitForApproval (pauses here)
```

You receive an **email notification** when the pipeline reaches WaitForApproval.

### Step D — Review and Approve the Draft

1. In the Admin UI, go to the **Review Queue** (bell icon or sidebar link).
2. Click on the pending draft for your topic.
3. Review:
   - The full drafted content
   - The diff vs previous published version (empty on first run)
   - The editorial scorecard (clarity, accuracy, completeness scores)
4. Click **Approve** to publish, or **Reject** with a note to discard.

After approval, the pipeline continues automatically to publish the content.

### Step E — View the Published Content

Open the Public Site: `https://dev.djcvgu9ysuar.amplifyapp.com`

Your topic should now appear in the table of contents. Click it to read the content.
The search index is rebuilt automatically after every publish.

### Step F — Submit Reader Feedback

On any topic page on the Public Site:
- **Highlight** any text to save a highlight (stored with `PENDING` status for admin review)
- **Comment** on a section using the comment widget

View all feedback in the Admin UI under **Feedback**.

---

## Redeploying After Code Changes

| What you changed | Command to run |
|---|---|
| `services/api/*.py` | `bash scripts/deploy_api.sh` |
| `services/workers/<name>.py` | `bash scripts/deploy_workers.sh <name>` |
| All worker files | `bash scripts/deploy_workers.sh` |
| `apps/admin-site/src/**` | `bash scripts/deploy_frontend.sh admin` |
| `apps/public-site/src/**` | `bash scripts/deploy_frontend.sh public` |
| `infra/terraform/**` | `cd infra/terraform/envs/dev && terraform apply` |

Always load environment variables before running deploy scripts:
```bash
export $(cat .env.local | grep -v '#' | grep -v '^$' | xargs)
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `deploy_api.sh` fails with `NoSuchBucket` | S3 bucket not created | Run `terraform apply` — it creates the bucket |
| `deploy_workers.sh` fails on pip install | Missing manylinux wheel | Check your Python version is 3.12 and pip is up to date |
| API returns `502 Bad Gateway` | Lambda crashed at import | Check CloudWatch: `aws logs tail /aws/lambda/ebook-platform-dev-api --follow` |
| API returns `401` on all requests | Cognito JWT expired | Tokens expire after 1 hour — get a fresh token |
| Pipeline fails at `LoadTopicConfig` | Topic not in DynamoDB | Verify the topic was saved via `POST /admin/topics` first |
| Pipeline fails with `NoCredentialsError` | Lambda env vars missing | Check Lambda → Configuration → Environment variables in AWS Console |
| OpenAI calls fail with auth error | Wrong key in Secrets Manager | Re-run the `secretsmanager put-secret-value` command |
| Approval email not received | SES not verified | Complete Step 8 and click the verification link |
| Amplify shows old content | Build cache | Trigger a new deploy: `bash scripts/deploy_frontend.sh public` |
| `AccessDeniedException` on DynamoDB | IAM role missing Scan permission | Run `terraform apply` — it adds the missing permissions |
| Frontend deploy fails with `app not found` | Wrong Amplify app name | Verify `DEPLOY_ENV=dev` and that Terraform created the Amplify apps |

### Viewing Lambda Logs

```bash
# API Lambda logs (last 10 minutes)
aws logs tail /aws/lambda/ebook-platform-dev-api \
  --since 10m --follow --region us-east-1

# Specific worker logs
aws logs tail /aws/lambda/ebook-platform-dev-planner-worker \
  --since 10m --follow --region us-east-1
```

### Checking Step Functions Execution

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn $STEP_FUNCTIONS_ARN \
  --region us-east-1 \
  --query 'executions[0:5].{status:status,name:name,start:startDate}' \
  --output table

# Get details of a specific execution
aws stepfunctions describe-execution \
  --execution-arn <execution_arn> \
  --region us-east-1 \
  --query '{status:status,error:error,cause:cause}'
```

---

## Environment Variable Reference

Complete list of all variables in `.env.local`:

| Variable | Description | Example |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key | `AKIAR7...` |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key | `Xa6u...` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `AWS_ACCOUNT_ID` | 12-digit account ID | `135671745449` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name (Terraform output) | `ebook-platform-dev` |
| `S3_ARTIFACT_BUCKET` | S3 bucket name (Terraform output) | `ebook-platform-artifacts-dev` |
| `STEP_FUNCTIONS_ARN` | State machine ARN (Terraform output) | `arn:aws:states:...` |
| `COGNITO_USER_POOL_ID` | Cognito pool ID (Terraform output) | `us-east-1_XXXXXXXXX` |
| `COGNITO_CLIENT_ID` | Cognito app client ID (Terraform output) | `5g3o4j...` |
| `SCHEDULE_GROUP_NAME` | EventBridge schedule group (Terraform output) | `ebook-platform-dev-topics` |
| `SCHEDULER_ROLE_ARN` | IAM role for EventBridge → SFN | `arn:aws:iam::...` |
| `SES_SENDER_EMAIL` | Verified SES sender email | `you@example.com` |
| `OWNER_EMAIL` | Digest recipient email | `you@example.com` |
| `OPENAI_SECRET_NAME` | Secrets Manager key name | `ebook-platform/openai-key` |
| `ADMIN_USERNAME` | Cognito admin email | `you@example.com` |
| `ADMIN_PASSWORD` | Cognito admin password | `YourPassword123!` |
| `ADMIN_API_BASE_URL` | API base for local dev (not used in AWS) | `http://localhost:8000` |
| `PUBLIC_API_BASE_URL` | Public API base for local dev (not used in AWS) | `http://localhost:8000` |

---

## Production Deployment

When you are ready to deploy to a production environment, the process is identical but
uses a separate Terraform workspace:

```bash
# 1. Create the prod Terraform environment (copy from dev)
cp -r infra/terraform/envs/dev infra/terraform/envs/prod
# Edit infra/terraform/envs/prod/terraform.tfvars with prod-specific values

# 2. Apply prod infrastructure
cd infra/terraform/envs/prod
terraform init
terraform apply

# 3. Deploy with DEPLOY_ENV=prod
DEPLOY_ENV=prod bash scripts/deploy_api.sh
DEPLOY_ENV=prod bash scripts/deploy_workers.sh
DEPLOY_ENV=prod bash scripts/deploy_frontend.sh
```

Key differences to address for production:
- Request SES production access from AWS (removes the sandbox limitation)
- Set up a custom domain in Amplify (Route 53 or your DNS provider)
- Tighten API Gateway rate limits
- Configure CloudWatch SNS alarm notifications to an ops distribution list
- Use separate AWS credentials (or a separate AWS account) for prod deployments

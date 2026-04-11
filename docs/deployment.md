# Deployment Guide — Agentic Ebook Platform V3

This guide covers deploying the application to AWS for both **dev** and **prod** environments.

---

## Live URLs (Dev Environment)

| Service | URL |
|---|---|
| **Admin UI** | https://dev.d200xw9mmlu4wj.amplifyapp.com |
| **Public Site** | https://dev.djcvgu9ysuar.amplifyapp.com |
| **API (base URL)** | https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com |
| **API — topic list** | `GET /admin/topics` (requires Cognito JWT) |
| **API — public releases** | `GET /public/releases/latest` (no auth) |

---

## Architecture Overview

```
                    ┌─────────────────────┐
                    │   AWS Amplify CDN    │
                    │  admin-site (React)  │
                    │  public-site (Astro) │
                    └─────────┬───────────┘
                              │ HTTPS
                    ┌─────────▼───────────┐
                    │   API Gateway        │
                    │   HTTP API           │
                    │   (Cognito JWT auth  │
                    │    on /admin/*)      │
                    └─────────┬───────────┘
                              │ Lambda invoke
              ┌───────────────┼───────────────────┐
              │               │                   │
   ┌──────────▼───┐  ┌────────▼──────┐  ┌────────▼──────┐
   │ API Lambda   │  │ Step Functions │  │  EventBridge  │
   │ topics.py    │  │ Pipeline       │  │  Scheduler    │
   │ reviews.py   │  │ (14 workers)   │  │  (weekly      │
   │ public.py    │  │                │  │   digest)     │
   │ feedback.py  │  └────────┬───────┘  └───────────────┘
   └──────────────┘           │
              ┌───────────────┼───────────────────┐
              │               │                   │
   ┌──────────▼───┐  ┌────────▼──────┐  ┌────────▼──────┐
   │  DynamoDB    │  │     S3        │  │  Secrets Mgr  │
   │  (metadata)  │  │  (artifacts + │  │  (OpenAI key) │
   │              │  │   site files) │  │               │
   └──────────────┘  └───────────────┘  └───────────────┘
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| AWS CLI | 2.x | Deploy scripts and credential management |
| Python | 3.12+ | Lambda packaging |
| Node.js | 20+ | Frontend builds |
| Terraform | 1.7+ | Infrastructure provisioning |
| Git Bash / WSL | any | Running `.sh` deploy scripts on Windows |

Install Python zipdir helper (used by deploy scripts):
```bash
# Already included at scripts/zipdir.py — no install needed
```

---

## First-Time Setup

### 1. Clone and configure credentials

```bash
git clone https://github.com/vaibhavmaurya/Agentic-EBook.git
cd Agentic-EBook
cp .env.local.example .env.local
```

Edit `.env.local` with your AWS credentials and resource names (see `.env.local.example` for all fields).

### 2. Provision AWS infrastructure (Terraform)

```bash
cd infra/terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your account ID, region, email addresses
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Terraform creates:
- DynamoDB table `ebook-platform-dev` (5 GSIs)
- S3 bucket `ebook-platform-artifacts-dev`
- 15 Lambda functions (skeleton handlers — real code deployed separately)
- API Gateway HTTP API
- Step Functions state machine
- Cognito user pool
- EventBridge Scheduler group + weekly digest schedule
- Amplify apps for admin and public sites
- SES email identity
- CloudWatch alarms and dashboard

After `apply`, copy the output values into `.env.local`:
```
DYNAMODB_TABLE_NAME=ebook-platform-dev
S3_ARTIFACT_BUCKET=ebook-platform-artifacts-dev
STEP_FUNCTIONS_ARN=arn:aws:states:us-east-1:<account>:stateMachine:...
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXX
```

### 3. Create the Cognito admin user

```bash
# Create user
aws cognito-idp admin-create-user \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --temporary-password "TempPass123!" \
  --region us-east-1

# Add to admins group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --group-name ebook-admins \
  --region us-east-1

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <POOL_ID> \
  --username <your-email> \
  --password "YourPermanentPass123!" \
  --permanent \
  --region us-east-1
```

Update `.env.local`:
```
ADMIN_USERNAME=<your-email>
ADMIN_PASSWORD=YourPermanentPass123!
```

### 4. Store the OpenAI API key

```bash
aws secretsmanager put-secret-value \
  --secret-id ebook-platform/openai-key \
  --secret-string '{"api_key": "sk-..."}' \
  --region us-east-1
```

### 5. Verify SES sender email

```bash
aws sesv2 create-email-identity \
  --email-identity <your-email> \
  --region us-east-1
# Check your inbox and click the verification link
```

---

## Deploying Application Code

All deploy scripts are in `scripts/`. Run from the **repo root** with `.env.local` sourced.

```bash
# Source credentials once per terminal session
source .env.local   # macOS/Linux
# Windows Git Bash:
export $(cat .env.local | grep -v '#' | xargs)
```

### Deploy the API Lambda

```bash
bash scripts/deploy_api.sh
```

Packages `services/api/{topics,reviews,public,feedback}.py` + `packages/shared-types` → uploads to S3 → updates Lambda `ebook-platform-dev-api`.

Expected output:
```
── Building API Lambda → ebook-platform-dev-api ──
Created .build/api/api.zip (2589 KB, 181 files)
  Uploading to s3://ebook-platform-artifacts-dev/deployments/api.zip …
ebook-platform-dev-api
  ✓ ebook-platform-dev-api deployed
```

### Deploy all worker Lambdas

```bash
bash scripts/deploy_workers.sh          # all 14 workers
bash scripts/deploy_workers.sh topic_loader   # single worker
```

AI workers (planner, research, verifier, draft, editorial, diff) automatically include the `openai_runtime` module and `openai` package (~4.7 MB each). Standalone workers are ~2.5 MB.

### Deploy frontend apps

```bash
bash scripts/deploy_frontend.sh         # both admin + public
bash scripts/deploy_frontend.sh admin   # admin SPA only
bash scripts/deploy_frontend.sh public  # public Astro site only
```

The script:
1. Queries API Gateway and Cognito for the correct env vars
2. Runs `npm run build`
3. Creates a deployment slot in Amplify
4. Uploads the `dist/` folder
5. Polls until the deployment status is `SUCCEED`

---

## Environment Variable Reference (`.env.local`)

| Variable | Description | Example |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key | `AKIAR7...` |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret | `Xa6u...` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `AWS_ACCOUNT_ID` | 12-digit account ID | `135671745449` |
| `DYNAMODB_TABLE_NAME` | DDB table name | `ebook-platform-dev` |
| `S3_ARTIFACT_BUCKET` | S3 bucket name | `ebook-platform-artifacts-dev` |
| `STEP_FUNCTIONS_ARN` | State machine ARN | `arn:aws:states:...` |
| `STEP_FUNCTIONS_ENDPOINT` | Leave blank for real SFN; set to `http://localhost:8083` for local emulator | |
| `SCHEDULE_GROUP_NAME` | EventBridge schedule group | `ebook-platform-dev-topics` |
| `SCHEDULER_ROLE_ARN` | IAM role for EventBridge → SFN | `arn:aws:iam::...` |
| `COGNITO_USER_POOL_ID` | Cognito pool | `us-east-1_R4FK1QHyr` |
| `COGNITO_CLIENT_ID` | Cognito app client | `5g3o4j...` |
| `SES_SENDER_EMAIL` | Verified SES sender | `you@example.com` |
| `OWNER_EMAIL` | Digest recipient | `you@example.com` |
| `OPENAI_SECRET_NAME` | Secrets Manager key name | `ebook-platform/openai-key` |
| `ADMIN_API_BASE_URL` | API base for local dev | `http://localhost:8000` |
| `PUBLIC_API_BASE_URL` | Public API base for local dev | `http://localhost:8000` |
| `ADMIN_USERNAME` | Cognito admin email | `you@example.com` |
| `ADMIN_PASSWORD` | Cognito admin password | `...` |

---

## Production Deployment

For `prod`, the process is identical but uses a separate Terraform workspace:

```bash
# 1. Provision prod infrastructure
cd infra/terraform/envs/prod   # (copy/adapt from envs/dev when ready)
terraform init
terraform apply

# 2. Deploy with DEPLOY_ENV=prod
DEPLOY_ENV=prod bash scripts/deploy_api.sh
DEPLOY_ENV=prod bash scripts/deploy_workers.sh
DEPLOY_ENV=prod bash scripts/deploy_frontend.sh
```

Key differences from dev:
- Separate DynamoDB table (`ebook-platform-prod`)
- Separate S3 bucket (`ebook-platform-artifacts-prod`)
- Separate Amplify apps / custom domain
- API Gateway rate limiting tighter
- SES out of sandbox (requires production access request to AWS)
- CloudWatch alarm SNS notifications to an ops email

> **Note:** A `prod` Terraform environment directory has not yet been created. Copy `infra/terraform/envs/dev/` and update `terraform.tfvars` with prod-specific values.

---

## Verifying a Deployment

### API Gateway health check
```bash
# Should return 401 (Cognito working), not 502 (Lambda broken)
curl -s https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com/admin/topics \
  -H "Authorization: Bearer invalid"
# Expected: {"message":"Unauthorized"}

# Public endpoint — no auth required
curl -s https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com/public/releases/latest
# Expected: {"releases":[],"count":0}
```

### Get a real Cognito token and call the admin API
```bash
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=<email>,PASSWORD=<pass> \
  --client-id <client_id> \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text)

curl -s https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com/admin/topics \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"topics":[],"count":0}
```

### Amplify site check
```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://dev.djcvgu9ysuar.amplifyapp.com
# Expected: 200

curl -s -o /dev/null -w "%{http_code}" \
  https://dev.d200xw9mmlu4wj.amplifyapp.com
# Expected: 200
```

### Check Lambda code is no longer the skeleton
```bash
aws lambda get-function-configuration \
  --function-name ebook-platform-dev-api \
  --query '{LastModified:LastModified,CodeSize:CodeSize}' \
  --region us-east-1
# CodeSize should be ~2.5MB (not ~1KB skeleton)
```

---

## Re-deploying After Code Changes

| Changed files | Command |
|---|---|
| `services/api/*.py` | `bash scripts/deploy_api.sh` |
| `services/workers/<name>.py` | `bash scripts/deploy_workers.sh <name>` |
| `services/workers/*.py` (all) | `bash scripts/deploy_workers.sh` |
| `apps/admin-site/src/**` | `bash scripts/deploy_frontend.sh admin` |
| `apps/public-site/src/**` | `bash scripts/deploy_frontend.sh public` |
| `infra/terraform/**` | `cd infra/terraform/envs/dev && terraform apply` |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| API returns 502 Bad Gateway | Lambda crashed at import time | Check CloudWatch Logs: `/aws/lambda/ebook-platform-dev-api` |
| API returns 401 on all requests | Cognito JWT expired | Re-authenticate; tokens expire after 1 hour |
| Step Functions execution fails at LoadTopicConfig | Topic not in DynamoDB | Verify `POST /admin/topics` succeeded first |
| Worker fails with `NoCredentialsError` | Lambda env vars not set | Check Lambda env vars in console (should have `DYNAMODB_TABLE_NAME` etc.) |
| OpenAI calls fail | Secret not set | `aws secretsmanager get-secret-value --secret-id ebook-platform/openai-key` |
| Amplify site shows old content | Build cache | Trigger a new deploy: `bash scripts/deploy_frontend.sh public` |
| `AccessDeniedException` on DynamoDB | IAM policy too tight | Check Lambda execution role in CloudWatch error |

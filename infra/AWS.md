# AWS Services Reference — Agentic Ebook Platform V3

This document covers every AWS service used, its purpose, cost model, and Terraform lifecycle instructions.

---

## Services Overview

### Cost model key

| Symbol | Meaning |
|---|---|
| **Pay-per-use** | You are only charged when the service actively processes something. Zero usage = zero cost. |
| **Always-on** | The resource runs continuously and accrues cost even when idle. |
| **One-time / negligible** | Minimal fixed cost or a one-time charge for provisioning. |

---

### 1. Amazon DynamoDB — Metadata Store

**Purpose:** Single-table store for all queryable metadata — topic config, run records, review states, trace events, feedback, notification logs, and global settings. S3 holds large artifacts; DynamoDB holds everything you need to query.

**Cost model: Pay-per-use**
- Billing mode: `PAY_PER_REQUEST` — you pay per read/write request, not for provisioned capacity.
- Storage is charged per GB/month (very cheap at ebook scale).
- No charge when the table is idle.
- Point-in-time recovery (PITR) adds a small storage fee.

**Dev tip:** A typical dev session (creating topics, triggering a few runs) costs cents.

---

### 2. Amazon S3 — Artifact Store

**Purpose:** Stores all large binary/text artifacts produced by the pipeline — raw research pages, extracted text, verified evidence packs, staged drafts, published HTML/JSON, Lunr.js search index, and table of contents.

**Cost model: Pay-per-use**
- Storage: charged per GB stored per month.
- Requests: charged per PUT/GET (fractions of a cent).
- No charge for an empty bucket.
- Lifecycle rules automatically move old `raw/` artifacts to Glacier (cheaper storage) after 90 days.

**Dev tip:** Delete test artifacts regularly using the notebook PURGE cell to keep storage costs near zero.

---

### 3. AWS Lambda — API Handlers + Pipeline Workers

**Purpose:** All application compute runs in Lambda. Two function groups:
- **API handler** (`ebook-platform-dev-api`) — serves all `/admin/*` and `/public/*` REST API calls.
- **Pipeline workers** (13 functions) — each Step Functions state invokes its own Lambda worker (topic loader, planner, research, draft, editorial review, publish, etc.).
- **Digest worker** — invoked weekly by EventBridge Scheduler to send the digest email.

**Cost model: Pay-per-use**
- Charged per invocation + per GB-second of memory × duration.
- AWS free tier includes 1 million invocations and 400,000 GB-seconds per month.
- Zero cost when no functions are running.

**Dev tip:** The pipeline workers have a 15-minute timeout and 512 MB memory — they only run during an active pipeline execution. The API handler is fast (30s timeout, 256 MB).

---

### 4. AWS Step Functions (Standard Workflow) — Pipeline Orchestration

**Purpose:** Durable, visual state machine that runs the 14-stage content pipeline (load config → plan → research → verify → draft → editorial → build → diff → notify → wait for approval → publish → rebuild index). Standard Workflows support the `waitForTaskToken` callback pattern needed for human-in-the-loop approval — execution pauses for up to 72 hours while waiting for admin decision.

**Cost model: Pay-per-use**
- Charged per state transition.
- One pipeline run ≈ 20–25 state transitions ≈ fractions of a cent.
- No cost when no executions are running.
- Standard (not Express) workflow required because Express Workflows do not support `waitForTaskToken` for async human approval.

---

### 5. Amazon API Gateway (HTTP API) — REST API Layer

**Purpose:** Single entry point for all HTTP traffic. Routes `/admin/*` requests through the Cognito JWT authorizer before forwarding to the API Lambda. Routes `/public/*` without authentication. Handles CORS.

**Cost model: Pay-per-use**
- Charged per API call + data transfer.
- AWS free tier includes 1 million API calls/month for 12 months.
- No idle cost.

---

### 6. Amazon Cognito — Admin Authentication

**Purpose:** Issues JWTs for admin users. The API Gateway JWT authorizer validates every `/admin/*` request against the Cognito user pool. Admin SPA uses the Cognito client to authenticate users and obtain tokens.

**Cost model: Pay-per-use**
- Free tier: 50,000 Monthly Active Users (MAUs).
- At single-admin scale, this is effectively free.

---

### 7. Amazon EventBridge Scheduler — Topic Scheduling

**Purpose:** Two uses:
1. **Per-topic schedules** (created dynamically by the API at runtime, not Terraform) — each active topic with a non-manual schedule gets its own EventBridge Scheduler entry that triggers the Step Functions pipeline on its configured cron/rate.
2. **Weekly digest schedule** (could be Terraform-managed) — triggers the digest Lambda once per week.

**Cost model: Pay-per-use**
- Charged per schedule invocation.
- One schedule firing per topic per week = negligible cost.
- No cost for schedules that haven't fired.

---

### 8. AWS Secrets Manager — OpenAI API Key

**Purpose:** Stores the OpenAI API key. Lambda workers fetch it at runtime using `GetSecretValue`. The key is never stored in environment variables or source code.

**Cost model: Always-on (very low)**
- Charged per secret per month (~$0.40/secret/month) + per API call.
- One secret = ~$0.40/month regardless of usage.
- This is the only service with a small fixed monthly cost.

---

### 9. Amazon SES (Simple Email Service) — Notifications

**Purpose:** Two uses:
1. Admin notification email when a draft is ready for review (sent by `approval_worker`).
2. Weekly digest email to the website owner (sent by `digest_worker`).

**Cost model: Pay-per-use**
- Charged per email sent (fractions of a cent per email).
- No idle cost.
- **Dev note:** SES starts in sandbox mode. In sandbox, you can only send to verified email addresses. To send to any address, request production access in the AWS console.

---

### 10. AWS Amplify Hosting — Frontend Sites

**Purpose:** Two Amplify apps:
- **Public site** (`ebook-platform-public-dev`) — Astro static site, reader-facing ebook.
- **Admin site** (`ebook-platform-admin-dev`) — React + Vite SPA for platform management.

**Cost model: Pay-per-use**
- Charged per build minute + per GB served + per GB stored.
- Amplify free tier: 1,000 build minutes/month, 15 GB serving/month, 5 GB storage.
- Static sites with low traffic are effectively free.
- **Note:** In MVP, Amplify apps are provisioned but deployed manually (no GitHub auto-deploy yet). Cost is near zero until you start deploying and serving traffic.

---

### 11. Amazon CloudWatch — Logging, Alarms, Dashboard

**Purpose:**
- Log groups for every Lambda function and Step Functions state machine.
- Alarms: Lambda error rate, SFN execution failures, API 5xx rate.
- Dashboard for operational visibility.
- SNS topic for alarm notifications (optional email subscription).

**Cost model: Pay-per-use**
- Log ingestion and storage charged per GB.
- Alarms: $0.10/alarm/month (5 alarms ≈ $0.50/month).
- Dashboard: $3/dashboard/month — only charged after the free tier (3 dashboards free).
- Dev log volumes are tiny; total CloudWatch cost is under $1/month.

---

### 12. AWS IAM — Identity and Access Management

**Purpose:** Least-privilege roles for every Lambda function, Step Functions, and EventBridge Scheduler. No role has broader permissions than required.

**Cost model: Free**
- IAM has no per-resource cost.

---

## Cost Summary

| Scenario | Estimated monthly cost |
|---|---|
| Idle dev environment (no runs) | ~$0.40 (Secrets Manager only) |
| Active dev (5–10 pipeline runs/month) | ~$2–5 |
| Production (daily runs, low reader traffic) | ~$10–20 |
| Production (weekly runs, moderate reader traffic) | ~$5–10 |

The only service with a guaranteed fixed cost is Secrets Manager (~$0.40/month per secret). Everything else scales to zero when unused.

---

## Terraform: Provisioning and Teardown

### Prerequisites

1. Install Terraform ≥ 1.7: `choco install terraform -y` (Windows) or `brew install terraform` (Mac)
2. AWS credentials with sufficient IAM permissions:
   - AdministratorAccess is easiest for initial provisioning; scope down after.
   - Export credentials to environment: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
3. Copy `infra/terraform/envs/dev/terraform.tfvars.example` → `infra/terraform/envs/dev/terraform.tfvars` and fill in your values.

---

### Provisioning — Dev Environment

```bash
# 1. Navigate to dev environment
cd infra/terraform/envs/dev

# 2. Copy and fill in your variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set aws_account_id, ses_sender_email, owner_email

# 3. Initialize providers and modules
terraform init

# 4. Preview what will be created (no changes applied)
terraform plan

# 5. Apply — creates all AWS resources
terraform apply

# 6. View outputs (API endpoint, Cognito IDs, etc.)
terraform output
```

**Expected resources created:** ~60–70 AWS resources (DynamoDB table + 5 GSIs, S3 bucket, 5 IAM roles + policies, 1 secret, Cognito user pool + client + group, 14 Lambda functions + log groups, API Gateway + authorizer + routes, Step Functions state machine, EventBridge schedule group, SES identity, CloudWatch alarms + dashboard + SNS topic, 2 Amplify apps + branches).

---

### Provisioning — Production Environment

```bash
# 1. Navigate to prod environment (created in a future milestone)
cd infra/terraform/envs/prod

# 2. Copy and fill in prod-specific variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: use prod AWS account or prod IAM role, real sender email, etc.

# 3. Switch to remote backend (S3 + DynamoDB lock) — edit main.tf to uncomment the S3 backend block
#    Create the S3 backend bucket manually first:
#    aws s3 mb s3://ebook-platform-tfstate-prod --region us-east-1

# 4. Initialize with remote backend
terraform init

# 5. Plan and apply
terraform plan
terraform apply
```

**Key differences from dev:**
- S3 backend for shared state (multiple developers, CI/CD pipeline)
- `force_destroy = false` on S3 bucket (protects published content)
- Secrets Manager recovery window: 30 days (not instant delete)
- Cognito token validity may be tightened
- SES out of sandbox (production access requested separately in AWS console)
- Terraform state stored remotely — never commit `terraform.tfstate` to git

---

### Updating Infrastructure

```bash
# Make changes to module .tf files, then:
cd infra/terraform/envs/dev   # or prod

terraform plan    # review what changes will be made
terraform apply   # apply the changes
```

Terraform is idempotent — running `apply` on an unchanged configuration makes no changes.

---

### Purging — Dev Environment (Complete Teardown)

Destroys **all** AWS resources created by Terraform in the dev environment. Safe to run after a development session to avoid idle costs.

```bash
cd infra/terraform/envs/dev

# Preview what will be destroyed
terraform plan -destroy

# Destroy everything
terraform destroy
```

> **Note:** The S3 bucket has `force_destroy = true` in dev, so `terraform destroy` will also delete all objects in the bucket. This is intentional for dev cleanup. In prod, `force_destroy = false` means you must empty the bucket manually before `terraform destroy` will succeed.

> **Note:** DynamoDB table and all its data are deleted. Run the notebook PURGE cell first if you want to inspect or export test data before destroying.

---

### Purging — Selective Resource Teardown

To destroy only a specific module (e.g., just the Lambda functions during a redeploy):

```bash
cd infra/terraform/envs/dev

# Destroy only the Lambda functions module
terraform destroy -target=module.lambda_functions

# Destroy only monitoring
terraform destroy -target=module.monitoring

# Destroy only Amplify apps
terraform destroy -target=module.amplify_public_site
terraform destroy -target=module.amplify_admin_site
```

Use `-target` carefully — it can leave Terraform state inconsistent if dependent resources are not also destroyed. Prefer full `terraform destroy` for dev cleanup.

---

### Purging — Production Environment

Production teardown is intentionally harder:

```bash
cd infra/terraform/envs/prod

# Step 1: Manually empty the S3 artifact bucket (force_destroy=false in prod)
aws s3 rm s3://ebook-platform-artifacts-prod --recursive

# Step 2: Destroy all Terraform-managed resources
terraform destroy
```

> **Warning:** Production destroy is irreversible. All published ebook content, run history, and reader feedback stored in DynamoDB and S3 will be permanently deleted. Always take a DynamoDB export and S3 backup before running `terraform destroy` in prod.

---

### Useful Terraform Commands

```bash
# Show current state (what Terraform thinks is deployed)
terraform state list

# Show details of a specific resource
terraform state show module.dynamodb.aws_dynamodb_table.main

# Refresh state from actual AWS resources (if something was changed outside Terraform)
terraform refresh

# Import an existing AWS resource into Terraform state
# (useful if you manually created something and want Terraform to manage it)
terraform import module.cognito.aws_cognito_user_pool.main <user-pool-id>

# Format all .tf files
terraform fmt -recursive .

# Validate configuration without AWS credentials
terraform validate
```

---

### Post-Apply Checklist (Dev)

After `terraform apply` completes:

- [ ] Note the outputs: `terraform output` — save `api_endpoint`, `cognito_user_pool_id`, `cognito_client_id`
- [ ] Update `.env.local` with the output values
- [ ] Create an admin user in Cognito:
  ```bash
  aws cognito-idp admin-create-user \
    --user-pool-id <user_pool_id> \
    --username admin@example.com \
    --temporary-password "TempPass123!" \
    --message-action SUPPRESS
  ```
- [ ] Add admin user to the `admins` group:
  ```bash
  aws cognito-idp admin-add-user-to-group \
    --user-pool-id <user_pool_id> \
    --username admin@example.com \
    --group-name admins
  ```
- [ ] Verify SES sender email in the AWS console (SES → Verified identities)
- [ ] Set the real OpenAI API key in Secrets Manager:
  ```bash
  aws secretsmanager put-secret-value \
    --secret-id ebook-platform/openai-key \
    --secret-string '{"api_key": "sk-..."}'
  ```
- [ ] Run `terraform output` and verify all expected values are populated (no empty strings)

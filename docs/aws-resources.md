# AWS Deployed Resources — Agentic Ebook Platform V3

**Environment:** dev  
**Account ID:** 135671745449  
**Region:** us-east-1  
**Last verified:** 2026-04-11

All resources below are active and deployed. This file is the single reference for every
AWS resource, ARN, ID, and URL in the dev environment.

---

## User-Facing URLs

| Interface | URL | Notes |
|---|---|---|
| **Admin Console** | https://dev.d200xw9mmlu4wj.amplifyapp.com | Login with Cognito credentials |
| **Public Ebook Site** | https://dev.djcvgu9ysuar.amplifyapp.com | No login required |
| **API Base URL** | https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com | Append route paths below |

### API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/admin/topics` | Bearer JWT | List all topics |
| POST | `/admin/topics` | Bearer JWT | Create a topic |
| GET | `/admin/topics/{id}` | Bearer JWT | Get topic detail |
| PUT | `/admin/topics/{id}` | Bearer JWT | Update a topic |
| DELETE | `/admin/topics/{id}` | Bearer JWT | Soft-delete a topic |
| PUT | `/admin/topics/reorder` | Bearer JWT | Reorder topics |
| POST | `/admin/topics/{id}/trigger` | Bearer JWT | Trigger AI pipeline |
| GET | `/admin/topics/{id}/runs` | Bearer JWT | List pipeline runs |
| GET | `/admin/topics/{id}/runs/{runId}` | Bearer JWT | Run detail + trace events |
| GET | `/admin/reviews` | Bearer JWT | All pending reviews |
| GET | `/admin/topics/{id}/review/{runId}` | Bearer JWT | Draft for review |
| POST | `/admin/topics/{id}/review/{runId}` | Bearer JWT | Approve or reject draft |
| GET | `/admin/feedback/summary` | Bearer JWT | Feedback across all topics |
| GET | `/admin/topics/{id}/feedback` | Bearer JWT | Feedback for one topic |
| POST | `/public/comments` | None | Submit reader comment |
| POST | `/public/highlights` | None | Submit text highlight |
| GET | `/public/releases/latest` | None | Recently published topics |

---

## AWS Amplify

### Admin Console

| Field | Value |
|---|---|
| App Name | `ebook-platform-admin-dev` |
| App ID | `d200xw9mmlu4wj` |
| Branch | `dev` |
| Live URL | https://dev.d200xw9mmlu4wj.amplifyapp.com |
| Default Domain | `d200xw9mmlu4wj.amplifyapp.com` |
| Console | https://us-east-1.console.aws.amazon.com/amplify/apps/d200xw9mmlu4wj |

### Public Ebook Site

| Field | Value |
|---|---|
| App Name | `ebook-platform-public-dev` |
| App ID | `djcvgu9ysuar` |
| Branch | `dev` |
| Live URL | https://dev.djcvgu9ysuar.amplifyapp.com |
| Default Domain | `djcvgu9ysuar.amplifyapp.com` |
| Console | https://us-east-1.console.aws.amazon.com/amplify/apps/djcvgu9ysuar |

---

## API Gateway

| Field | Value |
|---|---|
| API Name | `ebook-platform-dev-api` |
| API ID | `gcqq4kkov1` |
| Type | HTTP API |
| Endpoint | https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com |
| Stage | `$default` |
| Auth on `/admin/*` | Cognito JWT authorizer |
| Auth on `/public/*` | None |
| Console | https://us-east-1.console.aws.amazon.com/apigateway/main/apis/gcqq4kkov1 |

---

## Amazon Cognito

| Field | Value |
|---|---|
| User Pool Name | `ebook-platform-dev` |
| User Pool ID | `us-east-1_R4FK1QHyr` |
| App Client Name | `ebook-platform-admin-spa-dev` |
| App Client ID | `5g3o4juiad2ils16v48iuu119i` |
| Admin Group | `admins` |
| Console | https://us-east-1.console.aws.amazon.com/cognito/v2/idp/user-pools/us-east-1_R4FK1QHyr |

### Getting an Auth Token

```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=<email>,PASSWORD=<password> \
  --client-id 5g3o4juiad2ils16v48iuu119i \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

Use the output as `Authorization: Bearer <token>` on all `/admin/*` requests.
Tokens expire after **1 hour**.

---

## AWS Lambda Functions

All functions: runtime `python3.12`, handler `handler.lambda_handler`, region `us-east-1`.

### API Lambda

| Field | Value |
|---|---|
| Function Name | `ebook-platform-dev-api` |
| ARN | `arn:aws:lambda:us-east-1:135671745449:function:ebook-platform-dev-api` |
| Package Size | ~2.6 MB |
| Last Deployed | 2026-04-11 |
| IAM Role | `ebook-platform-dev-api-lambda` |
| CloudWatch Logs | `/aws/lambda/ebook-platform-dev-api` |
| Console | https://us-east-1.console.aws.amazon.com/lambda/home#/functions/ebook-platform-dev-api |

### Pipeline Worker Lambdas

| Function Name | Package Size | AI Model | Last Deployed |
|---|---|---|---|
| `ebook-platform-dev-topic-loader` | 2.6 MB | — | 2026-04-11 |
| `ebook-platform-dev-topic-context-builder` | 2.6 MB | — | 2026-04-11 |
| `ebook-platform-dev-planner-worker` | 5.6 MB | gpt-4o-mini | 2026-04-11 |
| `ebook-platform-dev-research-worker` | 5.6 MB | gpt-4o | 2026-04-11 |
| `ebook-platform-dev-verifier-worker` | 5.6 MB | gpt-4o-mini | 2026-04-11 |
| `ebook-platform-dev-artifact-persister` | 2.6 MB | — | 2026-04-11 |
| `ebook-platform-dev-draft-worker` | 5.6 MB | gpt-4o | 2026-04-11 |
| `ebook-platform-dev-editorial-worker` | 5.6 MB | gpt-4o | 2026-04-11 |
| `ebook-platform-dev-draft-builder-worker` | 2.6 MB | — | 2026-04-11 |
| `ebook-platform-dev-diff-worker` | 5.6 MB | gpt-4o-mini | 2026-04-11 |
| `ebook-platform-dev-approval-worker` | 2.6 MB | — | 2026-04-11 |
| `ebook-platform-dev-publish-worker` | 2.6 MB | — | 2026-04-11 |
| `ebook-platform-dev-search-index-worker` | 2.6 MB | — | 2026-04-11 |

> **Note:** Workers with 5.6 MB packages include the `openai` SDK and `openai_runtime` module.
> Workers with 2.6 MB packages are standalone (no AI calls).

### Digest Lambda

| Field | Value |
|---|---|
| Function Name | `ebook-platform-dev-digest` |
| ARN | `arn:aws:lambda:us-east-1:135671745449:function:ebook-platform-dev-digest` |
| Package Size | ~2.6 MB |
| Trigger | EventBridge Scheduler — every Monday 08:00 UTC |
| IAM Role | `ebook-platform-dev-digest-lambda` |
| CloudWatch Logs | `/aws/lambda/ebook-platform-dev-digest` |

### Viewing Logs for Any Lambda

```bash
# Tail live logs (replace function name as needed)
aws logs tail /aws/lambda/ebook-platform-dev-api \
  --follow --since 10m --region us-east-1

# Search logs for errors in the last hour
aws logs filter-log-events \
  --log-group-name /aws/lambda/ebook-platform-dev-planner-worker \
  --filter-pattern ERROR \
  --start-time $(date -d '1 hour ago' +%s000) \
  --region us-east-1
```

---

## AWS Step Functions

| Field | Value |
|---|---|
| State Machine Name | `ebook-platform-dev-topic-pipeline` |
| ARN | `arn:aws:states:us-east-1:135671745449:stateMachine:ebook-platform-dev-topic-pipeline` |
| Type | Standard Workflow |
| IAM Role | `ebook-platform-dev-sfn-execution` |
| Console | https://us-east-1.console.aws.amazon.com/states/home#/statemachines/view/arn:aws:states:us-east-1:135671745449:stateMachine:ebook-platform-dev-topic-pipeline |
| CloudWatch Logs | `/aws/states/ebook-platform-dev-topic-pipeline` |

### Pipeline Stage Sequence

```
LoadTopicConfig → AssembleTopicContext → PlanTopic → ResearchTopic → VerifyEvidence
  → PersistEvidenceArtifacts → DraftChapter → EditorialReview → BuildDraftArtifact
  → GenerateDiffReleaseNotes → NotifyAdminForReview → WaitForApproval
  → (approve) → PublishTopic → RebuildIndexes
  → (reject)  → StoreRejection → END
```

### Useful Commands

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:135671745449:stateMachine:ebook-platform-dev-topic-pipeline \
  --region us-east-1 \
  --query 'executions[0:10].{status:status,name:name,start:startDate}' \
  --output table

# Get execution detail
aws stepfunctions describe-execution \
  --execution-arn <execution_arn> \
  --region us-east-1 \
  --query '{status:status,error:error,cause:cause}'

# Get execution history (all state transitions)
aws stepfunctions get-execution-history \
  --execution-arn <execution_arn> \
  --region us-east-1
```

---

## Amazon DynamoDB

| Field | Value |
|---|---|
| Table Name | `ebook-platform-dev` |
| ARN | `arn:aws:dynamodb:us-east-1:135671745449:table/ebook-platform-dev` |
| Status | ACTIVE |
| Item Count | 15 (as of 2026-04-11) |
| Billing Mode | Pay-per-request |
| Encryption | AWS-managed (SSE enabled) |
| Console | https://us-east-1.console.aws.amazon.com/dynamodbv2/home#table?name=ebook-platform-dev |

### Global Secondary Indexes

| Index Name | Partition Key | Sort Key | Purpose |
|---|---|---|---|
| `GSI1-EntityType-OrderKey` | `ENTITY_TYPE` | `ORDER_KEY` | List topics sorted by order |
| `GSI2-RunStatus-UpdatedAt` | `RUN_STATUS` | `UPDATED_AT` | Monitor runs by status |
| `GSI3-ReviewStatus-UpdatedAt` | `REVIEW_STATUS` | `UPDATED_AT` | Pending review queue |
| `GSI4-ScheduleBucket-NextRunAt` | `SCHEDULE_BUCKET` | `NEXT_RUN_AT` | Schedule views |
| `GSI5-FeedbackTopic-CreatedAt` | `FEEDBACK_TOPIC` | `CREATED_AT` | Feedback by topic |

### Key Data Patterns

```bash
# List all topics
aws dynamodb query \
  --table-name ebook-platform-dev \
  --index-name GSI1-EntityType-OrderKey \
  --key-condition-expression "ENTITY_TYPE = :t" \
  --expression-attribute-values '{":t":{"S":"TOPIC"}}' \
  --region us-east-1

# Get all records for a topic
aws dynamodb query \
  --table-name ebook-platform-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"TOPIC#<topic_id>"}}' \
  --region us-east-1

# Get all trace events for a pipeline run
aws dynamodb query \
  --table-name ebook-platform-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"RUN#<run_id>"}}' \
  --region us-east-1
```

---

## Amazon S3

| Field | Value |
|---|---|
| Bucket Name | `ebook-platform-artifacts-dev` |
| ARN | `arn:aws:s3:::ebook-platform-artifacts-dev` |
| Region | `us-east-1` |
| Versioning | Enabled |
| Access | Private (no public access) |
| Console | https://s3.console.aws.amazon.com/s3/buckets/ebook-platform-artifacts-dev |

### Bucket Layout

```
ebook-platform-artifacts-dev/
├── deployments/                    ← Lambda deployment ZIPs (managed by deploy scripts)
│   ├── api.zip
│   ├── topic_loader.zip
│   └── ...
│
├── topics/<topic_id>/
│   └── runs/<run_id>/
│       ├── raw/                    ← Raw fetched web content
│       ├── extracted/              ← Normalized markdown text
│       ├── verified/               ← Validated evidence pack
│       ├── draft/                  ← Initial AI draft
│       ├── review/                 ← Staged draft for admin review
│       └── diff/                   ← Diff vs prior published version
│
├── published/
│   └── topics/<topic_id>/
│       ├── v001/                   ← First published version
│       ├── v002/                   ← Second published version (after re-run + approve)
│       └── ...
│
└── site/
    └── current/
        ├── search/index.json       ← Lunr.js search index (rebuilt on every publish)
        └── toc.json                ← Table of contents (rebuilt on every publish)
```

### Useful Commands

```bash
# List all artifacts for a topic
aws s3 ls s3://ebook-platform-artifacts-dev/topics/<topic_id>/ --recursive

# List published versions for a topic
aws s3 ls s3://ebook-platform-artifacts-dev/published/topics/<topic_id>/

# Download the current search index
aws s3 cp s3://ebook-platform-artifacts-dev/site/current/search/index.json ./index.json

# View a staged draft for review
aws s3 cp s3://ebook-platform-artifacts-dev/topics/<topic_id>/runs/<run_id>/review/ . --recursive
```

---

## Amazon EventBridge Scheduler

### Schedule Group (for per-topic schedules)

| Field | Value |
|---|---|
| Group Name | `ebook-platform-dev-topics` |
| Purpose | Holds per-topic recurring schedules (created/deleted at runtime by the API) |
| Console | https://us-east-1.console.aws.amazon.com/scheduler/home#/schedule-groups |

### Weekly Digest Schedule

| Field | Value |
|---|---|
| Schedule Name | `ebook-platform-dev-weekly-digest` |
| Group | `default` |
| Expression | `cron(0 8 ? * MON *)` — every Monday at 08:00 UTC |
| Target | `ebook-platform-dev-digest` Lambda |
| State | ENABLED |
| Console | https://us-east-1.console.aws.amazon.com/scheduler/home#/schedules/default/ebook-platform-dev-weekly-digest |

---

## AWS Secrets Manager

| Field | Value |
|---|---|
| Secret Name | `ebook-platform/openai-key` |
| ARN | `arn:aws:secretsmanager:us-east-1:135671745449:secret:ebook-platform/openai-key-sbBbMy` |
| Secret Key | `api_key` |
| Console | https://us-east-1.console.aws.amazon.com/secretsmanager/secret?name=ebook-platform/openai-key |

The secret is read at Lambda invocation time by AI worker functions. It is never stored
in environment variables or source code.

Update the key:
```bash
aws secretsmanager put-secret-value \
  --secret-id ebook-platform/openai-key \
  --secret-string '{"api_key": "sk-...new-key..."}' \
  --region us-east-1
```

---

## Amazon SES (Email)

| Field | Value |
|---|---|
| Sender Email | `vaibhavmaurya1986@gmail.com` |
| Verification Status | Pending (check inbox for AWS verification email) |
| Mode | SES Sandbox — both sender and recipient must be verified |
| Console | https://us-east-1.console.aws.amazon.com/ses/home#/verified-identities |

> **Action required:** If the sender email shows as unverified, click the verification
> link AWS sent to `vaibhavmaurya1986@gmail.com`. Pipeline approval notifications and
> weekly digests will fail until this is done.

Re-send the verification email:
```bash
aws sesv2 create-email-identity \
  --email-identity vaibhavmaurya1986@gmail.com \
  --region us-east-1
```

---

## IAM Roles

| Role Name | Used By | Key Permissions |
|---|---|---|
| `ebook-platform-dev-api-lambda` | API Lambda | DynamoDB CRUD+Scan, SFN StartExecution, EventBridge Scheduler CRUD |
| `ebook-platform-dev-worker-lambda` | All 13 pipeline workers | DynamoDB CRUD, S3 full access, Secrets Manager read, SFN SendTask* |
| `ebook-platform-dev-digest-lambda` | Digest Lambda | DynamoDB Query+Scan, SES send |
| `ebook-platform-dev-sfn-execution` | Step Functions | Lambda:InvokeFunction on all `ebook-platform-dev-*` functions |
| `ebook-platform-dev-scheduler` | EventBridge Scheduler (per-topic) | SFN StartExecution |
| `ebook-platform-dev-digest-scheduler` | EventBridge Scheduler (digest) | Lambda:InvokeFunction on digest Lambda |

---

## CloudWatch

### Dashboard

| Field | Value |
|---|---|
| Dashboard Name | `ebook-platform-dev` |
| Console | https://us-east-1.console.aws.amazon.com/cloudwatch/home#dashboards/dashboard/ebook-platform-dev |

### Alarms (all currently OK)

| Alarm | Monitors | Threshold |
|---|---|---|
| `ebook-platform-dev-api-5xx` | API Gateway 5xx errors | > 5 in 5 minutes |
| `ebook-platform-dev-sfn-failures` | Step Functions execution failures | > 1 in 5 minutes |
| `ebook-platform-dev-*-errors` | Each Lambda error count (13 alarms) | > 0 in 5 minutes |

All alarms publish to:
- **SNS Topic:** `ebook-platform-dev-alarms`
- **ARN:** `arn:aws:sns:us-east-1:135671745449:ebook-platform-dev-alarms`

### Log Groups (all with 14-day retention)

| Log Group | Lambda |
|---|---|
| `/aws/lambda/ebook-platform-dev-api` | API handler |
| `/aws/lambda/ebook-platform-dev-topic-loader` | Topic loader worker |
| `/aws/lambda/ebook-platform-dev-topic-context-builder` | Context builder worker |
| `/aws/lambda/ebook-platform-dev-planner-worker` | Planner AI worker |
| `/aws/lambda/ebook-platform-dev-research-worker` | Research AI worker |
| `/aws/lambda/ebook-platform-dev-verifier-worker` | Verifier AI worker |
| `/aws/lambda/ebook-platform-dev-artifact-persister` | Artifact persister |
| `/aws/lambda/ebook-platform-dev-draft-worker` | Writer AI worker |
| `/aws/lambda/ebook-platform-dev-editorial-worker` | Editor AI worker |
| `/aws/lambda/ebook-platform-dev-draft-builder-worker` | Draft builder |
| `/aws/lambda/ebook-platform-dev-diff-worker` | Diff AI worker |
| `/aws/lambda/ebook-platform-dev-approval-worker` | Approval / notify |
| `/aws/lambda/ebook-platform-dev-publish-worker` | Publish worker |
| `/aws/lambda/ebook-platform-dev-search-index-worker` | Index rebuilder |
| `/aws/lambda/ebook-platform-dev-digest` | Weekly digest |
| `/aws/states/ebook-platform-dev-topic-pipeline` | Step Functions execution logs |

---

## Quick Reference — AWS Console Links

| Resource | Console Link |
|---|---|
| Admin Amplify App | https://us-east-1.console.aws.amazon.com/amplify/apps/d200xw9mmlu4wj |
| Public Amplify App | https://us-east-1.console.aws.amazon.com/amplify/apps/djcvgu9ysuar |
| API Gateway | https://us-east-1.console.aws.amazon.com/apigateway/main/apis/gcqq4kkov1 |
| Cognito User Pool | https://us-east-1.console.aws.amazon.com/cognito/v2/idp/user-pools/us-east-1_R4FK1QHyr |
| DynamoDB Table | https://us-east-1.console.aws.amazon.com/dynamodbv2/home#table?name=ebook-platform-dev |
| S3 Artifacts Bucket | https://s3.console.aws.amazon.com/s3/buckets/ebook-platform-artifacts-dev |
| Step Functions | https://us-east-1.console.aws.amazon.com/states/home#/statemachines |
| Lambda Functions | https://us-east-1.console.aws.amazon.com/lambda/home#/functions?f0=true&n0=false&op=and&v0=ebook-platform-dev |
| EventBridge Schedules | https://us-east-1.console.aws.amazon.com/scheduler/home#/schedule-groups |
| Secrets Manager | https://us-east-1.console.aws.amazon.com/secretsmanager/secret?name=ebook-platform/openai-key |
| SES Identities | https://us-east-1.console.aws.amazon.com/ses/home#/verified-identities |
| CloudWatch Dashboard | https://us-east-1.console.aws.amazon.com/cloudwatch/home#dashboards/dashboard/ebook-platform-dev |
| CloudWatch Alarms | https://us-east-1.console.aws.amazon.com/cloudwatch/home#alarmsV2 |
| CloudWatch Logs | https://us-east-1.console.aws.amazon.com/cloudwatch/home#logsV2:log-groups |
| IAM Roles | https://us-east-1.console.aws.amazon.com/iam/home#/roles?filter=ebook-platform-dev |

# Action Items — Agentic Ebook Platform V3

> **How to use this file:**
> Open this file at the start of every coding session. The **RESUME HERE** section tells you exactly where to pick up. Update it at the end of every session before committing.

---

## ▶ RESUME HERE

**Session ended:** 2026-04-10
**Last completed:** M1-S3 through M1-S14 — all 13 Terraform modules fully implemented. `terraform init` and `terraform validate` pass with zero errors. Ready for `terraform apply`.
**Next action:** Start **M1-S15/S16** — fill in `terraform.tfvars` with real AWS account values, run `terraform plan` (verify resource count), then `terraform apply` against the dev AWS account.

### Immediate next steps (in order):

1. [x] **M1-S1:** Create `infra/terraform/envs/dev/main.tf` — provider config, backend, module calls (scaffold, modules can be empty initially)
2. [x] **M1-S2:** Create `infra/terraform/envs/dev/variables.tf` + `terraform.tfvars.example` + `outputs.tf` — all 13 module interfaces defined. Skeleton `main.tf`, `variables.tf`, `outputs.tf` written for every module so `terraform init/plan` can run.
3. [x] **M1-S3:** Build `infra/terraform/modules/dynamodb/` — single table, 5 GSIs, PITR, TTL
4. [x] **M1-S4:** Build `infra/terraform/modules/s3_artifacts/` — artifact bucket + lifecycle rules
5. [x] **M1-S5:** Build `infra/terraform/modules/iam/` — per-Lambda roles, SFN execution role, EventBridge Scheduler role
6. [x] **M1-S6:** Build `infra/terraform/modules/secrets_manager/` — OpenAI key placeholder secret
7. [x] **M1-S7:** Build `infra/terraform/modules/cognito/` — user pool, app client, admin group
8. [x] **M1-S8:** Build `infra/terraform/modules/lambda_functions/` — skeleton handler zip, 14 functions, log groups
9. [x] **M1-S9:** Build `infra/terraform/modules/api_gateway/` — HTTP API, JWT authorizer, CORS, routes
10. [x] **M1-S10:** Build `infra/terraform/modules/step_functions/` — full skeleton ASL, callback token pattern, CW logging
11. [x] **M1-S11:** Build `infra/terraform/modules/eventbridge_scheduler/` — schedule group
12. [x] **M1-S12:** Build `infra/terraform/modules/ses/` — sender identity (SESv2)
13. [x] **M1-S13:** Build `infra/terraform/modules/monitoring/` — CW alarms, SNS, dashboard
14. [x] **M1-S14:** Build `infra/terraform/modules/amplify_public_site/` + `amplify_admin_site/`
15. [ ] **M1-S15:** Fill in `terraform.tfvars` with real AWS values, run `terraform plan` — verify zero errors
16. [ ] **M1-S16:** Run `terraform apply` against dev AWS account — verify all resources exist

---

## Milestone Status

| # | Milestone | Status | Completed |
|---|---|---|---|
| 1 | Terraform Infrastructure Foundation | 🔄 In Progress | — |
| 2 | Topic CRUD API + Admin UI | ⏳ Pending | — |
| 3 | Scheduling + Manual Trigger | ⏳ Pending | — |
| 4 | Multi-Agent Pipeline | ⏳ Pending | — |
| 5 | Admin Review + Approval | ⏳ Pending | — |
| 6 | Incremental Publishing | ⏳ Pending | — |
| 7 | Public Website | ⏳ Pending | — |
| 8 | Run History + Feedback UI | ⏳ Pending | — |
| 9 | Weekly Digest | ⏳ Pending | — |
| 10 | Jupyter Notebook Test Harness | ⏳ Pending | — |

---

## Milestone 1 — Terraform Infrastructure Foundation

### Goal
`terraform apply` in `infra/terraform/envs/dev/` produces a fully deployed empty platform. All resources visible in AWS console. No application logic yet.

### Module Checklist

#### `dynamodb`
- [ ] Single table `ebook_platform`
- [ ] Billing mode: `PAY_PER_REQUEST`
- [ ] Hash key: `PK` (String), Range key: `SK` (String)
- [ ] GSI1: PK=`ENTITY_TYPE`, SK=`ORDER_KEY`
- [ ] GSI2: PK=`RUN_STATUS`, SK=`UPDATED_AT`
- [ ] GSI3: PK=`REVIEW_STATUS`, SK=`UPDATED_AT`
- [ ] GSI4: PK=`SCHEDULE_BUCKET`, SK=`NEXT_RUN_AT`
- [ ] GSI5: PK=`FEEDBACK_TOPIC`, SK=`CREATED_AT`
- [ ] Point-in-time recovery enabled
- [ ] TTL attribute: `expires_at`
- [ ] Server-side encryption enabled

#### `s3_artifacts`
- [ ] Artifact bucket: `ebook-platform-artifacts-<env>`
- [ ] Block all public access
- [ ] SSE-S3 encryption
- [ ] Versioning enabled
- [ ] Lifecycle rule: delete incomplete multipart uploads after 7 days
- [ ] Lifecycle rule: archive `topics/*/runs/*/raw/` to Glacier after 90 days
- [ ] Output: bucket name and ARN

#### `iam`
- [ ] Lambda execution base role (CloudWatch Logs, X-Ray)
- [ ] Lambda-DynamoDB role (read/write on `ebook_platform` table)
- [ ] Lambda-S3 role (read/write on artifact bucket)
- [ ] Lambda-SFN role (StartExecution, SendTaskSuccess, SendTaskFailure)
- [ ] Lambda-SecretsManager role (GetSecretValue for OpenAI key only)
- [ ] Lambda-SES role (SendEmail for digest Lambda only)
- [ ] Lambda-EventBridgeScheduler role (CreateSchedule, DeleteSchedule, UpdateSchedule)
- [ ] Step Functions execution role (InvokeFunction on all pipeline Lambdas)
- [ ] EventBridge Scheduler role (StartExecution on SFN state machine)
- [ ] Outputs: all role ARNs

#### `secrets_manager`
- [ ] Secret: `ebook-platform/openai-key` with placeholder value `{"api_key": "REPLACE_ME"}`
- [ ] KMS encryption (AWS managed key)
- [ ] Output: secret ARN and name

#### `cognito`
- [ ] User pool: `ebook-platform-admins-<env>`
- [ ] Password policy: min 8 chars, requires uppercase + number
- [ ] Email verification enabled
- [ ] App client: no secret (SPA-compatible), USER_PASSWORD_AUTH enabled
- [ ] Admin group: `ebook-admins`
- [ ] Outputs: user pool ID, app client ID, user pool ARN

#### `api_gateway`
- [ ] HTTP API: `ebook-platform-api-<env>`
- [ ] JWT authorizer linked to Cognito user pool
- [ ] CORS: allow all origins in dev, restrict in prod
- [ ] Default stage: `$default` with auto-deploy
- [ ] Route pattern: `/admin/*` → requires JWT auth; `/public/*` → no auth
- [ ] CloudWatch access logging enabled
- [ ] Outputs: API endpoint URL, API ID

#### `lambda_functions`
- [ ] One function per worker + API handler (14 functions total)
- [ ] Runtime: `python3.12`
- [ ] Skeleton handler zip (empty `lambda_function.py` with `def handler(event, context): return {}`)
- [ ] Memory: 512 MB default (adjust per function later)
- [ ] Timeout: 15 min for workers, 30 sec for API handlers
- [ ] Environment variables: `DYNAMODB_TABLE_NAME`, `S3_ARTIFACT_BUCKET`, `OPENAI_SECRET_NAME`, `AWS_REGION` (via data source)
- [ ] CloudWatch log group per function: `/aws/lambda/<name>`, retention 30 days
- [ ] X-Ray tracing enabled
- [ ] IAM role attached per function (from `iam` module)

Lambda function names:
```
ebook-api-handler-<env>
ebook-topic-loader-<env>
ebook-topic-context-builder-<env>
ebook-planner-worker-<env>
ebook-research-worker-<env>
ebook-verifier-worker-<env>
ebook-artifact-persister-<env>
ebook-draft-worker-<env>
ebook-editorial-worker-<env>
ebook-draft-builder-worker-<env>
ebook-diff-worker-<env>
ebook-approval-worker-<env>
ebook-publish-worker-<env>
ebook-search-index-worker-<env>
ebook-digest-worker-<env>
```

#### `step_functions`
- [ ] Standard workflow state machine: `ebook-topic-pipeline-<env>`
- [ ] Skeleton ASL with all 14 states (each state invokes its Lambda via ARN)
- [ ] States: LoadTopicConfig → AssembleTopicContext → PlanTopic → ResearchTopic → VerifyEvidence → PersistEvidenceArtifacts → DraftChapter → EditorialReview → BuildDraftArtifact → GenerateDiffReleaseNotes → NotifyAdminForReview → WaitForApproval → choice(Approved/Rejected) → PublishTopic → RebuildIndexes → NotifyOwner
- [ ] WaitForApproval uses `.waitForTaskToken` integration
- [ ] IAM role: SFN execution role from `iam` module
- [ ] CloudWatch logging: ALL level to `/aws/states/ebook-topic-pipeline-<env>`
- [ ] X-Ray tracing enabled
- [ ] Output: state machine ARN

#### `eventbridge_scheduler`
- [ ] Schedule group: `ebook-platform-<env>`
- [ ] IAM role: EventBridge → Start SFN execution (from `iam` module)
- [ ] No default schedules (per-topic schedules created dynamically at runtime)
- [ ] Output: schedule group name, scheduler IAM role ARN

#### `ses`
- [ ] Email identity for `SES_SENDER_EMAIL` variable
- [ ] IAM policy: allow SendEmail for digest Lambda role only
- [ ] Note: SES sandbox in dev — recipient addresses must be verified manually

#### `monitoring`
- [ ] CloudWatch alarm: Lambda error rate > 5 errors/5min (all worker functions)
- [ ] CloudWatch alarm: Step Functions execution failure > 1 in 5min
- [ ] CloudWatch alarm: API Gateway 5xx > 3% of requests in 5min
- [ ] CloudWatch dashboard: `ebook-platform-<env>` with Lambda error/duration, SFN executions, DynamoDB consumed capacity
- [ ] SNS topic for alarms (email subscription variable)

#### `amplify_public_site`
- [ ] Amplify app: `ebook-public-<env>`
- [ ] Branch: `main` with manual deploy (no GitHub connection yet — added in CI/CD phase)
- [ ] Environment variable: `PUBLIC_API_URL` pointing to API Gateway endpoint
- [ ] Output: app ID, default domain

#### `amplify_admin_site`
- [ ] Amplify app: `ebook-admin-<env>`
- [ ] Branch: `main` with manual deploy
- [ ] Environment variables: `VITE_API_URL`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`
- [ ] Output: app ID, default domain

### Acceptance Criteria
- [ ] `terraform plan` shows no errors and matches expected resource count
- [ ] `terraform apply` completes without errors
- [ ] DynamoDB table `ebook_platform` visible in AWS console with 5 GSIs
- [ ] S3 bucket created with correct lifecycle rules
- [ ] All 15 Lambda functions visible (each with correct role attached)
- [ ] Step Functions state machine visible with correct ASL
- [ ] Cognito user pool created — manually create admin user to verify
- [ ] API Gateway HTTP API accessible at its endpoint URL
- [ ] Amplify apps visible in console

---

## Milestone 2 — Topic CRUD API + Admin UI

### Prerequisite: Milestone 1 complete

### Backend tasks
- [ ] `services/api/topics.py` — Lambda handler for topic CRUD
- [ ] `services/api/local_dev_server.py` — FastAPI local server wrapping Lambda handlers
- [ ] `packages/shared-types/models.py` — Pydantic models: `Topic`, `TopicRun`, `Draft`, `Review`, `TraceEvent`
- [ ] `services/api/requirements.txt` — pydantic, boto3, aws-lambda-powertools
- [ ] Unit tests: `services/api/tests/test_topics.py`
- [ ] Trace event writer utility: `packages/shared-types/tracer.py`

### API endpoints to implement
- [ ] `GET /admin/topics` — list all active topics sorted by order
- [ ] `POST /admin/topics` — create topic, write META + SCHEDULE items, write EventBridge schedule if not manual
- [ ] `GET /admin/topics/{topicId}` — get topic with last run summary
- [ ] `PUT /admin/topics/{topicId}` — update topic, update EventBridge schedule if changed
- [ ] `DELETE /admin/topics/{topicId}` — soft delete (set `active=false`)
- [ ] `PUT /admin/topics/reorder` — update `order` field on affected topics

### Admin UI tasks
- [ ] Scaffold React + Vite app in `apps/admin-site/`
- [ ] Cognito auth integration (Amazon Cognito Identity SDK)
- [ ] Topic list page with status badges and order display
- [ ] Topic create/edit form
- [ ] Topic reorder (drag-and-drop)

---

## Milestone 3 — Scheduling and Manual Trigger

### Backend tasks
- [ ] `POST /admin/topics/{topicId}/trigger` handler
- [ ] `services/workers/topic_loader.py` — LoadTopicConfig worker skeleton
- [ ] EventBridge Scheduler API calls in topic create/update handler
- [ ] Dispatcher Lambda for scheduled triggers

---

## Milestone 4 — Multi-Agent Pipeline

### Backend tasks
- [ ] `services/openai-runtime/adapter.py` — OpenAI Responses API wrapper
- [ ] `services/openai-runtime/agents/planner.py`
- [ ] `services/openai-runtime/agents/research.py`
- [ ] `services/openai-runtime/agents/verifier.py`
- [ ] `services/openai-runtime/agents/writer.py`
- [ ] `services/openai-runtime/agents/editor.py`
- [ ] `services/openai-runtime/agents/diff.py`
- [ ] `services/openai-runtime/tools/` — search_web, fetch_url, extract_content, score_source
- [ ] All 11 worker Lambda handlers
- [ ] Full Step Functions ASL (replace skeleton)

---

## Milestone 5 — Admin Review and Approval

### Backend tasks
- [ ] `GET /admin/topics/{topicId}/review/{runId}`
- [ ] `POST /admin/topics/{topicId}/review/{runId}` — calls SFN SendTaskSuccess/SendTaskFailure

### Admin UI tasks
- [ ] Review queue page
- [ ] Draft review page: content viewer, diff view, source summary, approve/reject form

---

## Milestone 6 — Incremental Publishing

### Backend tasks
- [ ] `services/workers/publish_worker.py`
- [ ] `services/workers/search_index_worker.py`
- [ ] `services/content-build/lunr_index_builder.py`
- [ ] `services/content-build/toc_builder.py`

---

## Milestone 7 — Public Website

### Frontend tasks
- [ ] Scaffold Astro project in `apps/public-site/`
- [ ] Home page (TOC from `toc.json`)
- [ ] Per-topic chapter pages
- [ ] Lunr.js search integration
- [ ] Text highlight + comment widget
- [ ] Release notes page

### Backend tasks
- [ ] `services/api/public.py` — POST /public/comments, POST /public/highlights, GET /public/releases/latest

---

## Milestone 8 — Run History and Feedback UI

### Backend tasks
- [ ] `GET /admin/topics/{topicId}/runs`
- [ ] `GET /admin/topics/{topicId}/runs/{runId}`
- [ ] `GET /admin/feedback/summary`

### Admin UI tasks
- [ ] Run history page with cost totals
- [ ] Run detail page with trace event timeline
- [ ] Feedback list page

---

## Milestone 9 — Weekly Digest

### Backend tasks
- [ ] `services/workers/digest_worker.py`
- [ ] EventBridge weekly schedule for digest worker (Terraform-managed, not per-topic)

---

## Milestone 10 — Jupyter Notebook Test Harness

### Tasks
- [ ] Complete all cell group implementations in `notebooks/ebook_platform_test_harness.ipynb`
- [ ] Run full UC-01→UC-15 flow against dev AWS account
- [ ] Run PURGE cell and verify clean state
- [ ] Fix any assertion failures

---

## Technical Decisions Log

| Date | Decision | Reason |
|---|---|---|
| 2026-04-10 | Python 3.12 for all backend | OpenAI + boto3 first-class Python support |
| 2026-04-10 | TypeScript for all frontend | React admin SPA + Astro public site |
| 2026-04-10 | DynamoDB single-table design | Query efficiency, no large-item anti-patterns |
| 2026-04-10 | S3 + DynamoDB split | Large artifacts in S3, queryable metadata in DDB |
| 2026-04-10 | Lunr.js client-side search (MVP) | Zero infrastructure overhead |
| 2026-04-10 | Step Functions Standard (not Express) | Supports `.waitForTaskToken` for human approval |
| 2026-04-10 | EventBridge Scheduler per-topic (runtime) | Frequent create/delete; not suitable for Terraform management |
| 2026-04-10 | `openai_runtime` adapter isolation | Provider swap requires changing only one module |
| 2026-04-10 | gpt-4o for Research/Writer/Editor | Quality-critical, long-context tasks |
| 2026-04-10 | gpt-4o-mini for Planner/Verifier/Diff | Structured outputs, lower cost |
| 2026-04-10 | FastAPI + uvicorn for local dev server | Same Lambda handler code runs locally and in AWS |
| 2026-04-10 | No VPC in MVP | Reduces Lambda cold-start complexity; add in prod if required by org policy |

---

## Known Issues / Blockers

_None currently._

---

## Session Log

| Date | What was done |
|---|---|
| 2026-04-10 | Project initialization: plan.md, DevelopmentPlan.md, CLAUDE.md, action-item.md, MCP config, .gitignore, .env.local.example, notebook skeleton, full project scaffolding (35 files). Pushed to GitHub. |
| 2026-04-10 | M1-S1 + M1-S2: dev env main.tf (13 module calls, locals for circular-dep-free ARN construction), variables.tf, outputs.tf, terraform.tfvars.example. Skeleton main.tf/variables.tf/outputs.tf for all 13 modules with full interface contracts. |
| 2026-04-10 | M1-S3→S14: All 13 Terraform modules fully implemented (dynamodb, s3_artifacts, iam, secrets_manager, cognito, lambda_functions, api_gateway, step_functions, eventbridge_scheduler, ses, monitoring, amplify_public_site, amplify_admin_site). `terraform init` + `terraform validate` pass cleanly. Next: fill terraform.tfvars and run apply. |

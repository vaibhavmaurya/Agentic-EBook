# Phase 1 MVP Plan — Agentic Ebook Platform V3

> **Living document.** Update this file whenever scope, architecture, or sequencing decisions change.
> Last updated: 2026-04-12

---

## Context

The Agentic Ebook Platform V3 is a dynamic, per-topic publishing system that uses multi-agent AI workflows to research, draft, review, and publish web-based ebook content. Each "topic" is an independent lifecycle unit with its own schedule, agent pipeline, admin review gate, and published state.

**Goal of Phase 1 MVP:** deliver the complete end-to-end loop —
`topic creation → scheduled/manual agent run → admin review → incremental publish → public reading → feedback capture`

**Source specification documents:**
- `agentic-ebook-v3-use-case-specification.md` — use cases UC-01 through UC-15, FRs, BRs, acceptance criteria
- `agentic-ebook-v3-solution-architecture.md` — AWS service mapping, agent design, data model, API design

**Phase 2 deferred items:** semantic search (OpenSearch), WebSocket live status, Feedback Learning Agent, rich evidence inspection UI, multi-admin tiers, A/B model evaluation.

---

## Hard Constraints

1. **Local testability** — the entire application must be runnable locally against real AWS resources using AWS Access Key + Secret Key credentials. No mocking of AWS services in development; all code paths hit actual DynamoDB, S3, Step Functions, etc. in a dev AWS account.
2. **Jupyter notebook test harness** — a companion notebook must exercise every API in use-case order (UC-01 through UC-15), and include complete purge/teardown operations for post-testing cleanup.
3. **OpenAI only** — use OpenAI Responses API and OpenAI models. No Amazon Bedrock.
4. **Human approval gate** — no AI-generated content may be published without explicit admin approval.
5. **Terraform-first infra** — all AWS primitives provisioned by Terraform; per-topic schedules created dynamically at runtime.

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Public site | Astro (static shell) on AWS Amplify Hosting | Deployed once; content fetched from public API at runtime — no rebuild on publish |
| Admin UI | React + Vite SPA on AWS Amplify Hosting | Simple management console |
| Authentication | Amazon Cognito user pool | Admin JWT issuance, API Gateway JWT authorizer |
| API layer | API Gateway HTTP API + AWS Lambda (Python) | Serverless, lightweight routing |
| Orchestration | AWS Step Functions Standard workflows | Durable, callback-based human-in-the-loop |
| Scheduling | Amazon EventBridge Scheduler | One schedule per active topic, created at runtime |
| AI runtime | OpenAI Responses API via `openai_runtime` adapter | All OpenAI SDK calls isolated in one module |
| Search (MVP) | Lunr.js client-side over generated JSON index | Zero infrastructure, good for ebook scale |
| Artifact store | Amazon S3 | Raw research, drafts, published HTML/JSON/Markdown |
| Metadata store | Amazon DynamoDB single-table | Config, runs, reviews, traces, feedback |
| Secrets | AWS Secrets Manager | OpenAI key and other secrets |
| Notifications | Amazon SES | Weekly digest email to website owner |
| IaC | Terraform | All AWS infrastructure |
| Backend language | Python 3.12 | Lambda handlers, workers, openai_runtime adapter |
| Frontend language | TypeScript | React admin SPA, Astro public site |
| Agent model (heavy) | `gpt-4o` | Research, Writer, Editorial agents |
| Agent model (light) | `gpt-4o-mini` | Planner, Verifier, Diff agents |

---

## Repository Structure

```
ebook-platform/               ← project root (this folder)
  apps/
    public-site/              ← Astro static site (reader experience)
    admin-site/               ← React + Vite SPA (admin console)
  services/
    api/                      ← Lambda handlers: admin + public REST APIs
    workers/                  ← Step Functions Lambda workers (one per pipeline stage)
    openai-runtime/           ← Dedicated OpenAI SDK adapter (only layer touching OpenAI)
    content-build/            ← Search index builder, TOC generator, site artifact builder
  infra/
    terraform/
      modules/                ← One module per AWS resource group
        dynamodb/
        s3_artifacts/
        cognito/
        api_gateway/
        lambda_functions/
        step_functions/
        eventbridge_scheduler/
        ses/
        secrets_manager/
        iam/
        monitoring/
        amplify_public_site/
        amplify_admin_site/
      envs/
        dev/
        prod/
  packages/
    shared-types/             ← Python + TS shared type contracts
    prompt-policies/          ← Reusable prompt fragments and style guides
  notebooks/
    ebook_platform_test_harness.ipynb   ← Full UC-01→UC-15 test + purge
    requirements.txt
  docs/
    local-dev.md              ← Developer onboarding guide
  .env.local.example          ← Credential template (committed, no secrets)
  .env.local                  ← Actual dev credentials (gitignored)
  .gitignore
  plan.md                     ← This file
  DevelopmentPlan.md          ← Stack decisions, tooling, workflow guide
```

---

## DynamoDB Schema — Single Table: `ebook_platform`

| Entity | PK | SK |
|---|---|---|
| Topic config | `TOPIC#<id>` | `META` |
| Topic schedule | `TOPIC#<id>` | `SCHEDULE` |
| Topic run | `TOPIC#<id>` | `RUN#<run_id>` |
| Draft | `TOPIC#<id>` | `DRAFT#<run_id>` |
| Published version | `TOPIC#<id>` | `PUBLISHED#<version>` |
| Review | `TOPIC#<id>` | `REVIEW#<run_id>` |
| Feedback item | `TOPIC#<id>` | `FEEDBACK#<feedback_id>` |
| Trace event | `RUN#<run_id>` | `EVENT#<timestamp>#<event_type>` |
| Global settings | `SETTINGS` | `BOOK` |
| Prompt policy | `SETTINGS` | `PROMPT_POLICY#<name>` |
| Notification log | `NOTIF#<recipient>` | `TS#<timestamp>` |

**GSIs:**
| GSI | PK | SK | Purpose |
|---|---|---|---|
| GSI1 | `ENTITY_TYPE` | `ORDER_KEY` | List topics/reviews sorted by order |
| GSI2 | `RUN_STATUS#<status>` | `UPDATED_AT` | Operational monitoring |
| GSI3 | `REVIEW_STATUS#<status>` | `UPDATED_AT` | Pending review queue |
| GSI4 | `SCHEDULE_BUCKET#<bucket>` | `NEXT_RUN_AT` | Schedule views |
| GSI5 | `FEEDBACK_TOPIC#<topic_id>` | `CREATED_AT` | Feedback trend analysis |

---

## S3 Artifact Layout

```
s3://ebook-platform-artifacts-<env>/
  topics/
    <topic_id>/
      runs/
        <run_id>/
          raw/          ← fetched page content
          extracted/    ← normalized text
          verified/     ← validated evidence pack
          draft/        ← initial chapter draft
          review/       ← final staged draft for admin
          diff/         ← change summary vs prior published version
  published/
    topics/
      <topic_id>/
        v001/           ← promoted on approval; history retained
        v002/
  site/
    current/
      toc.json
      search/
        index.json      ← Lunr.js search index, rebuilt on every publish
      topics/
      assets/
  releases/
    weekly/
      2026-W15/
```

---

## Admin API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/topics` | List all topics |
| POST | `/admin/topics` | Create topic |
| GET | `/admin/topics/{topicId}` | Get topic details |
| PUT | `/admin/topics/{topicId}` | Update topic |
| DELETE | `/admin/topics/{topicId}` | Soft-delete topic |
| PUT | `/admin/topics/reorder` | Reorder topics |
| POST | `/admin/topics/{topicId}/trigger` | Manual run trigger |
| GET | `/admin/topics/{topicId}/runs` | Run history |
| GET | `/admin/topics/{topicId}/runs/{runId}` | Run detail + trace |
| GET | `/admin/topics/{topicId}/review/{runId}` | Review package |
| POST | `/admin/topics/{topicId}/review/{runId}` | Approve / reject |
| GET/PUT | `/admin/settings/book` | Global settings |
| GET/PUT | `/admin/settings/prompt-policies` | Prompt policy fragments |
| GET | `/admin/feedback/summary` | Feedback trends |

## Public API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/public/comments` | Reader comment |
| POST | `/public/highlights` | Reader highlight |
| GET | `/public/releases/latest` | Latest release summary |
| GET | `/public/search-manifest` | Optional search metadata |

---

## Multi-Agent Pipeline

### Agent Roles

| Agent | Model | Input | Output |
|---|---|---|---|
| Topic Planner | `gpt-4o-mini` | topic config, instructions, prior feedback | research plan, subtopic checklist, source classes |
| Research Agent | `gpt-4o` | research plan | evidence set, fetched content, source metadata |
| Evidence Verifier | `gpt-4o-mini` | evidence set | validated evidence pack, exclusion list, coverage report |
| Chapter Writer | `gpt-4o` | validated evidence, style guide | structured draft |
| Editorial Reviewer | `gpt-4o` | draft, admin instructions | revised draft, editorial scorecard |
| Release Diff Agent | `gpt-4o-mini` | prior version, new draft | diff summary, release notes |

### `openai_runtime` Adapter — Exposed Functions Only

```python
run_planner_agent(topic_context)   → research_plan
run_research_agent(research_plan)  → evidence_set
run_verifier_agent(evidence_set)   → validated_evidence
run_writer_agent(validated_evidence, style_guide) → draft_content
run_editor_agent(draft_content, instructions)     → final_draft, scorecard
run_diff_agent(prior_version, new_draft)          → diff_summary
```

No other module may import or call the OpenAI SDK directly.

### Research Agent Tools

```python
search_web(query, constraints)   # web search with optional exclusion list
fetch_url(url)                   # fetch and extract page content
score_source(metadata)           # authority/freshness scoring
extract_content(html)            # normalize HTML to markdown
```

### Step Functions State Machine

```
LoadTopicConfig
  → AssembleTopicContext
  → PlanTopic               [planner_worker.py → run_planner_agent()]
  → ResearchTopic           [research_worker.py → run_research_agent()]
  → VerifyEvidence          [verifier_worker.py → run_verifier_agent()]
  → PersistEvidenceArtifacts [artifact_persister.py → S3]
  → DraftChapter            [draft_worker.py → run_writer_agent()]
  → EditorialReview         [editorial_worker.py → run_editor_agent()]
  → BuildDraftArtifact      [draft_builder_worker.py → S3 staging]
  → GenerateDiffAndReleaseNotes [diff_worker.py → run_diff_agent()]
  → NotifyAdminForReview    [approval_worker.py → SES + store task token]
  → WaitForApproval         [Step Functions callback/task token]
      → Approved:
          → PublishTopic    [publish_worker.py → S3 promotion]
          → RebuildIndexes  [search_index_worker.py → TOC + Lunr index]
          → NotifyOwner     [SES notification]
          → SUCCEEDED
      → Rejected:
          → StoreRejection  [approval_worker.py → DynamoDB]
          → SUCCEEDED
```

Every stage emits `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED` trace events with: `agent_name`, `model_name`, `token_usage_prompt`, `token_usage_completion`, `cost_usd`.

---

## Human-in-the-Loop Approval

- Step Functions **callback/task token pattern** — workflow pauses at `WaitForApproval`
- Task token stored in `TOPIC#<id> | REVIEW#<run_id>` DynamoDB record
- Admin approves/rejects via `POST /admin/topics/{topicId}/review/{runId}`
- API calls `SendTaskSuccess` or `SendTaskFailure` with stored token
- Default timeout: **72 hours** — on timeout draft stays staged, status = `TIMED_OUT`

---

## Security Controls

- Cognito JWT authorizer on all `/admin/*` routes; public routes unauthenticated
- API Gateway rate limiting on `/public/*` endpoints
- OpenAI key in Secrets Manager only; Lambdas fetch at runtime via `boto3`
- S3 buckets private; public site artifacts served through Amplify CDN only
- Least-privilege IAM role per Lambda function
- HTTPS enforced everywhere; encryption at rest on S3, DynamoDB, Secrets Manager
- Input length limits and `moderation_status` flag on all reader-submitted content

---

## Milestones

### Milestone 1 — Infrastructure Foundation (Week 1–2)
**Terraform modules:** `dynamodb`, `s3_artifacts`, `cognito`, `api_gateway`, `lambda_functions`, `step_functions`, `eventbridge_scheduler`, `ses`, `secrets_manager`, `iam`, `monitoring`, `amplify_public_site`, `amplify_admin_site`

**Deliverable:** `terraform apply` in `infra/terraform/envs/dev` produces a fully deployed empty platform. All resources visible in AWS console.

**Key decision:** Terraform provisions platform primitives only. Per-topic EventBridge schedules are created dynamically by the API at runtime.

---

### Milestone 2 — Topic CRUD API + Admin UI (Week 3–4)
**Lambda handler:** `services/api/topics.py`

**Endpoints:** GET/POST/PUT/DELETE `/admin/topics`, PUT `/admin/topics/reorder`

**DynamoDB entities written:** `TOPIC#<id> | META`, `TOPIC#<id> | SCHEDULE`, `SETTINGS | BOOK`

**Admin UI screens:** topic list, create/edit form (title, description, instructions, subtopics, schedule), drag-and-drop reorder

**Business rules:** BR-001 (no publish without approved version), BR-008 (soft delete retained)

**Trace events:** `TOPIC_CREATED`, `TOPIC_UPDATED`, `TOPIC_DELETED`

---

### Milestone 3 — Scheduling and Manual Trigger (Week 5)
**Manual trigger:** `POST /admin/topics/{topicId}/trigger` → creates `RUN#<run_id>` in DynamoDB → starts Step Functions execution

**Dynamic scheduling:** on topic create/update, API Lambda upserts per-topic EventBridge Scheduler entry. Supported: `manual`, `daily`, `weekly`, custom cron.

**Trace events:** `RUN_TRIGGERED_MANUAL`, `RUN_TRIGGERED_SCHEDULE`

---

### Milestone 4 — Multi-Agent Pipeline (Week 6–8)
**Workers:** `topic_loader.py`, `topic_context_builder.py`, `planner_worker.py`, `research_worker.py`, `verifier_worker.py`, `artifact_persister.py`, `draft_worker.py`, `editorial_worker.py`, `draft_builder_worker.py`, `diff_worker.py`, `approval_worker.py`

**`openai_runtime` adapter:** `services/openai-runtime/` — sole module that imports OpenAI SDK. Reads API key from Secrets Manager at cold start.

**Local pipeline testing:** AWS Step Functions Local docker image (`amazon/aws-stepfunctions-local`) + real dev DynamoDB/S3

**Trace events per stage:** `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED` with `token_usage`, `cost_usd`

---

### Milestone 5 — Admin Review and Approval (Week 9–10)
**Endpoints:** GET/POST `/admin/topics/{topicId}/review/{runId}`

**DynamoDB entities:** `TOPIC#<id> | REVIEW#<run_id>` (task_token_reference, review_status, draft_artifact_uri, diff_summary_uri, notes, reviewer, timeout_at)

**Admin UI screens:** review queue, draft review page (content viewer, diff view, source summary, approve/reject controls with notes)

**Trace events:** `REVIEW_STARTED`, `REVIEW_APPROVED`, `REVIEW_REJECTED`, `REVIEW_TIMED_OUT`

---

### Milestone 6 — Incremental Publishing (Week 11)
**`publish_worker.py`:** S3 copy staging → `published/topics/<id>/v<NNN>/`; update `PUBLISHED#<version>` and `META` in DynamoDB

**`search_index_worker.py`:** query all active published topics → build Lunr.js JSON index → write `site/current/search/index.json` + `toc.json` + sitemap

**Trace events:** `TOPIC_PUBLISHED`, `INDEX_REBUILT`, `TOC_REBUILT`

---

### Milestone 7 — Public Website (Week 12–13) ✅
**Astro static shell:** TOC home (`index.astro`), runtime topic viewer (`topic.astro` — reads `?id=` param), search page, release notes page

**Architecture (updated 2026-04-12):** Static shell deployed once to Amplify. All content fetched from the public API at runtime in the browser — no site rebuild required after each topic publish. `topic.astro` replaces the old `[slug].astro` (which required build-time `getStaticPaths()`).

**Features:** chapter/section navigation sidebar, version badge per topic, Lunr.js client-side search (index fetched at runtime), text highlight+comment widget, release notes page

**Public API handlers:** `services/api/public.py`:
- `GET /public/toc` — table of contents from S3
- `GET /public/topics/{topicId}` — topic content + manifest from S3
- `GET /public/search-index` — Lunr.js index from S3
- `GET /public/releases/latest` — recent publishes from DynamoDB
- `POST /public/comments` — store reader comment
- `POST /public/highlights` — store text highlight

**Abuse controls:** input length limits, rate limiting at API GW, `moderation_status` flag

**Live URL:** https://dev.djcvgu9ysuar.amplifyapp.com

---

### Milestone 8 — Run History and Feedback UI (Week 14)
**Admin UI screens:** run history per topic (status, time, cost_usd), run detail (stage-by-stage trace, token usage), failed-run investigation (error messages, retry button), feedback list (reader comments, highlights, admin notes)

**Endpoints:** GET `/admin/topics/{topicId}/runs`, GET `/admin/topics/{topicId}/runs/{runId}`, GET `/admin/feedback/summary`

---

### Milestone 9 — Weekly Digest (Week 15)
**`digest_worker.py`** triggered by weekly EventBridge Scheduler:
1. Query DynamoDB for `TOPIC_PUBLISHED` trace events in past 7 days
2. Assemble change summary (title, version, changelog excerpt)
3. Send HTML email via SES to configured owner email
4. Write `NOTIF#<recipient> | TS#<timestamp>` to DynamoDB

**Trace event:** `DIGEST_SENT`

---

### Milestone 10 — Local Dev Setup + Jupyter Notebook Test Harness (Week 15, parallel)

See detailed specification in the **Jupyter Notebook** section below.

---

## Local Development Setup

### Credential and Configuration Model

```
.env.local.example    ← committed template, no secrets
.env.local            ← gitignored, developer fills in real values
```

All Lambda handlers and workers read configuration from environment variables. `boto3` picks up `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` automatically.

### Local API Server

```bash
cd services/api
uvicorn local_dev_server:app --reload --port 8000
```

`local_dev_server.py` maps route paths to the same handler functions deployed to Lambda — same code runs locally and in AWS.

### Local Worker Execution

```bash
python services/workers/topic_loader.py --topic-id <id> --run-id <run_id>
```

Each worker reads AWS credentials from environment and hits real dev-account resources.

### Step Functions Local (optional)

```bash
docker run -p 8083:8083 amazon/aws-stepfunctions-local
```

Set `STEP_FUNCTIONS_ENDPOINT=http://localhost:8083` in `.env.local`. All other services remain real AWS.

### Developer Onboarding Steps

1. Copy `.env.local.example` → `.env.local`, fill in dev AWS credentials and resource names
2. `cd infra/terraform/envs/dev && terraform init && terraform apply`
3. `cd services/api && uvicorn local_dev_server:app --reload`
4. Optionally: `docker run -p 8083:8083 amazon/aws-stepfunctions-local`
5. Open `notebooks/ebook_platform_test_harness.ipynb` and run cells top-to-bottom

Full guide: `docs/local-dev.md`

---

## Jupyter Notebook Test Harness

**File:** `notebooks/ebook_platform_test_harness.ipynb`
**Dependencies:** `notebooks/requirements.txt` — `requests`, `boto3`, `python-dotenv`, `jupyter`

All `topic_id`, `run_id`, `execution_arn` values are tracked in a `created_resources` dict at notebook top and reused across cell groups. No manual ID copy/paste.

| Cell Group | Use Case | What It Tests |
|---|---|---|
| 0 | Setup | Load `.env.local`, init boto3 clients, connectivity check |
| 1 | UC-01 | Create topic → assert DynamoDB META + TOPIC_CREATED trace |
| 2 | UC-02 | Update topic instructions → assert META updated |
| 3 | UC-03 | Create second topic, reorder → assert order values |
| 4 | UC-04 | Manual trigger → assert RUN record + Step Functions started |
| 5 | UC-05 | Schedule smoke test → assert SCHEDULE record |
| 6 | UC-06 | Poll pipeline until `WaitForApproval` → assert DRAFT, REVIEW, S3 artifacts, trace events |
| 7 | UC-07 + UC-08 | GET review package, POST approve → assert SUCCEEDED, PUBLISHED#v001, S3 published, index rebuilt |
| 8 | UC-09 | Trigger second topic run, POST reject → assert REJECTED, no PUBLISHED record |
| 9 | UC-10 | Re-trigger approved topic, approve again → assert PUBLISHED#v002, v001 still present |
| 10 | UC-11 | Load search index JSON, simulate Lunr keyword query → assert hits |
| 11 | UC-12 | POST highlight + POST comment → assert FEEDBACK records |
| 12 | UC-13 | GET feedback summary → assert topic entries with counts |
| 13 | UC-14 | Invoke digest_worker → assert NOTIF record + DIGEST_SENT trace |
| 14 | UC-15 | Trigger run with bad config → wait for FAILED → GET run detail → assert STAGE_FAILED event |
| 15 | — | GET run history + cost → assert token_usage and cost_usd populated |
| **16** | **PURGE** | **Stop Step Functions, delete EventBridge schedules, batch-delete DynamoDB items, delete S3 artifacts** |

### Purge Cell Design Rules

- Operates only on IDs in `created_resources` — never blindly wipes tables or buckets
- Scoped to test data; existing non-test topics and published content are untouched
- Each step wrapped in `try/except` with clear log output so partial failures are visible
- Idempotent — safe to re-run if partially completed

```python
# Purge sequence:
# 1. Stop all RUNNING Step Functions executions for test run_ids
# 2. Delete per-topic EventBridge Schedules for test topic_ids
# 3. Batch-delete all DynamoDB items: TOPIC#*, RUN#*, NOTIF#* for test IDs
# 4. Delete S3 objects under topics/<test_topic_ids>/ and published/topics/<test_topic_ids>/
# 5. Assert: DynamoDB scan for test keys returns 0 items
# 6. Assert: S3 list_objects for test prefixes returns 0 objects
# 7. Print: "Purge complete. AWS dev environment clean."
```

---

## Verification Checklist

### Infrastructure (Milestone 1)
- [ ] `terraform plan` produces no unexpected changes
- [ ] `terraform apply` completes in dev without errors
- [ ] DynamoDB table `ebook_platform` with 5 GSIs exists
- [ ] S3 artifact bucket with correct lifecycle rules exists
- [ ] Cognito user pool with admin group exists
- [ ] Step Functions state machine skeleton deployed
- [ ] Amplify apps deployed for public and admin sites

### Topic CRUD (Milestone 2)
- [ ] Create topic → DynamoDB META item present
- [ ] Update → changes reflected immediately
- [ ] Soft delete → `active=false` in DynamoDB, excluded from topic list
- [ ] Reorder → order values updated for affected topics

### Pipeline (Milestone 4)
- [ ] Manual trigger → Step Functions execution visible in AWS console
- [ ] All 11 stages transition in order
- [ ] S3 artifact folders populated per stage
- [ ] Trace events written to DynamoDB for every stage
- [ ] `token_usage` and `cost_usd` fields populated in trace events

### Approval (Milestone 5)
- [ ] Admin sees pending draft with diff and source summary
- [ ] Approve → Step Functions SUCCEEDED → artifact in `published/`
- [ ] Reject with notes → REJECTED status, notes stored, no PUBLISHED record
- [ ] Timeout → TIMED_OUT status, draft stays staged

### Publish (Milestone 6)
- [ ] `published/topics/<id>/v001/` in S3 after first approval
- [ ] `site/current/search/index.json` rebuilt
- [ ] `site/current/toc.json` updated

### Public Site (Milestone 7) ✅
- [x] Topic pages render on Amplify public URL (https://dev.djcvgu9ysuar.amplifyapp.com)
- [x] Lunr search returns results for known keyword (index fetched at runtime from /public/search-index)
- [x] Comment/highlight widget submits → DynamoDB FEEDBACK item created
- [x] `/admin/*` returns 401 for unauthenticated requests
- [x] New topics appear without site rebuild — runtime API fetching architecture
- [x] GET /public/toc, /public/topics/{id}, /public/search-index, /public/releases/latest all operational

### Digest (Milestone 9)
- [ ] Weekly EventBridge schedule triggers `digest_worker`
- [ ] Owner email received in SES sandbox with correct topic list
- [ ] NOTIF record written to DynamoDB

### Notebook (Milestone 10)
- [ ] Notebook runs top-to-bottom without manual intervention
- [ ] Each cell group prints `✓ PASS`
- [ ] Purge cell leaves zero test artifacts in DynamoDB and S3

---

## Business Rules Quick Reference

| Rule | Description |
|---|---|
| BR-001 | Topic not publicly visible until at least one approved version exists |
| BR-002 | Rejected draft does not overwrite current published version |
| BR-003 | Admin instructions are topic-specific; applied during planning and writing stages |
| BR-004 | Feedback may influence future generation but cannot bypass approval |
| BR-005 | Topic schedules may differ by topic |
| BR-006 | Topic dependency relationships influence planning |
| BR-007 | Published book ordering follows configured topic order |
| BR-008 | Soft-deleted topics excluded from publishing but retained for history |

---

## Phase 2 Deferred Items

- Semantic/vector search (OpenSearch Serverless)
- WebSocket live pipeline status in Admin UI
- Feedback Learning Agent and prompt policy update workflow
- Rich evidence inspection UI (source citation visualization)
- Multi-admin editorial tiers
- Automated A/B model evaluation across model variants
- Full WYSIWYG browser editing

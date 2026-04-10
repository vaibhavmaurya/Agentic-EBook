# Agentic Ebook Platform V3 — Solution Architecture, Design, Implementation, and Deployment

## 1. Purpose

This document defines the target solution architecture for the Agentic Ebook Platform V3.

It covers:
- reference architecture
- multi-agent design
- AWS service mapping
- runtime workflows
- data model
- API design
- implementation approach
- deployment model with Terraform
- operational controls

This V3 design assumes the following strategic decisions:
- the platform is **fully dynamic and per-topic**
- the content generation pipeline is **explicitly multi-agent**
- the platform is hosted in **AWS**
- the AI runtime uses the **OpenAI SDK and OpenAI models**, not Amazon Bedrock
- **human approval** is mandatory before public publication

---

## 2. Architectural Positioning

V3 should no longer be framed as a weekly batch book generator with optional per-topic refresh.

It should be framed as:

**A dynamic topic orchestration platform in which each topic is an independently scheduled, multi-agent content pipeline with staging, review, approval, publishing, and feedback learning.**

The “book” is the assembled presentation layer built from topic pages. The weekly cadence remains useful, but only for release digesting and operational reporting, not as the sole execution model.

---

## 3. Design Principles

1. **Topic-first design** — each topic is an independent lifecycle unit.
2. **AWS controls process** — orchestration, approval, scheduling, publishing, and traceability remain deterministic.
3. **AI controls content work** — agents plan, research, synthesize, and review content.
4. **Human approval gates publishing** — no direct autonomous publishing.
5. **Static-first delivery** — public website stays lightweight and low-management.
6. **Full traceability** — every material state transition is written to DynamoDB.
7. **S3 for artifacts, DynamoDB for metadata** — large documents stay in object storage; operational metadata stays queryable.
8. **Incremental publishing** — publish topics independently and refresh shared indexes/navigation.
9. **Provider abstraction** — the system integrates OpenAI through a dedicated runtime adapter layer so future model/provider changes remain manageable.
10. **Terraform-first deployment** — no critical manual infrastructure steps.

---

## 4. Target Technology Stack

## 4.1 Core Stack

| Layer | Recommended Technology | Notes |
|---|---|---|
| Public website | Astro or Next.js static export on Amplify Hosting | Lightweight, SEO-friendly, CDN-backed |
| Admin UI | React + Vite SPA on Amplify Hosting | Simple management console |
| Authentication | Amazon Cognito | Admin login and token issuance |
| API layer | API Gateway HTTP API + Lambda | Lightweight serverless backend |
| Orchestration | AWS Step Functions Standard | Durable workflow control |
| Scheduling | Amazon EventBridge Scheduler | Per-topic cron/rate schedules |
| Compute | AWS Lambda | API, orchestration tasks, adapters |
| Artifact storage | Amazon S3 | Raw sources, drafts, published artifacts |
| Operational metadata | Amazon DynamoDB | Config, runs, reviews, traces |
| Secrets | AWS Secrets Manager | OpenAI API key and other secrets |
| Notifications | Amazon SES + SNS (optional) | Emails and fan-out |
| Search (MVP) | Lunr.js client-side search | Very low management |
| Search (Phase 2) | OpenSearch Serverless vector/search | Semantic retrieval and admin search |
| AI runtime | OpenAI Responses API via SDK | Core model inference and tool use |
| Optional agent framework | OpenAI Agents SDK | Helpful for multi-agent handoffs and traces |
| IaC | Terraform | Full AWS deployment |

---

## 5. High-Level Reference Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                         Public Reader Experience                    │
│  Amplify Hosting (Public Site)                                     │
│  - ebook pages                                                     │
│  - search                                                          │
│  - highlights and comments UI                                      │
└────────────────────────────────────────────────────────────────────┘
                 │
                 │ calls
                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                      API Layer (HTTP API + Lambda)                  │
│  - comments/highlights APIs                                         │
│  - admin APIs                                                       │
│  - approval APIs                                                    │
└────────────────────────────────────────────────────────────────────┘
                 │
                 ├──────────────────────────────┐
                 │                              │
                 ▼                              ▼
┌──────────────────────────────┐      ┌──────────────────────────────┐
│       DynamoDB               │      │            S3                │
│  - topic config              │      │  - raw fetched content       │
│  - run metadata              │      │  - normalized research       │
│  - review records            │      │  - staged chapter drafts     │
│  - feedback                  │      │  - published site artifacts  │
│  - trace events              │      │  - changelogs and snapshots  │
└──────────────────────────────┘      └──────────────────────────────┘
                 ▲                              ▲
                 │                              │
                 └──────────────┬───────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Step Functions Topic Pipeline                    │
│  Load Topic -> Plan -> Research -> Verify -> Draft -> Review Prep  │
│  -> Wait for Approval -> Publish -> Rebuild Indexes -> Notify      │
└────────────────────────────────────────────────────────────────────┘
                                ▲
                                │
          ┌─────────────────────┴───────────────────────┐
          │                                             │
          ▼                                             ▼
┌──────────────────────────────┐      ┌──────────────────────────────┐
│   EventBridge Scheduler      │      │   Manual Trigger APIs        │
│  per-topic schedules         │      │  admin-triggered runs        │
└──────────────────────────────┘      └──────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                 OpenAI Runtime Adapter (Lambda/ECS optional)       │
│  - Responses API calls                                             │
│  - tool definitions                                                │
│  - background jobs                                                 │
│  - structured outputs                                              │
│  - optional Agents SDK orchestration                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 6. Why This Architecture

This architecture is preferred because it separates concerns cleanly:

- **EventBridge Scheduler** manages independent schedules.
- **Step Functions** guarantees ordered, durable workflow execution and callback-based human review.
- **Lambda** keeps compute serverless for most tasks.
- **S3** stores large artifacts and immutable output snapshots cheaply.
- **DynamoDB** provides the operational ledger and fast query model.
- **OpenAI runtime adapter** isolates the AI provider contract from the rest of the AWS system.
- **Amplify Hosting** minimizes web hosting operations.

---

## 7. Multi-Agent Architecture

## 7.1 Recommended Agent Roles

The multi-agent layer should be explicit and role-based.

| Agent | Primary Responsibility | Input | Output |
|---|---|---|---|
| Topic Planner Agent | Interpret topic config and build execution plan | topic config, admin instructions, dependencies, prior feedback | research plan, source plan, output contract |
| Research Agent | Gather web evidence and candidate source material | research plan, search tools, fetch tools | source list, extracted notes, evidence set |
| Evidence Verifier Agent | Validate authority, freshness, duplication, contradictions, and topic coverage | source list, raw extracts, topic goals | validated evidence pack, exclusion list, coverage report |
| Chapter Writer Agent | Produce chapter-quality draft | validated evidence pack, style guide, chapter template | staged draft content |
| Editorial Reviewer Agent | Check structure, compliance, readability, tone, cross-links, and policy adherence | staged draft, admin instructions, book guidelines | revised draft, editorial scorecard |
| Release Diff Agent | Compare new output against prior published version | prior version, new draft | change summary, release notes |
| Feedback Learning Agent | Mine admin and reader feedback into future guidance | comments, highlights, review notes, rejection notes | instruction deltas, prompt policy proposals |

## 7.2 Agent Collaboration Pattern

Use a **supervisor + specialists** pattern.

- The **Topic Planner Agent** acts as the local supervisor for content work.
- Specialist agents execute bounded roles.
- AWS Step Functions remains the ultimate orchestrator.

This avoids uncontrolled autonomy while still benefiting from specialization.

## 7.3 Agent Runtime Recommendation

### Preferred runtime option for production
Use the **OpenAI Responses API** directly through a dedicated runtime adapter.

### Optional enhancement
Use the **OpenAI Agents SDK** when you want:
- explicit handoffs between agents
- richer agent traces
- tool and guardrail abstractions
- easier local development of multi-agent logic

The architecture should work with either path because the adapter isolates the model/runtime choice.

---

## 8. OpenAI Integration Design

## 8.1 Integration Pattern

Create a dedicated `openai_runtime` module that exposes stable internal methods such as:

- `run_planner_agent()`
- `run_research_agent()`
- `run_verifier_agent()`
- `run_writer_agent()`
- `run_editor_agent()`
- `run_diff_agent()`
- `run_feedback_agent()`

The rest of the platform should never call the OpenAI SDK directly.

## 8.2 Runtime Features to Use

| Feature | Use in V3 |
|---|---|
| Responses API | Primary inference API |
| Structured outputs / JSON schema | Agent contracts between workflow stages |
| Function tools | Search, fetch, normalize, compare, publish helper actions |
| Background mode | Long-running deep research or writing tasks |
| Webhooks | Resume workflow after background completion |
| Optional Agents SDK | Agent handoffs and tracing |

## 8.3 Tooling Model

Agent tools should be exposed as deterministic backend tools, not direct browser functions.

Recommended tools:
- `search_web(query, constraints)`
- `fetch_url(url)`
- `extract_content(html)`
- `score_source(metadata)`
- `compare_versions(old, new)`
- `load_topic_context(topic_id)`
- `store_draft(topic_id, artifact_uri)`
- `request_human_review(topic_id, run_id)`

## 8.4 Guardrail Approach

Guardrails should exist at four levels:

1. **Prompt guardrails** — chapter style guide, banned behaviors, citation rules
2. **Tool guardrails** — allow only approved tools and bounded tool arguments
3. **Workflow guardrails** — Step Functions controls stage order and approvals
4. **Human guardrails** — publish requires explicit admin approval

---

## 9. Per-Topic Runtime Workflow

## 9.1 Primary Topic State Machine

```text
LoadTopicConfig
  -> AssembleTopicContext
  -> PlanTopic
  -> ResearchTopic
  -> VerifyEvidence
  -> PersistEvidenceArtifacts
  -> DraftChapter
  -> EditorialReview
  -> BuildDraftArtifact
  -> GenerateDiffAndReleaseNotes
  -> NotifyAdminForReview
  -> WaitForApproval
      -> If Approved: PublishTopic -> RebuildIndexes -> NotifyOwner -> Complete
      -> If Rejected: StoreRejection -> Complete
```

## 9.2 Workflow Stage Details

### LoadTopicConfig
Reads topic configuration, schedule metadata, dependency references, prior feedback, and the currently published version.

### AssembleTopicContext
Builds the topic execution context object and normalizes prompt inputs.

### PlanTopic
Planner Agent produces:
- subtopic checklist
- research plan
- preferred source classes
- expected output structure
- dependency usage hints

### ResearchTopic
Research Agent gathers evidence using web search and fetch tools. The system can loop internally for additional coverage.

### VerifyEvidence
Evidence Verifier removes duplicates, poor sources, stale content, and unsupported claims.

### PersistEvidenceArtifacts
Stores:
- raw fetched pages
- extracted text
- normalized evidence pack
- source metadata
- coverage report

### DraftChapter
Writer Agent converts validated evidence into a structured chapter.

### EditorialReview
Editorial Reviewer improves or rejects draft quality before it is shown to the human admin.

### BuildDraftArtifact
Converts draft content into website-ready staged HTML/JSON/Markdown artifacts.

### GenerateDiffAndReleaseNotes
Compares prior published topic version to the current draft and produces change notes.

### NotifyAdminForReview
Sends review notification and stores approval token metadata.

### WaitForApproval
Step Functions pauses using a callback token.

### PublishTopic
Promotes approved topic artifacts from staging to public delivery.

### RebuildIndexes
Regenerates table of contents, search index, topic manifests, and release list.

---

## 10. Human-in-the-Loop Approval Design

## 10.1 Approval Pattern

The approval stage should use the Step Functions callback/task token pattern.

### Flow
1. Workflow enters `WaitForApproval` task.
2. Task token is generated.
3. Token and review payload are stored in DynamoDB.
4. Admin reviews staged draft in the admin UI.
5. Admin chooses approve or reject.
6. Approval API validates identity and review state.
7. API calls `SendTaskSuccess` or `SendTaskFailure` with the task token.
8. Workflow resumes deterministically.

## 10.2 Approval Record Model

A review record should contain:
- review_id
- topic_id
- run_id
- task_token_reference
- reviewer_identity
- review_status
- draft_artifact_uri
- diff_summary_uri
- notes
- approved_at / rejected_at
- timeout_at

## 10.3 Timeout Policy

If no review is completed within the configured window:
- workflow moves to timed-out state
- draft remains staged, not published
- owner/admin receives reminder or timeout notification

---

## 11. Data Architecture

## 11.1 Storage Strategy

Use **DynamoDB for metadata** and **S3 for artifacts**.

### DynamoDB stores
- topic definitions
- schedules and next-run state
- run metadata
- review records
- publish pointers
- comments/highlights metadata
- trace events
- prompt policy metadata

### S3 stores
- raw source fetches
- extracted text snapshots
- validated evidence bundles
- generated draft content
- staged topic HTML/JSON
- published topic artifacts
- release note documents
- search index and manifests

## 11.2 Why Split Metadata and Artifacts

This keeps DynamoDB query-efficient and avoids large-item anti-patterns while preserving durable artifact history in S3.

---

## 12. DynamoDB Logical Schema

## 12.1 Single-Table Pattern

Recommended table name: `ebook_platform`

### Core entities

| Entity | PK | SK | Description |
|---|---|---|---|
| Topic config | `TOPIC#<topic_id>` | `META` | master topic definition |
| Topic schedule | `TOPIC#<topic_id>` | `SCHEDULE` | schedule state and config |
| Topic run | `TOPIC#<topic_id>` | `RUN#<run_id>` | one pipeline execution |
| Draft | `TOPIC#<topic_id>` | `DRAFT#<run_id>` | staged output metadata |
| Published version | `TOPIC#<topic_id>` | `PUBLISHED#<version>` | production version metadata |
| Review | `TOPIC#<topic_id>` | `REVIEW#<run_id>` | approval decision state |
| Feedback item | `TOPIC#<topic_id>` | `FEEDBACK#<feedback_id>` | highlights/comments/review feedback |
| Trace event | `RUN#<run_id>` | `EVENT#<timestamp>#<event_type>` | ordered event stream |
| Settings | `SETTINGS` | `BOOK` | global config |
| Prompt policy | `SETTINGS` | `PROMPT_POLICY#<name>` | reusable policy fragments |
| Notification | `NOTIF#<recipient>` | `TS#<timestamp>` | delivery log |

## 12.2 Required Metadata on Trace Events

Every trace event should carry these fields where applicable:
- event_id
- event_type
- topic_id
- run_id
- release_id
- actor_type
- actor_id
- agent_name
- model_name
- prompt_version
- tool_name
- input_artifact_uri
- output_artifact_uri
- source_urls
- token_usage_prompt
- token_usage_completion
- cost_usd
- status
- attempt
- correlation_id
- causation_id
- timestamp

## 12.3 Suggested GSIs

| GSI | Partition Key | Sort Key | Purpose |
|---|---|---|---|
| GSI1 | `ENTITY_TYPE` | `ORDER_KEY` | list topics and reviews |
| GSI2 | `RUN_STATUS#<status>` | `UPDATED_AT` | operational monitoring |
| GSI3 | `REVIEW_STATUS#<status>` | `UPDATED_AT` | pending review queue |
| GSI4 | `SCHEDULE_BUCKET#<bucket>` | `NEXT_RUN_AT` | optional admin schedule views |
| GSI5 | `FEEDBACK_TOPIC#<topic_id>` | `CREATED_AT` | feedback trend analysis |

## 12.4 TTL Usage

TTL should be used for transient operational objects only, such as ephemeral callback state, temporary notifications, or cached diagnostics. It should not be used for durable audit records.

---

## 13. S3 Artifact Layout

```text
s3://ebook-platform-artifacts/
  topics/
    <topic_id>/
      runs/
        <run_id>/
          raw/
          extracted/
          verified/
          draft/
          review/
          diff/
  published/
    topics/
      <topic_id>/
        v001/
        v002/
  site/
    current/
      index.html
      topics/
      assets/
      search/
  releases/
    weekly/
      2026-W15/
```

---

## 14. API Design

## 14.1 Admin APIs

| Endpoint | Method | Purpose |
|---|---|---|
| `/admin/topics` | GET | list topics |
| `/admin/topics` | POST | create topic |
| `/admin/topics/{topicId}` | GET | get topic details |
| `/admin/topics/{topicId}` | PUT | update topic |
| `/admin/topics/{topicId}` | DELETE | archive topic |
| `/admin/topics/reorder` | PUT | reorder topics |
| `/admin/topics/{topicId}/trigger` | POST | manual topic run |
| `/admin/topics/{topicId}/runs` | GET | run history |
| `/admin/topics/{topicId}/runs/{runId}` | GET | detailed run metadata |
| `/admin/topics/{topicId}/review/{runId}` | GET | review package |
| `/admin/topics/{topicId}/review/{runId}` | POST | approve/reject |
| `/admin/settings/book` | GET/PUT | global settings |
| `/admin/settings/prompt-policies` | GET/PUT | reusable guidance |
| `/admin/feedback/summary` | GET | feedback trends |

## 14.2 Public APIs

| Endpoint | Method | Purpose |
|---|---|---|
| `/public/comments` | POST | create reader comment |
| `/public/comments/{id}` | GET | read comment |
| `/public/highlights` | POST | create highlight |
| `/public/search-manifest` | GET | optional search metadata |
| `/public/releases/latest` | GET | latest release summary |

## 14.3 Internal APIs / Worker Contracts

Internal services should use event payloads and Step Functions input/output contracts rather than public REST.

---

## 15. Search Design

## 15.1 MVP Search

Use client-side keyword search with Lunr.js over generated content metadata.

### Why
- very low operational overhead
- no additional backend runtime
- good enough for moderate ebook size

## 15.2 Phase 2 Search

Add OpenSearch Serverless when you need:
- semantic retrieval over published sections
- admin search over evidence artifacts
- source-quality investigations
- similarity-based content checks

---

## 16. Comments, Highlights, and Feedback Design

## 16.1 Public Interaction Model

Each highlight/comment should capture:
- topic_id
- section_id or anchor
- selected text offset/locator
- optional selected text snapshot
- comment text
- user metadata if authenticated, else anonymous/session metadata
- moderation status
- created_at

## 16.2 Feedback Learning Model

The Feedback Learning Agent should process:
- reader comments
- repeated highlight patterns
- admin rejection notes
- manual topic instruction edits
- approval turnaround metrics

Its output should be a **proposed instruction delta**, not an automatic rewrite of core prompts. Admin or operator review should approve durable prompt policy changes.

---

## 17. Website Design Considerations

## 17.1 Public Site

Recommended characteristics:
- static content delivery
- chapter and section navigation
- release notes page
- version badge per topic
- feedback controls
- fast search
- responsive reading layout

## 17.2 Admin Site

Recommended capabilities:
- topic CRUD
- schedule configuration
- trigger topic run
- view detailed run metadata
- inspect source list and evidence summary
- compare draft vs published version
- approve/reject drafts
- review feedback trends
- review operational errors and trace data

---

## 18. Security Design

## 18.1 Identity and Access

- Cognito user pool for admins
- API Gateway HTTP API JWT authorizer for admin routes
- separate public and admin API route policies
- least-privilege IAM for Lambdas and Step Functions

## 18.2 Secrets and Keys

- OpenAI API key in AWS Secrets Manager
- no secrets in frontend build artifacts
- environment variables only for secret references, never plaintext secrets in Terraform state outputs

## 18.3 Content and Abuse Controls

- input validation on comments
- basic abuse controls and rate limiting
- moderation flag support on feedback items
- admin-only approval actions

## 18.4 Network and Encryption

- HTTPS everywhere
- encryption at rest for S3, DynamoDB, Secrets Manager
- optional VPC only if required by org standards; otherwise stay outside VPC to reduce Lambda complexity

---

## 19. Observability and Traceability Design

## 19.1 Operational Observability

Use:
- CloudWatch logs for Lambda and API execution
- CloudWatch metrics and alarms for failures and latency
- X-Ray or distributed tracing where appropriate
- DynamoDB trace events as the business workflow ledger

## 19.2 Business Traceability

Trace event families should include:
- topic lifecycle events
- schedule events
- run lifecycle events
- agent lifecycle events
- tool call events
- review lifecycle events
- publish lifecycle events
- feedback lifecycle events
- notification lifecycle events

## 19.3 Failure Handling

Every stage should emit:
- start event
- completion event
- failure event when applicable
- retry attempt count
- error classification

---

## 20. Scheduling Model

## 20.1 Dynamic Per-Topic Scheduling

Each topic has an independent schedule record.

Supported schedule types:
- manual
- daily
- weekly
- custom cron
- one-time rerun

EventBridge Scheduler should create one schedule per active topic or use a hybrid pattern where a routing scheduler invokes a centralized dispatcher. For a moderate topic count, one schedule per topic is acceptable and aligns with the dynamic-topic operating model.

## 20.2 Manual Trigger Model

Manual triggers should bypass the schedule and create an explicit run with:
- trigger source = `admin_manual`
- actor identity
- reason code or optional note

---

## 21. Incremental Publishing Model

## 21.1 Staging

Each run produces staged artifacts only.

## 21.2 Publish

Approval promotes only the approved topic to production, then refreshes:
- topic page
- table of contents
- search index
- sitemap/manifest
- release notes page

## 21.3 Release Digest

A weekly digest summarizes all approved/published topic changes across the prior window.

This preserves the value of a weekly “release” without forcing all content generation into one batch.

---

## 22. Implementation Design

## 22.1 Recommended Repository Structure

```text
repo/
  apps/
    public-site/
    admin-site/
  services/
    api/
    workers/
    openai-runtime/
    content-build/
  infra/
    terraform/
      modules/
      envs/
  packages/
    shared-types/
    shared-utils/
    prompt-policies/
  docs/
```

## 22.2 Worker Modules

Recommended workers:
- `topic_loader`
- `topic_context_builder`
- `planner_worker`
- `research_worker`
- `verifier_worker`
- `draft_worker`
- `editorial_worker`
- `diff_worker`
- `draft_builder_worker`
- `approval_worker`
- `publish_worker`
- `search_index_worker`
- `digest_worker`
- `feedback_learning_worker`

## 22.3 Language Recommendation

TypeScript is recommended for frontend and python for backend consistency, but Python is also viable for AI-heavy workers.

Pragmatic recommendation:
- Frontend: TypeScript
- API + workflow Lambdas: Python
- AI/runtime-heavy workers: Python

---

## 23. Terraform Deployment Design

## 23.1 Top-Level Modules

```text
terraform/
  modules/
    amplify_public_site/
    amplify_admin_site/
    cognito/
    api_gateway/
    lambda_functions/
    step_functions/
    eventbridge_scheduler/
    dynamodb/
    s3_artifacts/
    ses/
    iam/
    secrets_manager/
    monitoring/
    optional_opensearch/
  envs/
    dev/
    test/
    prod/
```

## 23.2 Core Terraform Responsibilities

### Amplify modules
- app creation
- branch settings
- environment variables
- custom domains if needed

### Cognito module
- user pool
- user pool client
- admin groups/claims if required

### API module
- HTTP API
- JWT authorizer
- routes and integrations

### Lambda module
- functions
- IAM roles
- environment variables
- log groups

### Step Functions module
- topic state machine
- IAM role
- CloudWatch logging config

### Scheduler module
- schedule group
- IAM role for invoking Step Functions
- optional bootstrap schedule(s)

### DynamoDB module
- single table
- GSIs
- PITR
- TTL for transient items if enabled

### S3 module
- artifact bucket
- published site artifact bucket if separate
- lifecycle rules
- encryption

### Monitoring module
- alarms for failed executions
- alarms for Lambda errors
- dashboards

## 23.3 Dynamic Resources vs Terraform-Managed Resources

Terraform should provision the **platform primitives**.  
The application should create **dynamic topic schedules** at runtime.

### Provision with Terraform
- schedule groups
- IAM roles
- Step Functions
- buckets
- table
- APIs
- Cognito
- Lambdas

### Create dynamically at runtime
- per-topic scheduler entries
- review callback records
- run records
- draft artifacts
- publish manifests

---

## 24. Recommended Delivery Environments

### Dev
- low-cost configuration
- manual triggers favored
- reduced retention periods

### Test / UAT
- realistic workflow testing
- approval flow testing
- integration testing with OpenAI and notifications

### Prod
- protected admin access
- alarms and dashboards enabled
- production-grade retention and backup settings

---

## 25. CI/CD Approach

## 25.1 Infrastructure Pipeline

- `terraform fmt`
- `terraform validate`
- `terraform plan`
- approval gate
- `terraform apply`

## 25.2 Application Pipeline

- lint
- unit tests
- integration tests
- package Lambdas
- deploy backend
- build and deploy public/admin sites

## 25.3 Release Controls

- separate application deployment from content publishing
- infrastructure changes should not force content regeneration
- content publishing should not require application redeployment

---

## 26. Cost and Management Posture

## 26.1 Why This Is Low Management

This architecture keeps operations light because it relies primarily on:
- Amplify Hosting
- API Gateway HTTP API
- Lambda
- Step Functions
- EventBridge Scheduler
- DynamoDB
- S3
- Cognito
- SES

There are no always-on servers in the MVP path.

## 26.2 Main Cost Drivers

Primary cost categories:
- OpenAI model usage
- search/fetch volume
- Step Functions execution volume
- Lambda duration
- DynamoDB reads/writes for traces and feedback
- Amplify hosting and CDN traffic

## 26.3 Cost Control Levers

- cap topic concurrency
- cap max source fetches per run
- distinguish light refresh vs deep refresh modes
- keep public search client-side in MVP
- use TTL for non-durable transient records
- route expensive semantic retrieval to phase 2 only when needed

---

## 27. Recommended Phased Implementation

## Phase 1 — MVP
- topic CRUD
- per-topic scheduling
- manual trigger
- planner/research/writer/editor agents
- staging and admin approval
- incremental publishing
- keyword search
- comments/highlights
- trace events
- weekly digest

## Phase 2 — Enhanced Governance and Search
- richer evidence inspection UI
- semantic retrieval with OpenSearch Serverless
- source citation visualization
- prompt policy review workflow
- live status updates

## Phase 3 — Advanced Editorial Intelligence
- model/agent A/B testing
- automated quality scoring pipelines
- richer editorial roles and SLAs
- advanced analytics and cost dashboards

---



## 30. Reference Notes

The following official capabilities informed this design direction:

- OpenAI Responses API and tool-based orchestration
- OpenAI Agents SDK with agent handoffs and tracing
- AWS Step Functions callback/task-token pattern for human-in-the-loop approval
- Amazon EventBridge Scheduler for dynamic recurring schedules
- AWS Amplify Hosting for low-management static/SPAs
- API Gateway HTTP API JWT authorizers for Cognito-based admin access
- OpenSearch Serverless vector collections for future semantic retrieval
- DynamoDB TTL for transient item cleanup


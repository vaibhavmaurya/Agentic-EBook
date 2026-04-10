# CLAUDE.md — Agentic Ebook Platform V3

This file is read automatically by Claude Code in every conversation. Keep it up to date.

---

## Project Summary

A dynamic, per-topic, multi-agent publishing platform. AI agents research, draft, and stage content per topic. Human admin approves before incremental publish to a public ebook site. Runs entirely on AWS.

**Full plan:** `plan.md` | **Stack and tooling decisions:** `DevelopmentPlan.md`

---

## Non-Negotiable Rules

1. **Only `services/openai-runtime/` may import the `openai` package.** All other modules call the functions exposed in that module's `__init__.py`. Never add `import openai` or `from openai import ...` anywhere else.
2. **No content may be published without human admin approval.** The Step Functions `WaitForApproval` callback token pattern is the gate. Never shortcut it.
3. **No AWS credentials in source code.** All config via environment variables (`.env.local` locally, Lambda environment + Secrets Manager in AWS). `.env.local` is gitignored.
4. **Terraform provisions platform primitives only.** Per-topic EventBridge Scheduler entries are created dynamically at runtime by the API — not by Terraform.
5. **Update `plan.md` whenever scope or sequencing changes.** Update the milestone status table in `DevelopmentPlan.md` when a milestone completes.

---

## Architecture in One Paragraph

API Gateway HTTP API → Lambda handlers (`services/api/`) → DynamoDB (metadata) + S3 (artifacts). Admin trigger or EventBridge Scheduler → Step Functions Standard workflow → 11 Lambda workers in `services/workers/` → `openai_runtime` adapter (OpenAI Responses API). Pipeline pauses at `WaitForApproval` (callback token). Admin approves via API → `publish_worker` promotes S3 artifacts → `search_index_worker` rebuilds Lunr.js index + TOC. Public Astro site reads from S3 + public API. Admin SPA (React) reads from admin API (Cognito JWT protected).

---

## Key File Locations

| File/Dir | Purpose |
|---|---|
| `plan.md` | Living MVP plan — milestones, schema, API endpoints, verification checklist |
| `DevelopmentPlan.md` | Stack decisions, MCP tools, env vars reference, milestone status |
| `services/openai-runtime/__init__.py` | ONLY place openai SDK is imported |
| `packages/prompt-policies/style_guide.md` | Chapter style guide injected into Writer and Editor agent prompts |
| `notebooks/ebook_platform_test_harness.ipynb` | UC-01→UC-15 end-to-end test + purge |
| `.env.local.example` | Credential template — copy to `.env.local` (gitignored) |
| `.claude/settings.json` | MCP server config + PostToolUse hooks |
| `infra/terraform/modules/` | One Terraform module per AWS resource group |
| `infra/terraform/envs/dev/` | Dev environment Terraform composition |
| `docs/local-dev.md` | Developer onboarding guide |

---

## DynamoDB Table: `ebook_platform` (single-table)

| Entity | PK | SK |
|---|---|---|
| Topic config | `TOPIC#<id>` | `META` |
| Topic run | `TOPIC#<id>` | `RUN#<run_id>` |
| Draft | `TOPIC#<id>` | `DRAFT#<run_id>` |
| Published version | `TOPIC#<id>` | `PUBLISHED#<version>` |
| Review | `TOPIC#<id>` | `REVIEW#<run_id>` |
| Feedback item | `TOPIC#<id>` | `FEEDBACK#<feedback_id>` |
| Trace event | `RUN#<run_id>` | `EVENT#<timestamp>#<event_type>` |
| Settings | `SETTINGS` | `BOOK` |
| Notification log | `NOTIF#<recipient>` | `TS#<timestamp>` |

5 GSIs — see `plan.md` for full schema.

---

## Step Functions Pipeline Stages → Workers

```
LoadTopicConfig         → services/workers/topic_loader.py
AssembleTopicContext    → services/workers/topic_context_builder.py
PlanTopic               → services/workers/planner_worker.py
ResearchTopic           → services/workers/research_worker.py
VerifyEvidence          → services/workers/verifier_worker.py
PersistEvidenceArtifacts→ services/workers/artifact_persister.py
DraftChapter            → services/workers/draft_worker.py
EditorialReview         → services/workers/editorial_worker.py
BuildDraftArtifact      → services/workers/draft_builder_worker.py
GenerateDiffReleaseNotes→ services/workers/diff_worker.py
NotifyAdminForReview    → services/workers/approval_worker.py
WaitForApproval         → [Step Functions callback — no Lambda]
PublishTopic            → services/workers/publish_worker.py
RebuildIndexes          → services/workers/search_index_worker.py
```

---

## Agent → Model Routing

| Agent | Model | Reason |
|---|---|---|
| Planner, Verifier, Diff | `gpt-4o-mini` | Structured outputs, lower token volume |
| Research, Writer, Editor | `gpt-4o` | Long context, quality-critical |

---

## Common Dev Commands

```bash
# Local API server
cd services/api && uvicorn local_dev_server:app --reload --port 8000

# Terraform (dev)
cd infra/terraform/envs/dev && terraform init && terraform plan

# Run a single worker in isolation
source .env.local && python services/workers/topic_loader.py --topic-id <id> --run-id <id>

# Step Functions Local (avoid SFN API costs in dev)
docker run -p 8083:8083 amazon/aws-stepfunctions-local

# Jupyter notebook test harness
cd notebooks && jupyter notebook ebook_platform_test_harness.ipynb

# Lint Python
ruff check services/ --fix

# Format Terraform
terraform fmt -recursive infra/
```

---

## Trace Events — Every Stage Must Emit

Every pipeline worker must write three trace event types to DynamoDB:
- `STAGE_STARTED` — at the top of the handler, before any work
- `STAGE_COMPLETED` — on success, with `token_usage` and `cost_usd` from the agent call
- `STAGE_FAILED` — in the exception handler, with `error_message` and `error_classification`

PK: `RUN#<run_id>` | SK: `EVENT#<iso_timestamp>#<event_type>`

---

## S3 Artifact Layout

```
topics/<topic_id>/runs/<run_id>/{raw,extracted,verified,draft,review,diff}/
published/topics/<topic_id>/v001/ v002/ ...
site/current/search/index.json   ← Lunr.js index, rebuilt on every publish
site/current/toc.json
```

---

## Testing Approach

- **No mocking AWS services.** All dev tests hit real AWS resources in the dev account via `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`.
- The Jupyter notebook is the primary integration test. Run cell groups 1-15 for full UC coverage, then run cell group 16 (PURGE) to clean up.
- For unit tests (`pytest`): only pure-logic functions with no AWS/OpenAI calls are mocked. AWS SDK calls must hit real dev resources.

---

## Security Reminders

- Never commit `.env.local`
- Never add OpenAI key as a Lambda environment variable (use Secrets Manager read at runtime)
- All `/admin/*` API routes must have Cognito JWT authorizer — never leave them unprotected
- `moderation_status=PENDING` on all reader-submitted comments
- IAM roles: one per Lambda function, least-privilege

---

## MCP Servers (configured in `.claude/settings.json`)

| Name | Purpose |
|---|---|
| `github` | Create repos, manage PRs/issues, search GitHub code |
| `aws-docs` | Look up AWS service docs (DynamoDB, SFN, EventBridge, etc.) inline |
| `terraform` | Generate and validate Terraform with AWS best practices |

Requires: `GITHUB_TOKEN` env var in shell profile (not `.env.local`).

---

## Milestone Status

| # | Milestone | Status |
|---|---|---|
| 1 | Terraform Infrastructure Foundation | Not started |
| 2 | Topic CRUD API + Admin UI | Not started |
| 3 | Scheduling + Manual Trigger | Not started |
| 4 | Multi-Agent Pipeline | Not started |
| 5 | Admin Review + Approval | Not started |
| 6 | Incremental Publishing | Not started |
| 7 | Public Website | Not started |
| 8 | Run History + Feedback UI | Not started |
| 9 | Weekly Digest | Not started |
| 10 | Jupyter Notebook Test Harness | Not started |

Update this table as milestones are completed.

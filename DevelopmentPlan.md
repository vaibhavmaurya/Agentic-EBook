# Development Plan — Agentic Ebook Platform V3

> This document captures all tooling, workflow, and architectural decisions for development.
> It is the companion to `plan.md` (which captures what to build).
> Last updated: 2026-04-12

---

## 1. Project Summary

A dynamic, per-topic, multi-agent publishing platform that creates and maintains a living ebook on AWS. Content is researched by AI agents, staged for human review, then published incrementally to a public website.

**MVP scope:** topic CRUD → per-topic scheduling → multi-agent pipeline → admin approval → incremental publish → public reading + feedback → weekly digest → full Terraform deployment.

**Detailed plan:** see `plan.md`

---

## 2. Technology Stack Decisions

### 2.1 Backend — Python 3.12

**Why Python:**
- OpenAI SDK has first-class Python support (`openai` package)
- `boto3` (AWS SDK) is most mature in Python
- All Lambda workers are CPU/IO-bound agent tasks — Python runtime cost is negligible
- Consistent language across all backend services avoids context switching

**Key libraries:**

| Library | Purpose |
|---|---|
| `openai` | OpenAI Responses API (isolated to `openai_runtime` module only) |
| `boto3` | AWS SDK: DynamoDB, S3, Step Functions, EventBridge, SES, Secrets Manager |
| `pydantic` | Request/response validation in Lambda handlers |
| `python-dotenv` | Load `.env.local` in local dev |
| `aws-lambda-powertools` | Structured logging, tracing, event parsing, response utilities |
| `fastapi` + `uvicorn` | Local dev API server (wraps same Lambda handlers) |
| `pytest` | Unit and integration tests |
| `ruff` | Linting and formatting |

### 2.2 Frontend — TypeScript

**Admin UI:** React 18 + Vite + React Router + TanStack Query + shadcn/ui

**Public Site:** Astro 4 with static output — deployed once as a static shell; all content fetched from the public API at runtime

**Why Astro for public site:**
- Minimal JavaScript by default — fast reader experience
- Static shell deployed to Amplify CDN; content loaded from API on page load
- No site rebuild required when topics are published — new content appears immediately
- SEO note: topic content is client-rendered (acceptable for MVP; SSR can be added in Phase 2 if needed)

### 2.3 AI Runtime — OpenAI Responses API

**Why not Bedrock:** specification constraint — OpenAI models required.

**Provider isolation:** the `services/openai-runtime/` module is the only code that imports the `openai` package. All other modules call stable internal functions (`run_planner_agent()` etc.). Swapping to a different provider in the future requires changing only this module.

**Model routing:**
- `gpt-4o` — Research Agent, Chapter Writer, Editorial Reviewer (long context, quality-critical)
- `gpt-4o-mini` — Topic Planner, Evidence Verifier, Diff Agent (structured outputs, lower cost)

**Structured outputs:** every agent returns a Pydantic model serialized to JSON. Step Functions passes this as the stage output, providing a verifiable contract between pipeline stages.

### 2.4 Infrastructure — AWS Serverless + Terraform

**No always-on servers in MVP.** Cost drivers: OpenAI usage, Lambda duration, DynamoDB reads/writes, Amplify hosting.

**Terraform-first:** all AWS primitives provisioned by Terraform. Per-topic EventBridge Scheduler entries created dynamically at runtime by the API (not Terraform) because they change frequently.

**Environments:** `dev` (low-cost, manual triggers, short retention) and `prod` (alarms enabled, PITR on DynamoDB, production retention).

### 2.5 Search — Lunr.js (MVP)

Client-side keyword search over a pre-built JSON index. The `search_index_worker.py` regenerates this index on every topic publish. Zero backend cost. Phase 2 will add OpenSearch Serverless for semantic retrieval.

---

## 3. MCP Servers Configured for This Project

MCP (Model Context Protocol) servers extend Claude Code with tools that make it significantly more productive. The following servers are configured in `.claude/settings.json` at the project root.

### 3.1 GitHub MCP — `@modelcontextprotocol/server-github`

**What it adds:** Claude can create/manage GitHub repositories, open and review pull requests, create issues, search code, and manage branches directly — without you switching to the browser or running git commands manually.

**Why it matters for this project:**
- Initialize and manage the `ebook-platform` GitHub repo
- Create PRs per milestone automatically during implementation
- Track issues for bugs and deferred Phase 2 items
- Search existing GitHub code for patterns (e.g. Lambda handler patterns, Terraform module examples)

**Setup requirement:** set `GITHUB_TOKEN` environment variable to a GitHub Personal Access Token with `repo` scope.

**Configuration:**
```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
}
```

### 3.2 AWS Documentation MCP — `awslabs.aws-documentation-mcp-server`

**What it adds:** Claude can look up official AWS service documentation, API references, and best-practice guides at any point during implementation — without leaving the editor or performing web searches.

**Why it matters for this project:**
- DynamoDB single-table design patterns and GSI limits
- Step Functions ASL (Amazon States Language) syntax for the pipeline state machine
- EventBridge Scheduler API for dynamic per-topic schedule management
- API Gateway HTTP API JWT authorizer configuration
- SES email sending best practices
- S3 lifecycle rule configuration for artifact retention

**Configuration:**
```json
"aws-docs": {
  "command": "uvx",
  "args": ["awslabs.aws-documentation-mcp-server@latest"],
  "env": { "FASTMCP_LOG_LEVEL": "ERROR" }
}
```

### 3.3 Terraform MCP — `awslabs.terraform-mcp-server`

**What it adds:** Claude can generate, validate, and review Terraform configurations using AWS provider best practices, including module structure, IAM policy generation, and resource dependency resolution.

**Why it matters for this project:**
- Generates correct `aws_dynamodb_table` resource with GSIs and PITR
- Validates Step Functions IAM trust policies and execution roles
- Suggests least-privilege IAM policies for each Lambda function
- Ensures Terraform module structure follows best practices
- Catches common Terraform anti-patterns before `terraform plan`

**Configuration:**
```json
"terraform": {
  "command": "uvx",
  "args": ["awslabs.terraform-mcp-server@latest"],
  "env": { "FASTMCP_LOG_LEVEL": "ERROR" }
}
```

### Installing MCP Servers

```bash
# GitHub MCP (requires Node.js)
npm install -g @modelcontextprotocol/server-github

# AWS Documentation MCP + Terraform MCP (requires uv)
pip install uv
uvx awslabs.aws-documentation-mcp-server@latest  # first run downloads it
uvx awslabs.terraform-mcp-server@latest           # first run downloads it
```

Set the `GITHUB_TOKEN` environment variable in your shell profile (not in `.env.local`).

---

## 4. Claude Code Skills in Use

Claude Code skills provide specialized workflows. The following are relevant to this project:

### 4.1 `simplify`

**Trigger:** `/simplify` after completing each milestone's implementation.

**What it does:** reviews recently changed code for reuse opportunities, redundancy, and efficiency issues, then fixes what it finds.

**When to use:**
- After each milestone is implemented — before moving to the next milestone
- Before creating a PR for a milestone
- After refactoring a module

### 4.2 `update-config`

**Trigger:** `/update-config`

**What it does:** configures Claude Code behaviors via `settings.json` — adds hooks, updates MCP server config, sets automated behaviors.

**When to use:**
- Adding new hooks (e.g. auto-run `terraform fmt` after editing `.tf` files)
- Updating the MCP server list as new tools are needed
- Configuring pre-commit-style behaviors

### 4.3 `schedule`

**Trigger:** `/schedule`

**What it does:** creates recurring remote agents that run on a cron schedule.

**When to use:**
- Set up a recurring "check for failed Step Functions executions in dev" agent
- Schedule periodic `terraform plan` diff reports against the dev environment

---

## 5. Recommended Hooks

Hooks run shell commands automatically in response to Claude Code events. The following are configured in `.claude/settings.json`:

### 5.1 Terraform Format on Save

Automatically runs `terraform fmt` whenever a `.tf` file is written or edited.

```json
{
  "type": "command",
  "command": "powershell -Command \"if ('${CLAUDE_TOOL_INPUT_file_path}' -match '\\.tf$') { terraform fmt '${CLAUDE_TOOL_INPUT_file_path}' }\""
}
```

### 5.2 Python Lint on Save

Runs `ruff check` on edited Python files to surface issues immediately.

```json
{
  "type": "command",
  "command": "powershell -Command \"if ('${CLAUDE_TOOL_INPUT_file_path}' -match '\\.py$') { ruff check '${CLAUDE_TOOL_INPUT_file_path}' --fix }\""
}
```

---

## 6. Development Workflow

### 6.1 Per-Milestone Workflow

```
1. Read the milestone section in plan.md
2. Use Claude Code to implement (Edit/Write tools)
3. Run the relevant notebook cell groups against the dev AWS account to verify
4. Run /simplify to review code quality
5. Commit milestone with descriptive message
6. Update plan.md to mark milestone complete and note any deviations
```

### 6.2 Local Dev Cycle

```bash
# Terminal 1 — local API server
cd services/api
source ../../.env.local   # or use direnv
uvicorn local_dev_server:app --reload --port 8000

# Terminal 2 — optional Step Functions Local
docker run -p 8083:8083 amazon/aws-stepfunctions-local

# Terminal 3 — run notebook or individual worker scripts
jupyter notebook notebooks/ebook_platform_test_harness.ipynb
```

### 6.3 Terraform Workflow

```bash
cd infra/terraform/envs/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# After infrastructure changes, re-run affected notebook cell groups
```

### 6.4 Adding a New Worker

1. Create `services/workers/<name>_worker.py` with handler function
2. Add Lambda function to `infra/terraform/modules/lambda_functions/main.tf`
3. Add state to Step Functions ASL in `infra/terraform/modules/step_functions/asl.json`
4. Add trace event emission at start/complete/fail in the worker
5. Add verification assertion in the relevant notebook cell group

---

## 7. Directory Responsibilities

| Directory | Language | Purpose |
|---|---|---|
| `apps/public-site/` | TypeScript (Astro) | Static public ebook site |
| `apps/admin-site/` | TypeScript (React) | Admin management console SPA |
| `services/api/` | Python | Lambda handlers for all REST endpoints |
| `services/workers/` | Python | Step Functions task Lambdas (one per pipeline stage) |
| `services/openai-runtime/` | Python | **Only** module that imports OpenAI SDK |
| `services/content-build/` | Python | Search index builder, TOC/sitemap generator |
| `infra/terraform/modules/` | HCL | Reusable Terraform modules per AWS resource group |
| `infra/terraform/envs/dev/` | HCL | Dev environment composition |
| `infra/terraform/envs/prod/` | HCL | Prod environment composition |
| `packages/shared-types/` | Python + TS | Shared Pydantic models and TypeScript types |
| `packages/prompt-policies/` | Markdown | Style guides, agent instruction fragments |
| `notebooks/` | Python (Jupyter) | API test harness with UC-01→UC-15 + purge |
| `docs/` | Markdown | Developer guides |

---

## 8. Environment Variables Reference

See `.env.local.example` for the full list. Key variables:

| Variable | Used By | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | All Lambda/workers locally | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | All Lambda/workers locally | AWS credentials |
| `AWS_REGION` | All | Target AWS region |
| `DYNAMODB_TABLE_NAME` | API, workers | DynamoDB table name |
| `S3_ARTIFACT_BUCKET` | API, workers | Artifact S3 bucket name |
| `STEP_FUNCTIONS_ARN` | API trigger handler | Step Functions state machine ARN |
| `STEP_FUNCTIONS_ENDPOINT` | Workers (local dev) | `http://localhost:8083` for local SF emulator |
| `COGNITO_USER_POOL_ID` | Admin UI | For local Cognito auth testing |
| `COGNITO_CLIENT_ID` | Admin UI | For local Cognito auth testing |
| `SES_SENDER_EMAIL` | `digest_worker.py` | Verified SES sender address |
| `OPENAI_SECRET_NAME` | `openai_runtime` | Secrets Manager secret name for OpenAI key |
| `ADMIN_API_BASE_URL` | Notebook | Base URL for admin API calls |
| `PUBLIC_API_BASE_URL` | Notebook | Base URL for public API calls |
| `ADMIN_USERNAME` | Notebook | Dev Cognito admin username |
| `ADMIN_PASSWORD` | Notebook | Dev Cognito admin password |
| `OWNER_EMAIL` | `digest_worker.py` | Digest recipient email |

---

## 9. Cost Management

**Primary cost drivers in MVP:**
1. OpenAI token usage (largest cost — gpt-4o for research/writing)
2. Step Functions executions (Standard workflow pricing per state transition)
3. Lambda duration
4. DynamoDB reads/writes (trace events are write-heavy)
5. S3 storage and requests

**Cost control levers:**
- Dev environment: use `manual` trigger only; no recurring schedules during development
- Cap `max_search_results` per Research Agent run in dev config
- Route expensive steps to `gpt-4o-mini` where quality allows
- Set DynamoDB TTL on transient records (callback state, ephemeral notifications)
- Use `STEP_FUNCTIONS_ENDPOINT=http://localhost:8083` in dev to avoid Step Functions API costs during pipeline iteration

---

## 10. Security Checklist

- [ ] No AWS credentials committed to source code or `.env.local` checked in
- [ ] OpenAI API key stored only in AWS Secrets Manager — never in env vars of deployed Lambdas (use Secrets Manager SDK call)
- [ ] All admin API routes protected by Cognito JWT authorizer
- [ ] S3 buckets have `BlockPublicAccess` enabled; public content served via Amplify CDN only
- [ ] Least-privilege IAM role per Lambda (no wildcard `*` actions in prod)
- [ ] Rate limiting enabled on `/public/comments` and `/public/highlights` endpoints
- [ ] Input validation (max length, character set) on all reader-submitted fields
- [ ] `moderation_status=PENDING` on all submitted comments — admin review required before surfacing in feedback analytics

---

## 11. Milestone Status

| # | Milestone | Status | Notes |
|---|---|---|---|
| 1 | Infrastructure Foundation | ✅ Complete | 83 AWS resources deployed via Terraform |
| 2 | Topic CRUD API + Admin UI | ✅ Complete | CRUD, reorder, soft-delete, drag-and-drop |
| 3 | Scheduling + Manual Trigger | ✅ Complete | EventBridge per-topic schedules, manual trigger |
| 4 | Multi-Agent Pipeline | ✅ Complete | 11 workers, openai_runtime adapter, full SFN ASL |
| 5 | Admin Review + Approval | ✅ Complete | SFN callback token, approve/reject, timeout handling |
| 6 | Incremental Publishing | ✅ Complete | Version incrementing, S3 promotion, DDB PUBLISHED# items |
| 7 | Public Website | ✅ Complete | Runtime API fetching — no rebuild on publish. URL: https://dev.djcvgu9ysuar.amplifyapp.com |
| 8 | Run History + Feedback UI | ✅ Complete | Run history, trace timeline, cost bars, feedback list |
| 9 | Weekly Digest | ✅ Complete | SES HTML digest, EventBridge Monday 08:00 UTC schedule |
| 10 | Local Dev + Notebook Test Harness | ✅ Complete | UC-01→UC-15 + PURGE cell, full assertion coverage |

> Last updated: 2026-04-12. All milestones complete. API: https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com

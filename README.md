# Agentic Ebook Platform V3

An AI-powered publishing platform where autonomous agents research, draft, and stage
web-based ebook content on a per-topic basis. A human administrator reviews every draft
before it is published — no AI content goes live without approval.

The platform runs entirely on AWS and is managed through two web interfaces: an admin
console for content management, and a public reader-facing ebook website.

---

## How It Works

```
Admin creates a topic
        │
        ▼
Scheduled or manual trigger
        │
        ▼
AI pipeline runs (Step Functions)
  ├── Planner    — designs the research strategy
  ├── Researcher — searches the web, collects evidence
  ├── Verifier   — checks source quality and accuracy
  ├── Writer     — drafts the chapter
  ├── Editor     — refines and scores the draft
  └── Diff       — compares to prior published version
        │
        ▼
Admin receives email → reviews staged draft → Approve or Reject
        │ (approve)
        ▼
Chapter published to public ebook site
        │
        ▼
Readers browse, search, highlight, and comment
```

---

## Live URLs (Dev Environment)

| Interface | URL |
|---|---|
| Admin Console | https://dev.d200xw9mmlu4wj.amplifyapp.com |
| Public Ebook Site | https://dev.djcvgu9ysuar.amplifyapp.com |
| API Base URL | https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com |

---

## Documentation

Start here depending on what you want to do:

| Document | When to read it |
|---|---|
| [Local Development Guide](docs/guide-local-development.md) | Setting up and running the app on your own machine |
| [AWS Deployment Guide](docs/guide-aws-deployment.md) | Deploying the app to AWS from scratch |
| [API Reference (Swagger)](http://localhost:8000/docs) | Interactive API explorer — start the local server first |
| [Deployment Operations](docs/deployment.md) | Deploy scripts reference, verification commands, troubleshooting |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Admin UI | React 19 + Vite + TypeScript |
| Public Site | Astro (static export) |
| Authentication | Amazon Cognito |
| API | API Gateway HTTP API + Lambda (Python 3.12) |
| AI Pipeline | AWS Step Functions + 14 Lambda workers |
| AI Agents | OpenAI API — gpt-4o (research/write/edit), gpt-4o-mini (plan/verify/diff) |
| Metadata store | Amazon DynamoDB (single-table design) |
| Artifact store | Amazon S3 |
| Scheduling | Amazon EventBridge Scheduler |
| Email | Amazon SES |
| Secrets | AWS Secrets Manager |
| Hosting | AWS Amplify |
| Infrastructure | Terraform 1.7+ |

---

## Repository Structure

```
Agentic-EBook/
├── apps/
│   ├── admin-site/         React + Vite admin console (port 3000 locally)
│   └── public-site/        Astro reader-facing ebook website (port 4321 locally)
│
├── services/
│   ├── api/                Lambda handlers — topics, reviews, feedback, public routes
│   │   └── local_dev_server.py   FastAPI wrapper for local development
│   ├── workers/            14 Step Functions Lambda workers (one per pipeline stage)
│   ├── openai_runtime/     OpenAI SDK adapter — the ONLY place openai is imported
│   └── content-build/      Search index and TOC builder
│
├── packages/
│   ├── shared-types/       Pydantic models, DynamoDB helpers, trace event writer
│   └── prompt-policies/    Agent style guides and prompt fragments
│
├── infra/
│   └── terraform/
│       ├── modules/        13 Terraform modules (one per AWS resource group)
│       └── envs/dev/       Dev environment composition
│
├── notebooks/
│   └── ebook_platform_test_harness.ipynb   End-to-end tests UC-01 → UC-15
│
├── scripts/
│   ├── deploy_api.sh       Package and deploy the API Lambda
│   ├── deploy_workers.sh   Package and deploy worker Lambdas
│   ├── deploy_frontend.sh  Build and deploy Amplify frontends
│   └── zipdir.py           Cross-platform zip utility used by deploy scripts
│
└── docs/
    ├── guide-local-development.md   Step-by-step local setup guide
    ├── guide-aws-deployment.md      Step-by-step AWS deployment guide
    └── deployment.md               Deploy script reference and troubleshooting
```

---

## Quick Start

### Run Locally

See the full [Local Development Guide](docs/guide-local-development.md). The short version:

```bash
# 1. Clone
git clone https://github.com/vaibhavmaurya/Agentic-EBook.git
cd Agentic-EBook

# 2. Configure credentials
cp .env.local.example .env.local
# Fill in AWS credentials and resource names in .env.local

# 3. Provision AWS infrastructure (one time)
cd infra/terraform/envs/dev && terraform init && terraform apply
cd ../../../..

# 4. Install Python dependencies
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on Mac/Linux
pip install -r services/api/requirements.txt
pip install -e packages/shared-types

# 5. Start all three servers (each in its own terminal)
cd services/api && uvicorn local_dev_server:app --reload --port 8000  # API
cd apps/admin-site && npm install && npm run dev                        # Admin UI
cd apps/public-site && npm install && npm run dev                       # Public site
```

| Service | URL |
|---|---|
| API + Swagger UI | http://localhost:8000/docs |
| Admin Console | http://localhost:3000 |
| Public Ebook Site | http://localhost:4321 |

### Deploy to AWS

See the full [AWS Deployment Guide](docs/guide-aws-deployment.md). The short version:

```bash
# Load environment variables
export $(cat .env.local | grep -v '#' | grep -v '^$' | xargs)

# Deploy in sequence
bash scripts/deploy_api.sh           # API Lambda
bash scripts/deploy_workers.sh       # All 14 pipeline workers
bash scripts/deploy_frontend.sh      # Admin UI + Public Site to Amplify
```

---

## Pipeline Stages and Workers

Each Stage is a separate Lambda function invoked by AWS Step Functions:

| Stage | Worker | AI? | What it does |
|---|---|---|---|
| LoadTopicConfig | `topic_loader.py` | | Reads topic config from DynamoDB |
| AssembleTopicContext | `topic_context_builder.py` | | Builds the research context payload |
| PlanTopic | `planner_worker.py` | gpt-4o-mini | Designs the research plan |
| ResearchTopic | `research_worker.py` | gpt-4o | Web search and evidence collection |
| VerifyEvidence | `verifier_worker.py` | gpt-4o-mini | Validates source quality |
| PersistEvidenceArtifacts | `artifact_persister.py` | | Writes research to S3 |
| DraftChapter | `draft_worker.py` | gpt-4o | Writes the chapter |
| EditorialReview | `editorial_worker.py` | gpt-4o | Edits and scores the draft |
| BuildDraftArtifact | `draft_builder_worker.py` | | Stages HTML/JSON to S3 |
| GenerateDiffReleaseNotes | `diff_worker.py` | gpt-4o-mini | Diffs against prior version |
| NotifyAdminForReview | `approval_worker.py` | | Sends email, stores callback token |
| WaitForApproval | *(Step Functions wait state)* | | Pipeline pauses here |
| PublishTopic | `publish_worker.py` | | Promotes artifacts to published/ in S3 |
| RebuildIndexes | `search_index_worker.py` | | Rebuilds Lunr.js search index and TOC |

A 15th Lambda (`digest_worker.py`) runs on a weekly EventBridge schedule to email the
owner a summary of newly published topics.

---

## API Overview

All admin routes require a **Cognito JWT Bearer token**. Public routes need no auth.

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/admin/topics` | Required | List all topics |
| POST | `/admin/topics` | Required | Create a topic |
| GET | `/admin/topics/{id}` | Required | Get a topic |
| PUT | `/admin/topics/{id}` | Required | Update a topic |
| DELETE | `/admin/topics/{id}` | Required | Soft-delete a topic |
| PUT | `/admin/topics/reorder` | Required | Reorder topics |
| POST | `/admin/topics/{id}/trigger` | Required | Trigger the AI pipeline |
| GET | `/admin/topics/{id}/runs` | Required | List pipeline runs |
| GET | `/admin/topics/{id}/runs/{runId}` | Required | Run detail + trace events |
| GET | `/admin/reviews` | Required | All pending review queue |
| GET | `/admin/topics/{id}/review/{runId}` | Required | Get draft for review |
| POST | `/admin/topics/{id}/review/{runId}` | Required | Approve or reject draft |
| GET | `/admin/feedback/summary` | Required | Feedback across all topics |
| GET | `/admin/topics/{id}/feedback` | Required | Feedback for one topic |
| POST | `/public/comments` | None | Submit a reader comment |
| POST | `/public/highlights` | None | Submit a text highlight |
| GET | `/public/releases/latest` | None | Recently published topics |

Full interactive docs with request/response schemas: run the API server and open
[http://localhost:8000/docs](http://localhost:8000/docs).

---

## Key Design Decisions

**Only `services/openai_runtime/` imports the OpenAI SDK.** All other modules call
the functions exposed by that module's `__init__.py`. This keeps the AI dependency
isolated and replaceable.

**No content is published without human approval.** The Step Functions pipeline always
pauses at `WaitForApproval` using a callback token pattern. Approval via the API
explicitly resumes the execution.

**No AWS credentials in source code.** All config is read from environment variables
at runtime. Lambda functions read from their environment; the local dev server reads
from `.env.local` via python-dotenv. `.env.local` is gitignored.

**Per-topic EventBridge schedules are created at runtime by the API**, not by Terraform.
Terraform only provisions the schedule group. This keeps infrastructure minimal and
lets admins change topic schedules without a Terraform apply.

**All dev tests hit real AWS resources.** There is no mocking of DynamoDB, S3, or
Step Functions. The Jupyter notebook test harness (`notebooks/`) is the primary
integration test suite.

---

## Milestone Status

| # | Milestone | Status |
|---|---|---|
| 1 | Terraform Infrastructure Foundation | Complete |
| 2 | Topic CRUD API + Admin UI | Complete |
| 3 | Scheduling + Manual Trigger | Complete |
| 4 | Multi-Agent Pipeline | Complete |
| 5 | Admin Review + Approval | Complete |
| 6 | Incremental Publishing | Complete |
| 7 | Public Website | Complete |
| 8 | Run History + Feedback UI | Complete |
| 9 | Weekly Digest | Complete |
| 10 | Jupyter Notebook Test Harness | Complete |

# SOP 01 — Project Setup & Bootstrapping

## Purpose

Get a new project started correctly from day one. The decisions made in the first session compound across every subsequent session. A poor setup means every future session spends time reconstructing context, fixing structural issues, or working around early mistakes.

---

## The Three-Document System

Every project needs three living documents working together. Create all three before writing any code.

### `plan.md` — What to Build

The living specification. Contains:
- Context and goal of the project
- Hard constraints (non-negotiable technical and business rules)
- Technology stack with rationale for each choice
- Full milestone breakdown with deliverables per milestone
- Data schema (DynamoDB, S3 layout, API endpoints)
- Verification checklist per milestone

**Rule:** Every scope or sequencing change must be reflected in `plan.md` before implementation begins. `plan.md` is the source of truth for what the system is supposed to do.

### `action-item.md` — Where to Resume

The session resume tracker. Contains:
- A `RESUME HERE` section at the top — always the next concrete action
- Granular step checklists per milestone (each step independently completable)
- A session log table (date, what was done)
- Milestone status table (mirrors the one in `CLAUDE.md`)

**Rule:** Read this at the start of every session. Update it at the end. If you don't, the next session will spend 20-30 minutes reconstructing where you are.

**What makes a good step entry:**
```
- [x] M3-S2: Create services/workers/base.py — shared DynamoDB/S3/SFN helpers
- [ ] M3-S3: Deploy topic_loader.py to Lambda, verify trigger → SFN execution visible in console
```
Each step should be: milestone-prefixed, file-specific, and outcome-verified (not just "write the code" but "write + deploy + verify").

### `CLAUDE.md` — Project Rules for Claude Code

The instruction file read automatically by Claude Code at the start of every session. Contains:
- Non-negotiable rules (explicit, with "Never" and "Always" language)
- Architecture summary in one paragraph
- Key file locations table
- Common dev commands
- Milestone status table

**Rule:** CLAUDE.md rules must use strong language. "Prefer to avoid" is ignored. "Never add `import openai` outside of `openai_runtime/`" is enforced. Write rules that would catch a mistake by a developer who hasn't read the full plan.

---

## Repository Structure

Use a monorepo layout with clear directory responsibilities. Never mix concerns across directories.

```
project-root/
  apps/           ← Frontend applications (public site, admin SPA)
  services/       ← Backend Lambda handlers and workers
  infra/          ← Terraform modules and environment compositions
  packages/       ← Shared code (types, utilities, prompts)
  notebooks/      ← Integration test harness
  docs/           ← Developer guides and SOPs
  .env.local.example  ← Credential template (committed, no secrets)
  .env.local          ← Actual secrets (gitignored)
```

**The `packages/` directory is for code shared across multiple services.** If something is only used in one service, keep it in that service. Don't create packages prematurely.

---

## Credential Pattern

**Never commit credentials. Ever.**

Template pattern:
1. Create `.env.local.example` with all variable names, placeholder values, and comments
2. Add `.env.local` to `.gitignore`
3. Developer copies `.example` to `.env.local` and fills in real values
4. All Lambda handlers and workers read config from environment variables only
5. Deployed secrets (API keys) go in AWS Secrets Manager — fetched at runtime, never as Lambda environment variables

```bash
# .env.local.example
AWS_ACCESS_KEY_ID=REPLACE_ME
AWS_SECRET_ACCESS_KEY=REPLACE_ME
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=ebook-platform-dev
S3_ARTIFACT_BUCKET=ebook-platform-artifacts-dev
OPENAI_SECRET_NAME=ebook-platform/openai-key   # Secrets Manager name, not the key itself
```

---

## MCP Servers — Configure Before Coding

MCP servers give Claude Code access to external systems and documentation. Set them up in `.claude/settings.json` at the start of the project, not mid-way.

**For AWS + Terraform projects, configure these three:**

### GitHub MCP
```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
}
```
Set `GITHUB_TOKEN` in your shell profile, not in `.env.local`.

### AWS Documentation MCP
```json
"aws-docs": {
  "command": "uvx",
  "args": ["awslabs.aws-documentation-mcp-server@latest"],
  "env": { "FASTMCP_LOG_LEVEL": "ERROR" }
}
```

### Terraform MCP
```json
"terraform": {
  "command": "uvx",
  "args": ["awslabs.terraform-mcp-server@latest"],
  "env": { "FASTMCP_LOG_LEVEL": "ERROR" }
}
```

---

## Technology Stack Decision Checklist

Before choosing a technology, answer these questions:

1. **Is there a simpler option that meets the requirement?** Start simple. Add complexity only when there's a proven need (e.g. Lunr.js before OpenSearch, Lambda before containers).
2. **Does the team/Claude have strong support for this choice?** Python for AWS Lambda + OpenAI: yes. Go for Lambda: possible but less tooling.
3. **What is the blast radius if this choice is wrong?** Choose technologies where the wrong choice is reversible (e.g. isolate the AI provider so you can swap models).
4. **Is this driven by a hard constraint or a preference?** Document the reason. Future sessions will question the choice without context.

**Document every technology choice with a rationale.** Use a table in `plan.md`:

```
| Layer        | Technology         | Rationale                                           |
| Public site  | Astro (static)     | Minimal JS, CDN-friendly, no rebuild on content pub |
| Auth         | Amazon Cognito     | Native JWT integration with API Gateway             |
```

---

## Milestone Structure Best Practice

**Milestones should be end-to-end slices, not layer slices.**

Wrong: "Milestone 1: All backend. Milestone 2: All frontend."
Right: "Milestone 1: Topic CRUD — backend + admin UI + verified end-to-end."

Each milestone should:
- Have a clear deliverable (not "code written" but "trigger → DDB record visible in console")
- Have an acceptance criteria checklist
- Be independently deployable and verifiable

**The milestone order should reflect dependency:** you cannot test the pipeline without infrastructure, cannot test approval without the pipeline, etc. Plan in dependency order, not feature order.

---

## First Session Checklist

```
[ ] Create plan.md with full milestone breakdown
[ ] Create action-item.md with M1-S1 as the first step
[ ] Create CLAUDE.md with non-negotiable rules and key file locations
[ ] Create .env.local.example with all expected variables
[ ] Add .env.local to .gitignore
[ ] Configure .claude/settings.json with MCP servers
[ ] Initialize git repository and push to GitHub
[ ] Document the technology stack decisions
[ ] Write the repository structure
```

If you don't do these in session 1, you will do them mid-project under pressure. Mid-project is the worst time to establish structure.

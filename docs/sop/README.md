# Standard Operating Procedures — Agentic Ebook Platform

This folder is a working knowledge base built from the complete development experience of the Agentic Ebook Platform V3. It captures decisions, patterns, pitfalls, and best practices so that future projects make fewer mistakes and move faster.

---

## How to Use This SOP

- **Starting a new project:** Read `01-project-setup.md` first. It sets the foundation.
- **Designing AWS architecture:** Read `02-aws-architecture.md` before touching Terraform.
- **Writing Terraform:** Read `03-terraform.md` before writing a single `.tf` file.
- **Building an AI pipeline:** Read `04-multi-agent-pipeline.md` before designing agent roles.
- **Building a frontend:** Read `05-frontend.md` before choosing a rendering strategy.
- **Setting up testing:** Read `06-testing.md` before writing any test or deploy script.
- **Security review:** Read `07-security.md` before any deployment.
- **Working with Claude Code across sessions:** Read `08-session-workflow.md` at the start of every new engagement.

---

## The 6 Non-Negotiable Rules

These rules were hard-won from this project. Violating any of them caused real bugs or production incidents.

1. **Only one module may import the AI provider SDK.** All other modules call stable internal functions. Swapping providers = changing one file.

2. **No content may be published without explicit human approval.** The Step Functions callback token pattern is the gate. Never shortcut it.

3. **No credentials in source code.** `.env.local` is gitignored. Secrets Manager for deployed secrets. Never Lambda environment variables for API keys.

4. **Terraform provisions platform primitives only.** Anything that changes at runtime (per-topic schedules, dynamic resources) is created by the application at runtime — not Terraform.

5. **Test locally against real AWS resources before committing.** No mocking. No "it should work." Real HTTP calls, real DynamoDB, real S3.

6. **Update session tracker at the end of every session.** The `action-item.md` RESUME HERE section must reflect exactly where to pick up. If it doesn't, the next session wastes time reconstructing state.

---

## Document Index

| File | Topic |
|---|---|
| `01-project-setup.md` | Bootstrapping a new project — structure, documentation, credentials |
| `02-aws-architecture.md` | AWS service selection, IAM patterns, common pitfalls |
| `03-terraform.md` | IaC best practices, module structure, runtime boundaries |
| `04-multi-agent-pipeline.md` | Agent design, provider isolation, tracing, human-in-the-loop |
| `05-frontend.md` | Astro static shell, React admin SPA, rendering strategy decisions |
| `06-testing.md` | Local dev cycle, integration testing, deployment workflow |
| `07-security.md` | Non-negotiable security controls and verification checklist |
| `08-session-workflow.md` | Multi-session development with Claude Code |

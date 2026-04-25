# SOP 08 — Multi-Session Development with Claude Code

## Purpose

Long-horizon software projects (10+ milestones, multiple sessions) require deliberate session management. Without it, each new session wastes 20-40 minutes reconstructing context, re-reading files, and rediscovering decisions made earlier. This SOP defines the workflow that kept this project coherent across all 10 milestones completed in multiple sessions.

---

## The Core Problem

Claude Code starts each session with no memory of previous sessions. The only context it has is:
1. What you explicitly provide in the session prompt
2. What it can read from the codebase
3. What is written in `CLAUDE.md` (auto-loaded)

If your session tracker (`action-item.md`) is stale, Claude will either:
- Ask you to summarize what was done (slow), or
- Make wrong assumptions about the current state (dangerous)

**The investment:** 5 minutes updating `action-item.md` at the end of a session saves 30 minutes at the start of the next.

---

## The Three-Document System (Recap)

| Document | Read frequency | Update frequency | Purpose |
|---|---|---|---|
| `CLAUDE.md` | Every session (auto-loaded) | Rarely (rules don't change) | Non-negotiable rules, architecture summary, key locations |
| `action-item.md` | Every session start | Every session end | Exact resume point, granular step checklists |
| `plan.md` | When scope changes | When milestones complete or pivot | What to build — milestones, schema, endpoints |

Do not conflate these documents. Each has a specific role.

---

## Session Start Ritual

Do this at the very start of every session, before writing any code:

1. **Read `action-item.md`** — find the RESUME HERE section. This tells you exactly where to start.
2. **Verify the current state** — read the files mentioned in the current step to confirm they exist and match what the session log says.
3. **If the state is unexpected** — investigate before proceeding. Don't assume the code is in the state the log says.
4. **Identify the milestone and step** — know which milestone you're in (e.g. M5-S3) before touching any code.

### Starting a Fresh Context on an Existing Codebase

If you need to re-establish full context (e.g. after a long break or on a new machine):

```
1. Read CLAUDE.md (loaded automatically)
2. Read action-item.md (RESUME HERE section)
3. Read plan.md (milestone table and current milestone section)
4. Read 2-3 key files mentioned in the current step
5. Then begin work
```

Do not read every file in the project. Trust the documents that were written to guide exactly this situation.

---

## Session End Ritual

Do this before closing the session, even if you're mid-task:

### 1. Update `action-item.md` RESUME HERE Section

```markdown
## ▶ RESUME HERE

**Session ended:** 2026-04-12
**Last completed:** [Exactly what was the last thing you finished and verified]

**Next action:** [One specific, concrete action — file to create, command to run, test to verify]
```

The "Next action" must be specific enough that you could hand it to someone unfamiliar with the project and they could execute it. "Continue M5" is bad. "Deploy the updated `approval_worker.py` to Lambda and run notebook cell 7 to verify approval flow" is good.

### 2. Check Off Completed Steps

Mark every completed step in the milestone checklist with `[x]`. Leave incomplete steps as `[ ]`.

### 3. Update Milestone Status Tables

Update the table in `action-item.md` AND the one in `CLAUDE.md`. They should always match.

### 4. Add a Session Log Row

```markdown
| 2026-04-12 | Bug fixes: approval_worker KeyError, API Lambda IAM (SendTaskSuccess/Failure), worker Amplify IAM, config_api path fix. Architecture change: public site switched to runtime API fetching. Deployed public site (Amplify job 16). |
```

Be specific about bugs fixed and architectural changes. Vague entries ("general improvements") are useless for the next session.

### 5. Commit and Push

```bash
git add -A
git commit -m "Update action-item.md: M5 complete, M6 ready to start. Bug fixes: [list]"
git push
```

**Never leave the session without committing `action-item.md`.** This is the most important artifact to keep current.

---

## Granular Step Writing

The quality of steps in `action-item.md` determines how efficiently the next session runs.

### Bad Step (Too Vague)
```
- [ ] Implement the approval flow
```

### Good Step (Specific and Verifiable)
```
- [ ] M5-S2: Create GET /admin/topics/{topicId}/review/{runId} handler in topics.py
      — Returns: review_status, draft_artifact_uri, diff_summary_uri, task_token_stored (bool)
      — Verify: curl with valid JWT + run_id → 200 with review JSON
```

Each step should have:
- **Milestone prefix** (M5-S2) — for tracking position
- **Specific file and action** — not "implement" but "create in X file"
- **Expected output** — what the result should look like
- **Verification method** — how to confirm it's done

---

## CLAUDE.md Rules That Actually Work

Rules in `CLAUDE.md` are only as effective as they are explicit. Claude Code applies these rules, but vague rules are interpreted loosely.

### Rules That Work

```markdown
1. **Only `services/openai-runtime/` may import the `openai` package.** Never add
   `import openai` or `from openai import ...` anywhere else.

2. **No AWS credentials in source code.** All config via environment variables.
   `.env.local` is gitignored.

3. **After implementing any backend module or UI component, test it locally before
   committing.** For backend: start the API server and make real HTTP calls. For UI:
   run `npm run build` (0 errors required).
```

### Rules That Don't Work

```markdown
- Try to keep things organized
- Be careful with credentials
- Test before committing (when possible)
```

Use "Never", "Always", "Must", "Only". Soft language creates wiggle room that leads to mistakes.

---

## Managing Scope Changes Mid-Project

Projects change. When scope or sequencing changes:

1. **Update `plan.md` immediately** — add a note with the date and what changed
2. **Update `action-item.md`** — reflect the new next steps
3. **Add a row to the Technical Decisions Log** in `action-item.md` with the reason
4. **Do NOT delete the old plan** — comment it out or mark it "REVISED" so you have a record

```markdown
## Technical Decisions Log

| Date | Decision | Reason |
|---|---|---|
| 2026-04-12 | Switch public site from SSG to runtime API fetching | SSG required Amplify rebuild on every publish — too slow and fragile for AI-generated content |
```

If you don't record why a decision was made, the next session will question it, re-evaluate it, and potentially revert it.

---

## Using Claude Code Efficiently

### What Claude Code is Good At

- Implementing well-specified tasks (specific files, specific behavior)
- Searching the codebase for patterns
- Writing Terraform, Python, TypeScript when given clear contracts
- Debugging when given the error message and relevant file paths
- Refactoring when shown the before/after intent

### What Requires Your Input

- **Architecture decisions** — Claude can propose options, but you must decide
- **Prioritization** — Claude doesn't know which milestone matters most to you
- **External context** — AWS account IDs, domain names, team decisions not in the code
- **Testing verification** — Claude can write tests, but you must run them and confirm the output

### Effective Prompting Pattern

Instead of: "Implement the approval flow"

Use: "Implement the approval flow. The handler is in `services/api/topics.py`. It needs to:
1. Read the task token from `TOPIC#{topicId} | REVIEW#{runId}` in DynamoDB
2. Call `sfn.send_task_success()` with the stored token
3. Catch `TaskTimedOut` and return 409
4. Return 200 on success
Verify by starting the local API server and making a POST to `/admin/topics/{id}/review/{runId}` with `{"decision": "approve"}`."

The more context you provide, the less time is spent reading files and the more time is spent implementing.

---

## Common Session Anti-Patterns

| Anti-pattern | Consequence | Fix |
|---|---|---|
| Starting without reading action-item.md | Redoing completed work or skipping steps | Always read it first |
| Ending without updating RESUME HERE | Next session starts confused | Never close without updating |
| Vague steps ("implement X") | Every session re-specifies from scratch | Write verifiable, file-specific steps |
| Not committing at session end | Changes lost if machine fails | Commit action-item.md at minimum |
| Making architecture decisions mid-milestone | Inconsistent codebase | Decide before coding; record the decision |
| "It should work" without testing | Bugs discovered sessions later | Test every code path before marking done |
| Not recording bugs fixed | Next session re-discovers same bugs | Add to session log with specific fix description |

---

## Session Log Format

The session log is for future reference — what was done and what was fixed. Write it for someone (or Claude) coming back 6 months later.

**Template:**
```
| YYYY-MM-DD | [Milestone accomplished]. [Key files created/modified]. [Bugs fixed with specific description]. [Architecture changes if any]. |
```

**Example:**
```
| 2026-04-12 | Bug fixes: approval_worker KeyError — WaitForApproval wraps state as {"task_token":..., "input":{...}}, handler now unwraps. API Lambda missing states:SendTaskSuccess/Failure IAM — added to api-lambda-policy. Worker Lambda missing amplify:CreateDeployment IAM — added to worker role. config_api.py Lambda path fix — _HERE/"openai_runtime" checked first. Architecture: public site switched from SSG to runtime API fetching — no Amplify rebuild on publish. Deployed: API Lambda, search_index_worker, public site (Amplify job 16). |
```

---

## When to Split Into Multiple Sessions

Split a milestone across sessions when:
- The milestone has more than 6-8 distinct steps
- A step requires a decision you haven't made yet
- A step requires external action (AWS console verification, email verification, team input)

When splitting, always end the session at a **verified checkpoint** — a point where you can confirm the current state is clean:
- Tests pass
- No partial implementations that will cause the next session to fail unexpectedly
- `action-item.md` accurately reflects what's done and what's next

Don't split mid-implementation of a single function or module. Finish the unit, verify it, then end the session.

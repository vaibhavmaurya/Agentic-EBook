# Agentic Ebook Platform — Use Case Specification

## 1. Purpose

This document defines the business use cases, operating model, actors, requirements, constraints, and acceptance criteria for an Agentic ebook platform.

The platform creates and continuously maintains a web-based ebook made up of independently managed topics. Each topic can be researched, drafted, reviewed, approved, published, revised, and refreshed on its own schedule. The system uses a multi-agent content generation pipeline with human review before publication.

This document is intentionally solution-light. It captures **what the platform must do** and **why it exists**. 

---

## 2. Product Vision

Build a lightweight, low-management web application on AWS that functions as a living ebook.

The ebook should:
- Present well-structured, web-friendly content organized into topics, sections, and subtopics, with very simple block diagrams (probably mermaid). Should contain sequence diagram for an illustration of the topic.
- Allow an administrator to configure each topic independently.
- Use multi-agent AI workflows to perform deep internet research and draft chapter content. The web resources can be restricted by user as exclusion feature.
- Require admin approval before content becomes publicly visible.
- Support comments, highlights, search, and release transparency.
- Learn from admin review and reader feedback over time.
- Maintain full execution traceability for governance, auditability, and troubleshooting.

---

## 3. Product Scope

### 3.1 In Scope

- Dynamic topic management through an admin UI
- Per-topic scheduling and manual triggering
- Topic-specific instructions/prompt guidance for web search, content extraction, formatting, published book page formatting and presentation methods. User should be able to control each stage by restart/retry/cancel etc
- Deep internet research for each topic
- Multi-agent content generation workflow
- Draft generation and staging
- Admin review, revision, approval, and rejection
- Topic-level publishing to a public (production) website from staging (development)
- Incremental updates to search index and navigation
- Highlighting and commenting by readers on the content
- Feedback mining from user and admin comments
- Weekly release digest summarizing newly approved changes
- Complete event traceability in DynamoDB
- AWS deployment using Terraform
- OpenAI SDK and OpenAI models for AI runtime with multiple span of LLM models used with cost effective and performant manner

### 3.2 Out of Scope for MVP

- Full WYSIWYG rich document editing inside the browser
- Real-time collaborative editing by multiple admins on the same chapter
- Enterprise CMS workflow with complex editorial hierarchies
- Native mobile applications
- Offline-first reading mode
- Automated legal review of generated content
- Full semantic enterprise search across all raw source materials
- Autonomous publishing without human approval

---

## 4. Business Outcomes

The platform is intended to deliver the following business outcomes:

1. Reduce manual research and drafting effort for topic-based web publications.
2. Improve publishing speed while maintaining editorial control.
3. Standardize structure, tone, and formatting across chapters.
4. Allow controlled experimentation with agentic content workflows.
5. Create a repeatable and auditable publishing process.
6. Enable incremental content maintenance rather than full-book rewrites.
7. Continuously improve content quality by learning from reviewer and reader feedback.

---

## 5. Actors and Personas

### 5.1 Website Owner

The business owner of the ebook platform.

**Goals**
- Publish high-quality content regularly
- Understand what changed in each release
- Minimize operational burden
- Ensure the system stays aligned with the intended editorial direction

### 5.2 Website Admin / Editor

The primary operational user of the admin interface.

**Goals**
- Create and maintain topic definitions
- Provide topic-specific instructions
- Trigger or schedule topic runs
- Review, approve, reject, or request revisions
- Monitor run details, source quality, traceability
- Observe LLM cost and performance per topic. Trace the web searches, content extracted, formatted and sent for approval, then publish after approve.
- User can change the topic level instructions and trigger the particular topic research.
- User can trigger any step in the topic mining to publish process. For example user does not want to start the research instead wants to format the content presentation

### 5.3 Public Reader

The end user of the ebook website.

**Goals**
- Read high-quality topic pages
- Search across the ebook
- Highlight text and leave comments
- Understand recent changes to content

### 5.4 Platform Operator

A technical operator or developer responsible for deployment, incident handling, and system changes.

**Goals**
- Deploy and update infrastructure safely
- Monitor workflows and failures
- Investigate trace events
- Control operational cost and security posture

### 5.5 Multi-Agent Content System

A coordinated set of AI agents and deterministic services that perform planning, research, verification, writing, reviewing, and feedback analysis.

**Goals**
- Produce better content than a single-step generation flow
- Separate responsibilities across specialized agent roles
- Improve controllability, quality, and auditability

---

## 6. Core Conceptual Model

The platform should be treated as a **dynamic topic orchestration system**, not just a weekly batch ebook generator.

### 6.1 Topic as the Primary Unit

Each topic is an independent publishing unit with its own:
- title
- short description
- admin instructions
- target audience or tone overrides
- structure hints and subtopics
- dependency list
- schedule
- run history
- draft state
- review state
- published state
- feedback history
- trace history

### 6.2 Book as the Presentation Layer

The public ebook is the assembled reading experience built from many topic pages. A “book release” is a presentation event summarizing approved topic updates, not necessarily a single monolithic full rebuild.

---

## 7. Use Case Catalog

### UC-01 — Create Topic

**Primary actor:** Website Admin  
**Goal:** Add a new topic to the ebook backlog

**Preconditions**
- Admin is authenticated
- Admin has topic management permissions

**Main flow**
1. Admin opens topic management UI.
2. Admin enters title, description, structure hints, and topic instructions.
3. Admin defines or accepts a default schedule.
4. System validates required fields.
5. System stores the topic as an active draft topic.
6. System records a trace event.

**Postconditions**
- Topic exists in the configuration store
- Topic can be scheduled or manually triggered

### UC-02 — Update Topic Configuration

**Primary actor:** Website Admin  
**Goal:** Modify the instructions or configuration for an existing topic

**Main flow**
1. Admin opens an existing topic.
2. Admin changes one or more fields.
3. System validates the change.
4. System updates the topic record.
5. System records before/after trace details.
6. If schedule changes, the system updates the execution schedule.

### UC-03 — Reorder Topics

**Primary actor:** Website Admin  
**Goal:** Change the order in which topics appear in the ebook

**Outcome**
- Navigation and table of contents reflect the new ordering after publish/index rebuild.

### UC-04 — Trigger Topic Run Manually

**Primary actor:** Website Admin  
**Goal:** Force content refresh for one topic immediately

**Main flow**
1. Admin clicks trigger.
2. System creates a new topic run.
3. Multi-agent workflow starts.
4. Trace events are recorded for all subsequent steps.

### UC-05 — Run Topic Automatically on Schedule

**Primary actor:** System  
**Goal:** Refresh a topic according to its schedule

**Main flow**
1. Scheduler fires for the topic.
2. System starts a new topic run.
3. Multi-agent workflow executes.
4. Draft output is created for review.

### UC-06 — Perform Multi-Agent Research and Drafting

**Primary actor:** Multi-Agent Content System  
**Goal:** Produce a staged draft for a topic

**Main flow**
1. Topic Planner interprets topic instructions and output goals.
2. Research Agent gathers source material from the internet.
3. Evidence Verifier checks authority, freshness, duplication, and coverage.
4. Chapter Writer drafts chapter content.
5. Editorial Reviewer checks style, structure, and compliance with instructions.
6. System stores the draft, metadata, citations/provenance, and run trace.

### UC-07 — Review Topic Draft

**Primary actor:** Website Admin  
**Goal:** Review the draft created by the AI pipeline

**Main flow**
1. Admin opens the staged topic draft.
2. Admin views content, source summary, diffs, and run metadata.
3. Admin chooses approve, reject, or request revisions.
4. System records the decision and rationale.

### UC-08 — Approve Topic for Publish

**Primary actor:** Website Admin  
**Goal:** Make staged topic content eligible for public publishing

**Postconditions**
- Draft becomes the next published version for the topic
- Search index and navigation are refreshed
- Release summary is updated
- Notifications may be sent

### UC-09 — Reject Topic Draft

**Primary actor:** Website Admin  
**Goal:** Prevent poor-quality content from going live

**Main flow**
1. Admin rejects draft.
2. Admin enters rejection notes.
3. System stores the notes as structured revision guidance.
4. System marks run as rejected.
5. Rejection feedback becomes available for future runs.

### UC-10 — Publish Incremental Topic Update

**Primary actor:** System  
**Goal:** Publish one approved topic without requiring a full-book rebuild

**Main flow**
1. System promotes approved topic content from staging to production.
2. System updates topic version pointers.
3. System rebuilds TOC, search index, and release notes.
4. System invalidates or refreshes site delivery artifacts if needed.

### UC-11 — Search the Ebook

**Primary actor:** Public Reader  
**Goal:** Find relevant topic content quickly

**Main flow**
1. Reader enters keywords in search UI.
2. System returns matching chapters and sections.
3. Reader opens the relevant section.

### UC-12 — Highlight Text and Add Comment

**Primary actor:** Public Reader  
**Goal:** Leave contextual feedback on a passage

**Main flow**
1. Reader highlights a text span.
2. Reader enters a comment.
3. System stores the highlight anchor and associated comment.
4. Feedback becomes available for admin review and future AI learning.

### UC-13 — Review Feedback Trends

**Primary actor:** Website Admin  
**Goal:** Understand where the system is underperforming

**Main flow**
1. Admin opens feedback analytics.
2. System groups comments by topic, section, issue type, and severity.
3. Admin reviews patterns and decides whether to adjust instructions or rerun topics.

### UC-14 — Generate Weekly Release Digest

**Primary actor:** System  
**Goal:** Inform the website owner about newly published changes

**Main flow**
1. System identifies all approved and published updates since the last digest.
2. System prepares a change summary.
3. System sends the digest to the website owner.

### UC-15 — Investigate a Failed Run

**Primary actor:** Platform Operator / Website Admin  
**Goal:** Troubleshoot pipeline failures quickly

**Main flow**
1. User opens run history and trace details.
2. System shows state transitions, errors, tool calls, and affected artifacts.
3. User identifies the failed stage.
4. User retriggers or remediates.

---

## 8. End-to-End Operational Scenarios

### 8.1 New Topic Lifecycle

1. Admin creates topic.
2. System schedules topic.
3. Topic run executes.
4. Draft is generated.
5. Admin reviews and approves.
6. Topic is published.
7. Public readers view and comment.
8. Feedback influences future topic runs.

### 8.2 Existing Topic Refresh Lifecycle

1. Scheduled or manual trigger starts a new run.
2. Research and drafting agents produce a revised topic.
3. System compares new draft with current published version.
4. Admin reviews changes.
5. Approved content is published incrementally.
6. Release digest includes the update.

### 8.3 Rejection and Learning Lifecycle

1. Admin rejects a draft.
2. Rejection notes are stored.
3. Feedback Learning process aggregates rejections and user comments.
4. Future prompting and policy instructions are refined.

---

## 9. Functional Requirements

### 9.1 Topic Management

- FR-001: The system shall allow creation, update, soft deletion, and reordering of topics.
- FR-002: The system shall store a short description for each topic.
- FR-003: The system shall allow admin instructions for each topic.
- FR-004: The system shall support topic dependencies.
- FR-005: The system shall support schedule types including manual, weekly, daily, and custom cron.
- FR-006: The system shall allow a topic to be manually triggered on demand.

### 9.2 Agentic Content Generation

- FR-007: The system shall execute a multi-agent pipeline per topic.
- FR-008: The system shall support deep internet research for each topic.
- FR-009: The system shall ingest, normalize, and persist collected content and metadata.
- FR-010: The system shall generate structured drafts with sections and subtopics.
- FR-011: The system shall preserve source provenance for generated content.
- FR-012: The system shall generate topic change summaries relative to the last published version.

### 9.3 Review and Publish

- FR-013: The system shall stage generated topic drafts before publication.
- FR-014: The system shall require admin approval before publication.
- FR-015: The system shall allow rejection with structured notes.
- FR-016: The system shall publish approved content incrementally at topic level.
- FR-017: The system shall maintain version history for published topics.

### 9.4 Website Experience

- FR-018: The public website shall present well-formatted ebook content.
- FR-019: The website shall support keyword search.
- FR-020: The website shall support text highlights and comments.
- FR-021: The website shall surface release or version information for changed content.

### 9.5 Feedback and Learning

- FR-022: The system shall capture user comments and highlight metadata.
- FR-023: The system shall capture admin approval and rejection decisions.
- FR-024: The system shall analyze feedback to derive future instruction improvements.
- FR-025: The system shall make feedback-derived guidance available to future runs.

### 9.6 Traceability and Operations

- FR-026: The system shall record all major state transitions in DynamoDB.
- FR-027: The system shall record run-level details including topic, run status, start/end time, and cost metadata.
- FR-028: The system shall expose run history and trace events in the admin UI.
- FR-029: The system shall notify the website owner about newly published changes.
- FR-030: The system shall be deployable using Terraform.

---

## 10. Non-Functional Requirements

### 10.1 Architecture and Deployment

- NFR-001: The platform shall run entirely in AWS.
- NFR-002: Infrastructure shall be defined and deployed through Terraform.
- NFR-003: The architecture shall be event-driven.
- NFR-004: The platform shall favor managed or serverless services to minimize operational overhead.

### 10.2 Quality and Governance

- NFR-005: No AI-generated topic content shall be published without human approval.
- NFR-006: Every topic run shall be auditable.
- NFR-007: The system shall maintain traceability from schedule trigger to publish outcome.
- NFR-008: Generated content shall preserve source provenance at least at section or subsection level.

### 10.3 Security

- NFR-009: Admin functionality shall require authenticated access.
- NFR-010: Public users shall not have access to admin APIs.
- NFR-011: Secrets and API keys shall not be stored in source code or frontend assets.
- NFR-012: Public comment capture shall include abuse controls and validation.

### 10.4 Performance and Scale

- NFR-013: Topic pipelines shall run independently so one topic failure does not block others.
- NFR-014: The system shall support concurrent runs for multiple topics.
- NFR-015: Search on the public website shall remain responsive for normal ebook sizes.

### 10.5 Maintainability

- NFR-016: The architecture shall support adding new agent roles or tools without redesigning the full system.
- NFR-017: Topic configuration changes shall not require code redeployment.
- NFR-018: The solution shall support incremental enhancement toward semantic search and richer editorial workflows.

---

## 11. Business Rules

- BR-001: A topic cannot be publicly visible until at least one approved version exists.
- BR-002: A rejected topic draft shall not overwrite the currently published topic version.
- BR-003: Admin instructions are specific to a topic and shall be applied during planning and writing stages.
- BR-004: Feedback from users and admins may influence future generation, but not bypass approval.
- BR-005: Topic schedules may differ by topic.
- BR-006: Topic dependency relationships may influence planning and cross-referencing.
- BR-007: Published book ordering shall follow the configured topic order.
- BR-008: Soft-deleted topics shall be excluded from future publishing but retained for history unless explicitly purged.

---

## 12. Data Objects (Business View)

### 12.1 Topic

Represents a configurable content unit.

**Attributes**
- topic_id
- title
- description
- instructions
- subtopics
- order
- schedule
- dependency list
- active/inactive status

### 12.2 Topic Run

Represents one execution of the multi-agent pipeline for a topic.

**Attributes**
- run_id
- topic_id
- trigger type
- status
- started_at
- ended_at
- agent outputs
- cost metadata
- trace reference

### 12.3 Draft

Represents generated content staged for review.

**Attributes**
- draft_id
- topic_id
- run_id
- content pointer
- review status
- diff summary

### 12.4 Published Topic Version

Represents the public version of a topic.

**Attributes**
- topic_id
- version
- publish timestamp
- content pointer
- changelog summary

### 12.5 Review Decision

Represents admin approval or rejection.

**Attributes**
- reviewer
- decision
- notes
- timestamp
- related draft/run

### 12.6 Feedback Item

Represents user or admin feedback tied to a topic or text span.

**Attributes**
- feedback_id
- type
- topic_id
- section anchor
- text selection reference
- comment text
- author type
- created_at

### 12.7 Trace Event

Represents an auditable event emitted by the system.

**Attributes**
- event_id
- run_id
- topic_id
- event_type
- actor
- timestamp
- details payload

---

## 13. Assumptions

- The website owner accepts human review as a mandatory publishing control.
- A lightweight static or mostly static website is sufficient for the public reading experience.
- AI research will use external internet content and therefore source provenance is required.
- The first release can prioritize keyword search and later add semantic retrieval.
- The platform is optimized for a moderate number of topics, not mass-scale publishing from day one.

---

## 14. Constraints

- Must be deployed fully in AWS.
- Must use Terraform for infrastructure deployment.
- Must use OpenAI SDK and OpenAI models instead of Amazon Bedrock.
- Must support dynamic per-topic scheduling and manual runs.
- Must maintain complete traceability in DynamoDB.
- Must provide admin approval before public release.
- Must be designed for low-management operations.

---

## 15. Risks and Requirement Implications

### 15.1 Source Quality Risk
Poor or low-authority sources may reduce content quality.

**Implication:** Source verification and provenance are mandatory.

### 15.2 Over-Autonomy Risk
Autonomous agents may produce content that is misaligned or unsafe to publish.

**Implication:** Human approval is non-negotiable.

### 15.3 Operational Complexity Risk
A multi-agent system can become hard to govern.

**Implication:** Deterministic orchestration and strong traceability are required.

### 15.4 Feedback Mislearning Risk
User comments may be noisy or malicious.

**Implication:** Feedback must be filtered and reviewed before it changes durable instructions.

---

## 16. Acceptance Criteria

### 16.1 Topic Management Acceptance
- Admin can create, edit, delete, and reorder topics through the UI.
- Admin can set topic-specific instructions and schedule.
- Topic changes persist without code deployment.

### 16.2 Pipeline Acceptance
- A single topic can be triggered manually.
- A scheduled topic run starts automatically at its configured time.
- The system produces a staged draft with structured content.
- The run history and trace events are visible in the admin UI.

### 16.3 Review Acceptance
- Admin can approve or reject a staged draft.
- Rejection notes are stored and visible on future review.
- Approved topics become publicly visible only after publish completes.

### 16.4 Website Acceptance
- Public users can browse topic pages.
- Public users can search the ebook.
- Public users can highlight text and leave comments.

### 16.5 Traceability Acceptance
- Every topic run has an associated run record.
- Every major workflow step writes a trace event.
- A failed run can be investigated from the admin interface.

### 16.6 Notification Acceptance
- Website owner receives a digest summarizing newly published topic updates.

---

## 17. Recommended MVP Cut

The MVP should include:
- Topic CRUD
- Per-topic scheduling and manual trigger
- Multi-agent topic pipeline
- Draft generation and admin review
- Incremental publishing
- Public website with keyword search
- Highlights/comments
- DynamoDB traceability
- Weekly digest
- Terraform deployment

Deferred to phase 2:
- Semantic retrieval over source corpus
- WebSocket live status updates
- Rich analytics dashboards
- Multi-admin editorial workflow tiers
- Automated A/B evaluation across model variants

---

## 18. Summary

The V3 product should be positioned as:

**A dynamic, per-topic, multi-agent publishing platform for creating and maintaining a living ebook on AWS, with human approval, full traceability, and feedback-driven improvement.**


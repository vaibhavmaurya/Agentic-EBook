# Agentic Ebook Platform V3 — Diagram Pack

This document provides Mermaid diagrams for the Agentic Ebook Platform V3.

It includes:
- high-level application block diagrams
- component-level block diagrams
- sequence diagrams for key process flows

These diagrams assume the V3 target architecture uses AWS Step Functions for workflow orchestration, EventBridge Scheduler for per-topic scheduling, DynamoDB for operational metadata, Amplify Hosting for the public and admin web applications, API Gateway JWT authorization for admin APIs, and the OpenAI Responses API with an optional OpenAI Agents SDK layer for multi-agent execution.

---

## 1. High-Level Application Block Diagram

```mermaid
flowchart LR
    subgraph UX[User Experience Layer]
        Reader[Public Reader]
        Admin[Website Admin / Editor]
        Owner[Website Owner]
    end

    subgraph WEB[Web Delivery Layer]
        PublicSite[Public Ebook Site\nAmplify Hosting]
        AdminUI[Admin UI\nAmplify Hosting]
    end

    subgraph API[Application API Layer]
        APIGW[API Gateway HTTP API]
        Auth[Cognito]
        LambdaAPI[Lambda APIs\nAdmin / Comments / Review / Publish]
    end

    subgraph ORCH[Workflow & Scheduling]
        Scheduler[EventBridge Scheduler\nPer-topic schedules]
        SFN[Step Functions Standard\nTopic orchestration]
        ManualTrigger[Manual Trigger Endpoint]
    end

    subgraph AI[AI Runtime Layer]
        Adapter[OpenAI Runtime Adapter\nLambda service layer]
        Planner[Topic Planner Agent]
        Research[Research Agent]
        Verifier[Evidence Verifier Agent]
        Writer[Chapter Writer Agent]
        Editor[Editorial Reviewer Agent]
        Diff[Release Diff Agent]
        FeedbackAgent[Feedback Learning Agent]
        OpenAI[OpenAI Responses API\nOptional Agents SDK]
    end

    subgraph DATA[Data & Artifact Layer]
        DDB[DynamoDB\nConfig / Runs / Reviews / Traces / Feedback]
        S3[S3\nRaw sources / Drafts / Published artifacts]
        Secrets[Secrets Manager]
        SearchIndex[Search Index\nLunr.js now / OpenSearch later]
    end

    subgraph NOTIFY[Notification Layer]
        SES[SES / SNS]
    end

    Reader --> PublicSite
    Reader --> APIGW
    Admin --> AdminUI
    Admin --> APIGW
    Owner --> SES

    PublicSite --> APIGW
    AdminUI --> Auth
    AdminUI --> APIGW
    APIGW --> LambdaAPI
    LambdaAPI --> DDB
    LambdaAPI --> S3
    LambdaAPI --> SFN

    Scheduler --> SFN
    ManualTrigger --> SFN
    SFN --> Adapter
    SFN --> DDB
    SFN --> S3
    SFN --> SES

    Adapter --> Secrets
    Adapter --> Planner
    Planner --> Research
    Research --> Verifier
    Verifier --> Writer
    Writer --> Editor
    Editor --> Diff
    FeedbackAgent --> OpenAI
    Planner --> OpenAI
    Research --> OpenAI
    Verifier --> OpenAI
    Writer --> OpenAI
    Editor --> OpenAI
    Diff --> OpenAI

    DDB --> SearchIndex
    S3 --> PublicSite
    S3 --> AdminUI
```

---

## 2. Logical Block Diagram by Major Domains

```mermaid
flowchart TB
    subgraph A[Topic Configuration & Governance]
        TopicConfig[Topic definitions]
        TopicSchedule[Per-topic schedule]
        TopicInstructions[Admin instructions]
        ReviewState[Approval / rejection state]
        TraceLedger[Trace ledger]
    end

    subgraph B[Agentic Content Generation]
        ContextAssembly[Context assembly]
        Planning[Planning]
        Researching[Research]
        Verification[Verification]
        Drafting[Drafting]
        Editing[Editing]
        Diffing[Diffing]
    end

    subgraph C[Publishing & Delivery]
        Staging[Draft staging]
        Approval[Human approval]
        Publish[Topic publish]
        IndexRefresh[TOC / search refresh]
        ReleaseDigest[Release digest]
    end

    subgraph D[Engagement & Learning]
        Highlights[Highlights]
        Comments[Comments]
        AdminReviewNotes[Admin review notes]
        FeedbackMining[Feedback mining]
        PromptPolicy[Prompt / instruction updates]
    end

    A --> B --> C --> D --> B
```

---

## 3. Component Block Diagram — Admin & Public Web Layer

```mermaid
flowchart LR
    subgraph Client[Frontend]
        PublicSPA[Public Site]
        AdminSPA[Admin UI]
    end

    subgraph Security[Identity]
        Cognito[Cognito User Pool]
    end

    subgraph Backend[Backend APIs]
        APIGW[API Gateway HTTP API]
        TopicAPI[Topic Management API]
        ReviewAPI[Review / Approval API]
        CommentAPI[Comments / Highlights API]
        PublishAPI[Publish / Trigger API]
    end

    subgraph Stores[Storage]
        DDB[DynamoDB]
        S3[S3]
    end

    AdminSPA --> Cognito
    AdminSPA --> APIGW
    PublicSPA --> APIGW

    APIGW --> TopicAPI
    APIGW --> ReviewAPI
    APIGW --> CommentAPI
    APIGW --> PublishAPI

    TopicAPI --> DDB
    ReviewAPI --> DDB
    CommentAPI --> DDB
    PublishAPI --> DDB
    PublishAPI --> S3
```

---

## 4. Component Block Diagram — Agentic Execution Layer

```mermaid
flowchart LR
    subgraph StepFunctions[Step Functions Topic Workflow]
        Load[Load topic config]
        Context[Assemble context]
        Plan[Plan topic]
        Research[Research topic]
        Verify[Verify evidence]
        Write[Write chapter]
        Edit[Editorial review]
        Diff[Generate diff]
        WaitApproval[Wait for approval]
        Publish[Publish topic]
        Notify[Notify owner]
    end

    subgraph Adapter[OpenAI Runtime Adapter]
        PlannerFn[run_planner_agent]
        ResearchFn[run_research_agent]
        VerifyFn[run_verifier_agent]
        WriteFn[run_writer_agent]
        EditFn[run_editor_agent]
        DiffFn[run_diff_agent]
        FeedbackFn[run_feedback_agent]
    end

    subgraph OpenAI[OpenAI Runtime]
        Responses[Responses API]
        Tools[Function Tools]
        Agents[Optional Agents SDK]
    end

    Load --> Context --> Plan --> Research --> Verify --> Write --> Edit --> Diff --> WaitApproval --> Publish --> Notify

    Plan --> PlannerFn --> Responses
    Research --> ResearchFn --> Responses
    Verify --> VerifyFn --> Responses
    Write --> WriteFn --> Responses
    Edit --> EditFn --> Responses
    Diff --> DiffFn --> Responses
    Tools --> Responses
    Agents --> Responses
```

---

## 5. Component Block Diagram — Data & Traceability

```mermaid
flowchart LR
    subgraph Producers[Event Producers]
        AdminActions[Admin actions]
        ScheduledRuns[Scheduled runs]
        ManualRuns[Manual runs]
        AgentStages[Agent stages]
        PublishEvents[Publish events]
        ReaderFeedback[Reader feedback]
    end

    subgraph Ledger[DynamoDB Operational Ledger]
        Topics[Topics]
        Runs[Runs]
        Reviews[Reviews]
        Feedback[Feedback]
        Traces[Trace events]
        Notifications[Notifications]
    end

    subgraph Artifacts[S3 Artifact Store]
        Raw[Raw source captures]
        Normalized[Normalized research packs]
        Drafts[Draft chapters]
        Published[Published site assets]
        Snapshots[Release snapshots]
    end

    Producers --> Ledger
    AgentStages --> Artifacts
    PublishEvents --> Artifacts
    Ledger --> Artifacts
```

---

## 6. Sequence Diagram — Create or Update Topic Configuration

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Website Admin
    participant AdminUI as Admin UI
    participant Cognito as Cognito
    participant APIGW as API Gateway
    participant TopicAPI as Topic API Lambda
    participant DDB as DynamoDB
    participant Scheduler as EventBridge Scheduler

    Admin->>AdminUI: Create or edit topic
    AdminUI->>Cognito: Get/refresh token
    Cognito-->>AdminUI: JWT token
    AdminUI->>APIGW: POST/PUT topic request
    APIGW->>TopicAPI: Invoke with JWT claims
    TopicAPI->>DDB: Validate and write topic config
    DDB-->>TopicAPI: Topic stored
    alt Schedule created or changed
        TopicAPI->>Scheduler: Create/update per-topic schedule
        Scheduler-->>TopicAPI: Schedule ARN / confirmation
    end
    TopicAPI->>DDB: Write trace event
    TopicAPI-->>APIGW: Success response
    APIGW-->>AdminUI: Topic saved
    AdminUI-->>Admin: Updated topic state shown
```

---

## 7. Sequence Diagram — Scheduled Topic Run

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as EventBridge Scheduler
    participant SFN as Step Functions
    participant Config as Load Config Lambda
    participant DDB as DynamoDB
    participant S3 as S3
    participant Adapter as OpenAI Runtime Adapter
    participant OpenAI as OpenAI Responses API

    Scheduler->>SFN: Start topic workflow(topic_id)
    SFN->>Config: Load topic configuration
    Config->>DDB: Read topic, instructions, feedback, dependencies
    DDB-->>Config: Topic context
    Config-->>SFN: Assembled input
    SFN->>DDB: Write PIPELINE_STARTED trace

    SFN->>Adapter: Run Planner Agent
    Adapter->>OpenAI: responses.create(planning input)
    OpenAI-->>Adapter: Research plan + output contract
    Adapter-->>SFN: Planner output
    SFN->>DDB: Write PLANNER_COMPLETED trace

    SFN->>Adapter: Run Research Agent
    Adapter->>OpenAI: responses.create(research tools enabled)
    OpenAI-->>Adapter: Evidence pack / tool results
    Adapter->>S3: Store raw and normalized research artifacts
    Adapter-->>SFN: Research output
    SFN->>DDB: Write RESEARCH_COMPLETED trace

    SFN->>Adapter: Run Verifier Agent
    Adapter->>OpenAI: responses.create(verification input)
    OpenAI-->>Adapter: Validated evidence + coverage report
    Adapter-->>SFN: Verification output
    SFN->>DDB: Write VERIFICATION_COMPLETED trace

    SFN->>Adapter: Run Writer + Editor + Diff Agents
    Adapter->>OpenAI: responses.create(writer/editor/diff stages)
    OpenAI-->>Adapter: Draft + scorecard + diff summary
    Adapter->>S3: Store staged draft
    Adapter-->>SFN: Draft package
    SFN->>DDB: Write DRAFT_READY trace
```

---

## 8. Sequence Diagram — Manual Trigger Topic Run

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Website Admin
    participant AdminUI as Admin UI
    participant APIGW as API Gateway
    participant TriggerAPI as Trigger API Lambda
    participant DDB as DynamoDB
    participant SFN as Step Functions

    Admin->>AdminUI: Click "Run now"
    AdminUI->>APIGW: POST /topics/{id}/trigger
    APIGW->>TriggerAPI: Invoke request
    TriggerAPI->>DDB: Write MANUAL_TRIGGER trace
    TriggerAPI->>SFN: Start execution(topic_id, trigger=manual)
    SFN-->>TriggerAPI: Execution ARN
    TriggerAPI-->>APIGW: Accepted + execution id
    APIGW-->>AdminUI: Run started
    AdminUI-->>Admin: Show running state / poll details
```

---

## 9. Sequence Diagram — Multi-Agent Research and Drafting Flow

```mermaid
sequenceDiagram
    autonumber
    participant SFN as Step Functions
    participant Adapter as OpenAI Runtime Adapter
    participant Planner as Planner Agent
    participant Research as Research Agent
    participant Verifier as Evidence Verifier Agent
    participant Writer as Writer Agent
    participant Editor as Editorial Reviewer Agent
    participant Diff as Release Diff Agent
    participant Tools as Search/Fetch/Compare Tools
    participant S3 as S3
    participant DDB as DynamoDB

    SFN->>Adapter: run_planner_agent(topic_context)
    Adapter->>Planner: Planning request
    Planner-->>Adapter: Source strategy + chapter contract
    Adapter->>DDB: Trace planner output

    SFN->>Adapter: run_research_agent(plan)
    Adapter->>Research: Research request
    Research->>Tools: search_web(query set)
    Tools-->>Research: candidate URLs
    Research->>Tools: fetch_url(urls)
    Tools-->>Research: extracted content
    Research-->>Adapter: evidence pack
    Adapter->>S3: Store raw extracts and notes
    Adapter->>DDB: Trace research results

    SFN->>Adapter: run_verifier_agent(evidence)
    Adapter->>Verifier: Verification request
    Verifier-->>Adapter: validated evidence + exclusions + coverage
    Adapter->>S3: Store validated evidence pack
    Adapter->>DDB: Trace verification results

    SFN->>Adapter: run_writer_agent(validated evidence)
    Adapter->>Writer: Drafting request
    Writer-->>Adapter: chapter draft
    Adapter->>S3: Store chapter draft
    Adapter->>DDB: Trace writer output

    SFN->>Adapter: run_editor_agent(draft)
    Adapter->>Editor: Editorial review request
    Editor-->>Adapter: revised draft + scorecard
    Adapter->>S3: Store editorial draft
    Adapter->>DDB: Trace editor output

    SFN->>Adapter: run_diff_agent(old vs new)
    Adapter->>Diff: Diff request
    Diff-->>Adapter: release notes delta
    Adapter->>DDB: Trace diff output
    Adapter-->>SFN: Draft package ready for approval
```

---

## 10. Sequence Diagram — Approval, Rejection, and Callback Resume

```mermaid
sequenceDiagram
    autonumber
    participant SFN as Step Functions
    participant ReviewPrep as Review Prep Lambda
    participant DDB as DynamoDB
    participant SES as SES
    actor Admin as Website Admin
    participant AdminUI as Admin UI
    participant APIGW as API Gateway
    participant ReviewAPI as Review API Lambda

    SFN->>ReviewPrep: Prepare review package + task token
    ReviewPrep->>DDB: Store review record, task token, draft pointer
    ReviewPrep->>SES: Send review email / notification
    ReviewPrep-->>SFN: Enter waitForTaskToken state

    Admin->>AdminUI: Open draft and review metadata
    AdminUI->>APIGW: GET review details
    APIGW->>ReviewAPI: Load draft / review package
    ReviewAPI->>DDB: Read review record
    DDB-->>ReviewAPI: Review package
    ReviewAPI-->>AdminUI: Draft + diff + scorecard

    alt Admin approves
        Admin->>AdminUI: Approve topic
        AdminUI->>APIGW: Submit approval
        APIGW->>ReviewAPI: Approval request
        ReviewAPI->>DDB: Persist approval event
        ReviewAPI->>SFN: SendTaskSuccess(task token)
        SFN-->>SFN: Resume workflow to publish
    else Admin rejects
        Admin->>AdminUI: Reject with revision notes
        AdminUI->>APIGW: Submit rejection
        APIGW->>ReviewAPI: Rejection request
        ReviewAPI->>DDB: Persist rejection + notes
        ReviewAPI->>SFN: SendTaskFailure(task token)
        SFN-->>SFN: End or branch to revision workflow
    end
```

---

## 11. Sequence Diagram — Publish Approved Topic and Refresh Shared Assets

```mermaid
sequenceDiagram
    autonumber
    participant SFN as Step Functions
    participant Publish as Publish Lambda
    participant S3 as S3
    participant DDB as DynamoDB
    participant Search as Search Builder
    participant CDN as Amplify / CDN
    participant SES as SES
    actor Owner as Website Owner

    SFN->>Publish: Publish approved topic
    Publish->>S3: Copy staged draft to published location
    Publish->>Search: Rebuild TOC + search index + changelog fragment
    Search->>S3: Write refreshed shared assets
    Publish->>DDB: Update topic published version
    Publish->>DDB: Write PUBLISHED trace event
    Publish->>CDN: Trigger cache refresh / deployment update
    Publish->>SES: Send owner release notification
    SES-->>Owner: Topic updated + changes summary
    Publish-->>SFN: Publish completed
```

---

## 12. Sequence Diagram — Reader Highlights, Comments, and Feedback Learning

```mermaid
sequenceDiagram
    autonumber
    actor Reader as Public Reader
    participant Site as Public Site
    participant APIGW as API Gateway
    participant CommentAPI as Comments API Lambda
    participant DDB as DynamoDB
    participant Scheduler as EventBridge Scheduler
    participant SFN as Step Functions
    participant Adapter as OpenAI Runtime Adapter
    participant OpenAI as OpenAI Responses API

    Reader->>Site: Highlight text / submit comment
    Site->>APIGW: POST highlight or comment
    APIGW->>CommentAPI: Persist feedback
    CommentAPI->>DDB: Store feedback and trace event
    DDB-->>CommentAPI: Stored
    CommentAPI-->>Site: Acknowledged

    Scheduler->>SFN: Start feedback mining workflow
    SFN->>DDB: Read recent comments, highlights, rejections
    DDB-->>SFN: Feedback set
    SFN->>Adapter: run_feedback_agent(feedback set)
    Adapter->>OpenAI: responses.create(feedback analysis input)
    OpenAI-->>Adapter: Themes, prompt deltas, policy suggestions
    Adapter->>DDB: Store learning outputs
    Adapter-->>SFN: Feedback learning completed
```

---

## 13. Sequence Diagram — Weekly Release Digest for Owner

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as EventBridge Scheduler
    participant SFN as Step Functions
    participant DDB as DynamoDB
    participant Adapter as OpenAI Runtime Adapter
    participant OpenAI as OpenAI Responses API
    participant SES as SES
    actor Owner as Website Owner

    Scheduler->>SFN: Start weekly digest workflow
    SFN->>DDB: Query approved and published topic changes for period
    DDB-->>SFN: Release candidate set
    SFN->>Adapter: Run release summary generation
    Adapter->>OpenAI: responses.create(digest summarization input)
    OpenAI-->>Adapter: Weekly release digest
    Adapter-->>SFN: Digest content
    SFN->>SES: Send digest email
    SES-->>Owner: Weekly release summary
```

---

## 14. Block Diagram — Topic Lifecycle

```mermaid
flowchart LR
    DraftConfig[Topic Configured] --> Queued[Scheduled or Triggered]
    Queued --> Running[Agentic Workflow Running]
    Running --> DraftReady[Draft Ready in Staging]
    DraftReady --> PendingReview[Pending Human Review]
    PendingReview -->|Approve| Published[Published Topic]
    PendingReview -->|Reject| Rework[Revision Notes Captured]
    Rework --> Queued
    Published --> Feedback[Reader/Admin Feedback]
    Feedback --> PolicyLearning[Instruction / Policy Update]
    PolicyLearning --> Queued
```

---

## 15. Block Diagram — Feedback Learning Subsystem

```mermaid
flowchart TB
    ReaderComments[Reader comments]
    ReaderHighlights[Reader highlights]
    AdminRejections[Admin rejection notes]
    AdminEdits[Admin review patterns]

    ReaderComments --> FeedbackStore[DynamoDB feedback store]
    ReaderHighlights --> FeedbackStore
    AdminRejections --> FeedbackStore
    AdminEdits --> FeedbackStore

    FeedbackStore --> FeedbackWorkflow[Scheduled feedback workflow]
    FeedbackWorkflow --> LearningAgent[Feedback Learning Agent]
    LearningAgent --> PolicyProposals[Prompt / instruction proposals]
    PolicyProposals --> AdminReview[Admin review of policy updates]
    AdminReview --> TopicConfig[Topic instructions / system policies]
```

---

## 16. Block Diagram — Publish & Delivery Subsystem

```mermaid
flowchart LR
    ApprovedDraft[Approved staged draft] --> PublishWorker[Publish worker]
    PublishWorker --> PublishedTopic[Published topic page]
    PublishWorker --> TOC[Table of contents refresh]
    PublishWorker --> SearchIndex[Search index refresh]
    PublishWorker --> ChangeLog[Changelog update]
    PublishWorker --> ReleaseSnapshot[Release snapshot]
    PublishedTopic --> PublicSite[Public ebook site]
    TOC --> PublicSite
    SearchIndex --> PublicSite
    ChangeLog --> PublicSite
```

---

## 17. Suggested Usage

- Use these Mermaid diagrams directly in GitHub, Markdown previews, Confluence markdown renderers, or documentation portals that support Mermaid.
- For presentations, export them into SVG/PNG or redraw selected diagrams in a slide-native format.
- For implementation docs, keep the high-level block diagram, topic workflow sequence, approval flow, and feedback learning flow as the core set.


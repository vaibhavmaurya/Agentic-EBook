export type ScheduleType = 'manual' | 'daily' | 'weekly' | 'custom'

export type RunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'WAITING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'FAILED'
  | 'TIMED_OUT'

export interface LastRun {
  run_id: string
  status: RunStatus
  started_at: string
  cost_usd: number
}

export interface Topic {
  topic_id: string
  title: string
  description: string
  instructions: string
  subtopics: string[]
  order: number
  active: boolean
  schedule_type: ScheduleType
  cron_expression: string | null
  current_published_version: string | null
  published_at: string | null
  created_at: string
  updated_at: string
  last_run: LastRun | null
}

export interface TopicListItem {
  topic_id: string
  title: string
  description: string
  order: number
  active: boolean
  schedule_type: ScheduleType
  last_run: LastRun | null
}

export interface TopicCreatePayload {
  title: string
  description: string
  instructions: string
  subtopics: string[]
  schedule_type: ScheduleType
  cron_expression: string | null
}

export interface ApiError {
  error: string
  message: string
}

// ── Review types (M5) ─────────────────────────────────────────────────────────

export type ReviewStatus = 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' | 'TIMED_OUT'

export interface Scorecard {
  instruction_adherence: number
  style_compliance: number
  factual_confidence: number
  clarity: number
  overall: number
}

export interface DiffSummary {
  is_first_version: boolean
  sections_added: string[]
  sections_removed: string[]
  sections_changed: string[]
  release_notes: string
}

export interface ReviewQueueItem {
  topic_id: string
  run_id: string
  title: string
  review_status: ReviewStatus
  timeout_at: string
  updated_at: string
}

export interface ReviewDetail {
  topic_id: string
  run_id: string
  title: string
  review_status: ReviewStatus
  timeout_at: string
  reviewer: string | null
  notes: string | null
  approved_at: string | null
  rejected_at: string | null
  // inlined draft content
  content: string
  sections: string[]
  word_count: number
  scorecard: Scorecard
  changes_summary: string
  diff: DiffSummary
  run: {
    status: RunStatus | null
    trigger_source: string | null
    started_at: string | null
    cost_usd_total: number | null
  }
}

export interface ReviewDecisionPayload {
  decision: 'approve' | 'reject'
  notes: string
}

// ── Run history types (M8) ────────────────────────────────────────────────────

export interface RunSummary {
  run_id: string
  status: RunStatus
  trigger_source: string
  triggered_by: string
  execution_arn: string
  started_at: string
  completed_at: string | null
  cost_usd: string
  content_score: string | null
}

export interface TraceEvent {
  sk: string
  event_type: string
  stage: string | null
  agent_name: string | null
  model_name: string | null
  token_usage: Record<string, number> | null
  cost_usd: string
  error_message: string | null
  error_classification: string | null
  timestamp: string | null
}

export interface RunDetail {
  run: RunSummary
  trace_events: TraceEvent[]
  stage_costs: Record<string, number>
}

// ── Feedback types (M8) ───────────────────────────────────────────────────────

export type FeedbackType = 'COMMENT' | 'HIGHLIGHT'
export type ModerationStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface FeedbackItem {
  feedback_id: string
  feedback_type: FeedbackType
  topic_id: string
  section_id: string | null
  comment_text: string | null
  selected_text: string | null
  highlight_id: string | null
  moderation_status: ModerationStatus
  created_at: string
}

export interface TopicFeedbackSummary {
  topic_id: string
  comment_count: number
  highlight_count: number
  pending_count: number
  recent: Array<{
    feedback_id: string
    feedback_type: FeedbackType
    section_id: string | null
    comment_text: string
    selected_text: string
    moderation_status: ModerationStatus
    created_at: string
  }>
}

export interface FeedbackSummaryResponse {
  topics: TopicFeedbackSummary[]
  topic_count: number
  total_feedback: number
}

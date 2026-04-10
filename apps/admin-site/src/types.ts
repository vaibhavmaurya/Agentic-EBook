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

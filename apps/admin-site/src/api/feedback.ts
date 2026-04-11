import { apiClient } from './client'
import type { FeedbackItem, FeedbackSummaryResponse } from '../types'

export const feedbackApi = {
  summary: async (): Promise<FeedbackSummaryResponse> => {
    const res = await apiClient.get('/admin/feedback/summary')
    return res.data
  },

  listForTopic: async (topicId: string, type?: 'COMMENT' | 'HIGHLIGHT'): Promise<FeedbackItem[]> => {
    const params = type ? `?type=${type}` : ''
    const res = await apiClient.get(`/admin/topics/${topicId}/feedback${params}`)
    return res.data.feedback
  },
}

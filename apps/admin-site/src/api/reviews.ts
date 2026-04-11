import { apiClient } from './client'
import type { ReviewQueueItem, ReviewDetail, ReviewDecisionPayload } from '../types'

export const reviewsApi = {
  list: async (): Promise<ReviewQueueItem[]> => {
    const res = await apiClient.get('/admin/reviews')
    return res.data.reviews
  },

  get: async (topicId: string, runId: string): Promise<ReviewDetail> => {
    const res = await apiClient.get(`/admin/topics/${topicId}/review/${runId}`)
    return res.data
  },

  submit: async (
    topicId: string,
    runId: string,
    payload: ReviewDecisionPayload,
  ): Promise<{ review_status: string; decided_at: string }> => {
    const res = await apiClient.post(`/admin/topics/${topicId}/review/${runId}`, payload)
    return res.data
  },
}

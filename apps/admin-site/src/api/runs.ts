import { apiClient } from './client'
import type { RunSummary, RunDetail } from '../types'

export const runsApi = {
  list: async (topicId: string): Promise<RunSummary[]> => {
    const res = await apiClient.get(`/admin/topics/${topicId}/runs`)
    return res.data.runs
  },

  get: async (topicId: string, runId: string): Promise<RunDetail> => {
    const res = await apiClient.get(`/admin/topics/${topicId}/runs/${runId}`)
    return res.data
  },
}

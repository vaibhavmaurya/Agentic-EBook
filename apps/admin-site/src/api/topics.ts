import { apiClient } from './client'
import type { Topic, TopicListItem, TopicCreatePayload } from '../types'

export const topicsApi = {
  list: async (): Promise<TopicListItem[]> => {
    const res = await apiClient.get('/admin/topics')
    return res.data.topics
  },

  get: async (topicId: string): Promise<Topic> => {
    const res = await apiClient.get(`/admin/topics/${topicId}`)
    return res.data
  },

  create: async (payload: TopicCreatePayload): Promise<{ topic_id: string }> => {
    const res = await apiClient.post('/admin/topics', payload)
    return res.data
  },

  update: async (topicId: string, payload: Partial<TopicCreatePayload>): Promise<void> => {
    await apiClient.put(`/admin/topics/${topicId}`, payload)
  },

  delete: async (topicId: string): Promise<void> => {
    await apiClient.delete(`/admin/topics/${topicId}`)
  },

  reorder: async (orderedIds: string[]): Promise<void> => {
    await apiClient.put('/admin/topics/reorder', { order: orderedIds })
  },

  trigger: async (topicId: string): Promise<{ run_id: string; execution_arn: string }> => {
    const res = await apiClient.post(`/admin/topics/${topicId}/trigger`)
    return res.data
  },
}

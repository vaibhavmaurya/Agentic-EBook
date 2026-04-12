import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { feedbackApi } from '../api/feedback'
import type { TopicFeedbackSummary } from '../types'

function TopicFeedbackCard({ summary }: { summary: TopicFeedbackSummary }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e5e7eb',
      borderRadius: 8,
      marginBottom: 12,
      overflow: 'hidden',
    }}>
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          textAlign: 'left',
          font: 'inherit',
        }}
      >
        <div>
          <code style={{ fontSize: 12, color: '#6b7280' }}>{summary.topic_id.slice(0, 8)}…</code>
          <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
            <span style={{ fontSize: 13, color: '#374151' }}>
              💬 {summary.comment_count} comment{summary.comment_count !== 1 ? 's' : ''}
            </span>
            <span style={{ fontSize: 13, color: '#374151' }}>
              🖍 {summary.highlight_count} highlight{summary.highlight_count !== 1 ? 's' : ''}
            </span>
            {summary.pending_count > 0 && (
              <span style={{
                fontSize: 12,
                background: '#fef3c7',
                color: '#92400e',
                border: '1px solid #fde68a',
                borderRadius: 4,
                padding: '2px 8px',
              }}>
                {summary.pending_count} pending
              </span>
            )}
          </div>
        </div>
        <span style={{ fontSize: 16, color: '#9ca3af' }}>{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div style={{ borderTop: '1px solid #f3f4f6', padding: '0 20px 16px' }}>
          {summary.recent.length === 0 ? (
            <p style={{ color: '#9ca3af', fontSize: 14, marginTop: 12 }}>No recent feedback.</p>
          ) : (
            summary.recent.map(item => (
              <div key={item.feedback_id} style={{
                borderBottom: '1px solid #f9fafb',
                padding: '10px 0',
                fontSize: 13,
              }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                  <span style={{
                    background: item.feedback_type === 'COMMENT' ? '#ede9fe' : '#fce7f3',
                    color: item.feedback_type === 'COMMENT' ? '#7c3aed' : '#be185d',
                    borderRadius: 4,
                    padding: '2px 6px',
                    fontSize: 11,
                    fontWeight: 600,
                  }}>
                    {item.feedback_type}
                  </span>
                  <span style={{
                    background: item.moderation_status === 'PENDING' ? '#fef3c7' : '#d1fae5',
                    color: item.moderation_status === 'PENDING' ? '#92400e' : '#065f46',
                    borderRadius: 4,
                    padding: '2px 6px',
                    fontSize: 11,
                    fontWeight: 600,
                  }}>
                    {item.moderation_status}
                  </span>
                  {item.section_id && (
                    <span style={{ fontSize: 11, color: '#9ca3af' }}>§ {item.section_id}</span>
                  )}
                  <span style={{ fontSize: 11, color: '#9ca3af', marginLeft: 'auto' }}>
                    {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                  </span>
                </div>
                {item.comment_text && (
                  <p style={{ color: '#374151', margin: 0, lineHeight: 1.5 }}>{item.comment_text}</p>
                )}
                {item.selected_text && (
                  <blockquote style={{
                    margin: '4px 0 0',
                    paddingLeft: 10,
                    borderLeft: '3px solid #e5e7eb',
                    color: '#6b7280',
                    fontStyle: 'italic',
                  }}>
                    "{item.selected_text}"
                  </blockquote>
                )}
              </div>
            ))
          )}
          <Link
            to="/feedback"
            style={{ display: 'inline-block', marginTop: 8, fontSize: 13, color: '#3b82f6', textDecoration: 'none' }}
          >
            View all feedback →
          </Link>
        </div>
      )}
    </div>
  )
}

export default function FeedbackPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['feedback-summary'],
    queryFn: feedbackApi.summary,
    refetchInterval: 60_000,
  })

  if (isLoading) return <p style={{ padding: 32 }}>Loading feedback…</p>
  if (error) return <p style={{ padding: 32, color: '#ef4444' }}>Failed to load feedback.</p>

  return (
    <div style={{ padding: 32, maxWidth: 860 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Reader Feedback</h1>
          <p style={{ color: '#6b7280', fontSize: 14, margin: '4px 0 0' }}>
            {data?.total_feedback ?? 0} total items across {data?.topic_count ?? 0} topic{data?.topic_count !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {!data || data.topics.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#9ca3af' }}>
          <p style={{ fontSize: '2rem', marginBottom: 8 }}>💬</p>
          <p>No reader feedback yet.</p>
        </div>
      ) : (
        data.topics.map(summary => (
          <TopicFeedbackCard key={summary.topic_id} summary={summary} />
        ))
      )}
    </div>
  )
}

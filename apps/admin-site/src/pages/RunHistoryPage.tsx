import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { runsApi } from '../api/runs'
import type { RunSummary, RunStatus } from '../types'

const STATUS_COLORS: Record<RunStatus, string> = {
  PENDING:          '#f59e0b',
  RUNNING:          '#3b82f6',
  WAITING_APPROVAL: '#8b5cf6',
  APPROVED:         '#10b981',
  REJECTED:         '#ef4444',
  FAILED:           '#ef4444',
  TIMED_OUT:        '#6b7280',
}

function scoreColor(score: number): string {
  if (score >= 0.8) return '#10b981'
  if (score >= 0.6) return '#f59e0b'
  return '#ef4444'
}

function RunCard({ run, topicId }: { run: RunSummary; topicId: string }) {
  const color = STATUS_COLORS[run.status as RunStatus] ?? '#6b7280'
  const cost = parseFloat(run.cost_usd || '0')
  return (
    <Link
      to={`/topics/${topicId}/runs/${run.run_id}`}
      style={{
        display: 'block',
        background: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '16px 20px',
        textDecoration: 'none',
        color: '#111827',
        marginBottom: 10,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{
              display: 'inline-block',
              background: color + '20',
              color,
              border: `1px solid ${color}40`,
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: 12,
              fontWeight: 600,
            }}>
              {run.status}
            </span>
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              {run.trigger_source?.replace('_', ' ')}
            </span>
          </div>
          <div style={{ fontSize: 13, color: '#374151' }}>
            <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#6b7280' }}>
              {run.run_id.slice(0, 8)}…
            </span>
            {run.triggered_by && (
              <span style={{ marginLeft: 12, color: '#6b7280' }}>by {run.triggered_by}</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>
            Started {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
            {run.completed_at && (
              <> · Completed {new Date(run.completed_at).toLocaleString()}</>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>
              ${cost.toFixed(4)}
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af' }}>cost</div>
          </div>
          {run.content_score && (
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: scoreColor(parseFloat(run.content_score)) }}>
                {parseFloat(run.content_score).toFixed(2)}
              </div>
              <div style={{ fontSize: 12, color: '#9ca3af' }}>content score</div>
            </div>
          )}
        </div>
      </div>
    </Link>
  )
}

export default function RunHistoryPage() {
  const { topicId } = useParams<{ topicId: string }>()

  const { data: runs, isLoading, error } = useQuery({
    queryKey: ['runs', topicId],
    queryFn: () => runsApi.list(topicId!),
    enabled: !!topicId,
    refetchInterval: 30_000,
  })

  if (isLoading) return <p style={{ padding: 32 }}>Loading runs…</p>
  if (error) return <p style={{ padding: 32, color: '#ef4444' }}>Failed to load run history.</p>

  const totalCost = (runs ?? []).reduce((sum, r) => sum + parseFloat(r.cost_usd || '0'), 0)

  return (
    <div style={{ padding: 32, maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <Link to="/topics" style={{ fontSize: 13, color: '#6b7280', textDecoration: 'none' }}>
          ← Topics
        </Link>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Run History</h1>
          <p style={{ color: '#6b7280', fontSize: 14, margin: '4px 0 0' }}>
            Topic <code style={{ fontSize: 12 }}>{topicId}</code>
          </p>
        </div>
        {runs && runs.length > 0 && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 18, fontWeight: 700 }}>${totalCost.toFixed(4)}</div>
            <div style={{ fontSize: 12, color: '#9ca3af' }}>total across {runs.length} run{runs.length !== 1 ? 's' : ''}</div>
          </div>
        )}
      </div>

      {!runs || runs.length === 0 ? (
        <p style={{ color: '#6b7280', textAlign: 'center', padding: '48px 0' }}>No runs yet for this topic.</p>
      ) : (
        runs.map(run => <RunCard key={run.run_id} run={run} topicId={topicId!} />)
      )}
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { runsApi } from '../api/runs'
import { topicsApi } from '../api/topics'
import type { TraceEvent } from '../types'

const EVENT_COLORS: Record<string, string> = {
  STAGE_STARTED:   '#3b82f6',
  STAGE_COMPLETED: '#10b981',
  STAGE_FAILED:    '#ef4444',
  RUN_TRIGGERED_MANUAL:   '#8b5cf6',
  RUN_TRIGGERED_SCHEDULE: '#8b5cf6',
}

function EventRow({ ev }: { ev: TraceEvent }) {
  const color = EVENT_COLORS[ev.event_type] ?? '#6b7280'
  const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '—'
  const cost = parseFloat(ev.cost_usd || '0')
  const tokens = ev.token_usage
    ? Object.entries(ev.token_usage).map(([k, v]) => `${k}: ${v}`).join(', ')
    : null

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '80px 160px 1fr auto',
      gap: 12,
      alignItems: 'start',
      padding: '10px 0',
      borderBottom: '1px solid #f3f4f6',
      fontSize: 13,
    }}>
      <span style={{
        display: 'inline-block',
        background: color + '15',
        color,
        border: `1px solid ${color}30`,
        borderRadius: 4,
        padding: '2px 6px',
        fontSize: 11,
        fontWeight: 600,
        textAlign: 'center',
      }}>
        {ev.event_type.replace('STAGE_', '').replace('_', ' ')}
      </span>

      <div>
        <div style={{ fontWeight: 500, color: '#374151' }}>{ev.stage ?? '—'}</div>
        {ev.agent_name && (
          <div style={{ fontSize: 11, color: '#9ca3af' }}>{ev.agent_name} · {ev.model_name}</div>
        )}
      </div>

      <div>
        {tokens && <div style={{ color: '#6b7280', fontSize: 12 }}>{tokens}</div>}
        {ev.error_message && (
          <div style={{ color: '#ef4444', fontSize: 12, marginTop: 2 }}>
            {ev.error_message}
          </div>
        )}
      </div>

      <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
        {cost > 0 && (
          <div style={{ fontWeight: 500, color: '#374151' }}>${cost.toFixed(5)}</div>
        )}
        <div style={{ color: '#9ca3af', fontSize: 11 }}>{ts}</div>
      </div>
    </div>
  )
}

function StageCostBar({ stageCosts }: { stageCosts: Record<string, number> }) {
  const entries = Object.entries(stageCosts).filter(([, v]) => v > 0)
  if (!entries.length) return null
  const total = entries.reduce((s, [, v]) => s + v, 0)
  const colors = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899']
  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: '#6b7280', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Cost by Stage
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {entries.map(([stage, cost], i) => (
          <div key={stage} style={{ display: 'grid', gridTemplateColumns: '200px 1fr 70px', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 12, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stage}</span>
            <div style={{ background: '#f3f4f6', borderRadius: 4, height: 8, overflow: 'hidden' }}>
              <div style={{
                width: `${(cost / total) * 100}%`,
                height: '100%',
                background: colors[i % colors.length],
                borderRadius: 4,
              }} />
            </div>
            <span style={{ fontSize: 12, textAlign: 'right', color: '#374151' }}>${cost.toFixed(5)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function RunDetailPage() {
  const { topicId, runId } = useParams<{ topicId: string; runId: string }>()

  const { data, isLoading, error } = useQuery({
    queryKey: ['run', topicId, runId],
    queryFn: () => runsApi.get(topicId!, runId!),
    enabled: !!(topicId && runId),
    refetchInterval: (q) => {
      const status = q.state.data?.run?.status
      return status === 'PENDING' || status === 'RUNNING' ? 5_000 : false
    },
  })

  const { data: topic } = useQuery({
    queryKey: ['topic', topicId],
    queryFn: () => topicsApi.get(topicId!),
    enabled: !!topicId,
  })

  if (isLoading) return <p style={{ padding: 32 }}>Loading run…</p>
  if (error || !data) return <p style={{ padding: 32, color: '#ef4444' }}>Failed to load run detail.</p>

  const { run, trace_events, stage_costs } = data
  const totalCost = parseFloat(run.cost_usd || '0')

  return (
    <div style={{ padding: 32, maxWidth: 1000 }}>
      <div style={{ display: 'flex', gap: 8, fontSize: 13, color: '#6b7280', marginBottom: 8 }}>
        <Link to="/topics" style={{ color: '#6b7280', textDecoration: 'none' }}>Topics</Link>
        <span>›</span>
        {topic && (
          <>
            <Link to={`/topics/${topicId}`} style={{ color: '#6b7280', textDecoration: 'none' }}>
              {topic.title}
            </Link>
            <span>›</span>
          </>
        )}
        <Link to={`/topics/${topicId}/runs`} style={{ color: '#6b7280', textDecoration: 'none' }}>Runs</Link>
        <span>›</span>
        <span style={{ color: '#374151' }}>{runId?.slice(0, 8)}…</span>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0 0 4px' }}>
            Run Detail
          </h1>
          <code style={{ fontSize: 12, color: '#9ca3af' }}>{runId}</code>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>${totalCost.toFixed(4)}</div>
          <div style={{ fontSize: 12, color: '#9ca3af' }}>total cost</div>
        </div>
      </div>

      {/* Run metadata */}
      <div style={{
        background: '#f9fafb',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '16px 20px',
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 16,
        marginBottom: 24,
        fontSize: 13,
      }}>
        {[
          ['Status', run.status],
          ['Trigger', run.trigger_source?.replace('_', ' ') ?? '—'],
          ['By', run.triggered_by ?? '—'],
          ['Started', run.started_at ? new Date(run.started_at).toLocaleString() : '—'],
          ['Completed', run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'],
          ['Execution ARN', run.execution_arn ? run.execution_arn.split(':').slice(-1)[0] : '—'],
        ].map(([label, value]) => (
          <div key={label}>
            <div style={{ fontWeight: 600, color: '#6b7280', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
              {label}
            </div>
            <div style={{ color: '#111827', wordBreak: 'break-all' }}>{value}</div>
          </div>
        ))}
      </div>

      <StageCostBar stageCosts={stage_costs} />

      {/* Trace events */}
      <h3 style={{ fontSize: 13, fontWeight: 600, color: '#6b7280', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Trace Events ({trace_events.length})
      </h3>
      {trace_events.length === 0 ? (
        <p style={{ color: '#9ca3af', fontSize: 14 }}>No trace events recorded yet.</p>
      ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: '0 16px' }}>
          {trace_events.map((ev, i) => <EventRow key={i} ev={ev} />)}
        </div>
      )}

      {/* Retry button for failed runs */}
      {(run.status === 'FAILED' || run.status === 'TIMED_OUT') && (
        <div style={{ marginTop: 24 }}>
          <Link
            to={`/topics/${topicId}`}
            style={{
              display: 'inline-block',
              background: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              padding: '8px 20px',
              fontSize: 14,
              fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            ↺ Trigger New Run
          </Link>
        </div>
      )}
    </div>
  )
}

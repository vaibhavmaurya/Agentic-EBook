import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewsApi } from '../api/reviews'
import type { Scorecard, ReviewDetail } from '../types'
import styles from './ReviewDetailPage.module.css'

// ── Scorecard bar ─────────────────────────────────────────────────────────────

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color =
    pct >= 80 ? 'var(--color-success)' :
    pct >= 60 ? 'var(--color-warning)' :
                'var(--color-danger)'
  return (
    <div className={styles.scoreRow}>
      <span className={styles.scoreLabel}>{label}</span>
      <div className={styles.scoreTrack}>
        <div className={styles.scoreFill} style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className={styles.scorePct}>{pct}%</span>
    </div>
  )
}

function ScorecardPanel({ scorecard }: { scorecard: Scorecard }) {
  const dims: [keyof Scorecard, string][] = [
    ['overall',               'Overall'],
    ['instruction_adherence', 'Instruction adherence'],
    ['style_compliance',      'Style compliance'],
    ['factual_confidence',    'Factual confidence'],
    ['clarity',               'Clarity'],
  ]
  return (
    <div className={`card ${styles.panel}`}>
      <h3 className={styles.panelTitle}>Editorial Scorecard</h3>
      <div className={styles.scoreList}>
        {dims.map(([key, label]) => (
          <ScoreBar key={key} label={label} value={scorecard[key] ?? 0} />
        ))}
      </div>
    </div>
  )
}

// ── Diff panel ────────────────────────────────────────────────────────────────

function DiffPanel({ diff, changesSummary }: { diff: ReviewDetail['diff']; changesSummary: string }) {
  return (
    <div className={`card ${styles.panel}`}>
      <h3 className={styles.panelTitle}>
        {diff.is_first_version ? 'First Publication' : 'What Changed'}
      </h3>

      {diff.release_notes && (
        <p className={styles.releaseNotes}>{diff.release_notes}</p>
      )}

      {!diff.is_first_version && (
        <div className={styles.diffSections}>
          {diff.sections_added.length > 0 && (
            <div className={styles.diffGroup}>
              <span className={styles.diffAdded}>+ Added</span>
              <ul>{diff.sections_added.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {diff.sections_removed.length > 0 && (
            <div className={styles.diffGroup}>
              <span className={styles.diffRemoved}>− Removed</span>
              <ul>{diff.sections_removed.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {diff.sections_changed.length > 0 && (
            <div className={styles.diffGroup}>
              <span className={styles.diffChanged}>~ Changed</span>
              <ul>{diff.sections_changed.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      {changesSummary && (
        <p className={styles.changesSummary}>
          <strong>Editor notes:</strong> {changesSummary}
        </p>
      )}
    </div>
  )
}

// ── Approve / Reject form ─────────────────────────────────────────────────────

function DecisionForm({
  topicId,
  runId,
  onDone,
}: {
  topicId: string
  runId: string
  onDone: () => void
}) {
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const qc = useQueryClient()
  const navigate = useNavigate()

  const approve = useMutation({
    mutationFn: () => reviewsApi.submit(topicId, runId, { decision: 'approve', notes }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reviews'] })
      qc.invalidateQueries({ queryKey: ['review', topicId, runId] })
      onDone()
      navigate('/reviews')
    },
    onError: () => setError('Failed to submit approval. Please try again.'),
  })

  const reject = useMutation({
    mutationFn: () => {
      if (!notes.trim()) {
        setError('Please provide notes explaining the rejection.')
        return Promise.reject()
      }
      return reviewsApi.submit(topicId, runId, { decision: 'reject', notes })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reviews'] })
      qc.invalidateQueries({ queryKey: ['review', topicId, runId] })
      navigate('/reviews')
    },
    onError: (e: unknown) => {
      if (e) setError('Failed to submit rejection. Please try again.')
    },
  })

  const busy = approve.isPending || reject.isPending

  return (
    <div className={`card ${styles.panel} ${styles.decisionPanel}`}>
      <h3 className={styles.panelTitle}>Decision</h3>
      <label htmlFor="review-notes">Notes</label>
      <textarea
        id="review-notes"
        rows={4}
        value={notes}
        onChange={(e) => { setNotes(e.target.value); setError('') }}
        placeholder="Optional for approval · Required for rejection"
        className={styles.notesArea}
      />
      {error && <p className="error-msg">{error}</p>}
      <div className={styles.decisionButtons}>
        <button
          className={`btn-primary ${styles.approveBtn}`}
          onClick={() => approve.mutate()}
          disabled={busy}
        >
          {approve.isPending ? <span className="spin" /> : '✓ Approve & Publish'}
        </button>
        <button
          className={`btn-danger`}
          onClick={() => reject.mutate()}
          disabled={busy}
        >
          {reject.isPending ? <span className="spin" /> : '✕ Reject'}
        </button>
      </div>
    </div>
  )
}

// ── Content viewer ────────────────────────────────────────────────────────────

function ContentViewer({ content, sections, wordCount }: {
  content: string
  sections: string[]
  wordCount: number
}) {
  return (
    <div className={`card ${styles.contentCard}`}>
      <div className={styles.contentHeader}>
        <span className={styles.contentMeta}>
          {wordCount.toLocaleString()} words · {sections.length} sections
        </span>
      </div>
      <div className={styles.tocList}>
        {sections.map((s) => (
          <span key={s} className={styles.tocItem}>§ {s}</span>
        ))}
      </div>
      <pre className={styles.contentPre}>{content}</pre>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReviewDetailPage() {
  const { topicId, runId } = useParams<{ topicId: string; runId: string }>()
  const navigate = useNavigate()
  const [decided, setDecided] = useState(false)

  const { data: review, isLoading, error } = useQuery({
    queryKey: ['review', topicId, runId],
    queryFn: () => reviewsApi.get(topicId!, runId!),
    enabled: !!topicId && !!runId,
  })

  if (isLoading) return <div className={styles.center}><span className="spin" /></div>
  if (error || !review) return <p className="error-msg">Failed to load review.</p>

  const isPending = review.review_status === 'PENDING_REVIEW' && !decided
  const statusBadgeClass =
    review.review_status === 'APPROVED' ? 'badge-success' :
    review.review_status === 'REJECTED' ? 'badge-danger' :
    review.review_status === 'TIMED_OUT' ? 'badge-warning' :
    'badge-pending'

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <button className={styles.back} onClick={() => navigate('/reviews')}>
            ← Review Queue
          </button>
          <h1 className={styles.title}>{review.title || 'Draft Review'}</h1>
          <div className={styles.headerMeta}>
            <span className={`badge ${statusBadgeClass}`}>
              {review.review_status.replace('_', ' ')}
            </span>
            {review.run.started_at && (
              <span className={styles.metaItem}>
                Run started {new Date(review.run.started_at).toLocaleString()}
              </span>
            )}
            {review.run.cost_usd_total != null && (
              <span className={styles.metaItem}>
                Cost ${review.run.cost_usd_total.toFixed(4)}
              </span>
            )}
            {review.word_count > 0 && (
              <span className={styles.metaItem}>
                {review.word_count.toLocaleString()} words
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Already decided notice */}
      {!isPending && (
        <div className={`card ${styles.decidedBanner}`}>
          {review.review_status === 'APPROVED' && (
            <span>✓ Approved by {review.reviewer} on {new Date(review.approved_at!).toLocaleString()}</span>
          )}
          {review.review_status === 'REJECTED' && (
            <span>✕ Rejected by {review.reviewer} on {new Date(review.rejected_at!).toLocaleString()}
              {review.notes && ` — "${review.notes}"`}
            </span>
          )}
          {review.review_status === 'TIMED_OUT' && (
            <span>⚠ Review timed out — no action was taken.</span>
          )}
        </div>
      )}

      {/* Main layout: content left, sidebar right */}
      <div className={styles.layout}>
        {/* Left: draft content */}
        <div className={styles.contentCol}>
          <ContentViewer
            content={review.content}
            sections={review.sections}
            wordCount={review.word_count}
          />
        </div>

        {/* Right: diff + scorecard + decision */}
        <div className={styles.sideCol}>
          <DiffPanel diff={review.diff} changesSummary={review.changes_summary} />
          <ScorecardPanel scorecard={review.scorecard} />
          {isPending && (
            <DecisionForm
              topicId={topicId!}
              runId={runId!}
              onDone={() => setDecided(true)}
            />
          )}
        </div>
      </div>
    </div>
  )
}

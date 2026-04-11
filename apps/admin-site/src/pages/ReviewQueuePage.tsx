import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { reviewsApi } from '../api/reviews'
import type { ReviewQueueItem } from '../types'
import styles from './ReviewQueuePage.module.css'

function timeUntil(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'Expired'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  if (h > 0) return `${h}h ${m}m remaining`
  return `${m}m remaining`
}

function urgencyClass(iso: string): string {
  const h = (new Date(iso).getTime() - Date.now()) / 3_600_000
  if (h <= 0) return styles.expired
  if (h < 12) return styles.urgent
  return ''
}

function ReviewCard({ item }: { item: ReviewQueueItem }) {
  const navigate = useNavigate()
  const until = timeUntil(item.timeout_at)
  const cls = urgencyClass(item.timeout_at)

  return (
    <div className={`card ${styles.card}`}>
      <div className={styles.cardMain}>
        <span className={styles.topicTitle}>{item.title || item.topic_id}</span>
        <span className={styles.runId}>Run {item.run_id.slice(0, 8)}&hellip;</span>
      </div>
      <div className={styles.cardMeta}>
        <span className={`badge badge-pending`}>Pending review</span>
        <span className={`${styles.timeout} ${cls}`}>{until}</span>
      </div>
      <button
        className="btn-primary"
        onClick={() => navigate(`/topics/${item.topic_id}/review/${item.run_id}`)}
      >
        Review →
      </button>
    </div>
  )
}

export default function ReviewQueuePage() {
  const { data: reviews = [], isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ['reviews'],
    queryFn: reviewsApi.list,
    refetchInterval: 30_000,
  })

  if (isLoading) return <div className={styles.center}><span className="spin" /></div>
  if (error)     return <p className="error-msg">Failed to load review queue.</p>

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Review Queue</h1>
          <p className={styles.subtitle}>
            {reviews.length === 0
              ? 'No pending reviews'
              : `${reviews.length} draft${reviews.length !== 1 ? 's' : ''} awaiting approval`}
            {dataUpdatedAt ? ` · updated ${new Date(dataUpdatedAt).toLocaleTimeString()}` : ''}
          </p>
        </div>
      </div>

      {reviews.length === 0 ? (
        <div className={`card ${styles.empty}`}>
          <p>All caught up — no pending drafts to review.</p>
        </div>
      ) : (
        <div className={styles.list}>
          {reviews.map((item) => (
            <ReviewCard key={`${item.topic_id}#${item.run_id}`} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

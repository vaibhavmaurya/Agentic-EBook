import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { topicsApi } from '../api/topics'
import type { TopicListItem, RunStatus } from '../types'
import styles from './TopicListPage.module.css'

// ── Status badge ─────────────────────────────────────────────────────────────

function statusBadge(status: RunStatus | undefined) {
  if (!status) return <span className="badge badge-neutral">No runs</span>
  const map: Record<RunStatus, string> = {
    PENDING:          'badge-neutral',
    RUNNING:          'badge-warning',
    WAITING_APPROVAL: 'badge-pending',
    APPROVED:         'badge-success',
    REJECTED:         'badge-danger',
    FAILED:           'badge-danger',
    TIMED_OUT:        'badge-warning',
  }
  return <span className={`badge ${map[status]}`}>{status.replace('_', ' ')}</span>
}

// ── Sortable row ──────────────────────────────────────────────────────────────

function TopicRow({
  topic,
  onEdit,
  onDelete,
  onTrigger,
  triggering,
}: {
  topic: TopicListItem
  onEdit: () => void
  onDelete: () => void
  onTrigger: () => void
  triggering: boolean
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: topic.topic_id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div ref={setNodeRef} style={style} className={`card ${styles.row}`}>
      <span className={styles.handle} {...attributes} {...listeners} title="Drag to reorder">
        ⠿
      </span>

      <div className={styles.rowInfo}>
        <span className={styles.rowTitle}>{topic.title}</span>
        <span className={styles.rowDesc}>{topic.description}</span>
      </div>

      <div className={styles.rowMeta}>
        <span className={styles.scheduleTag}>{topic.schedule_type}</span>
        {statusBadge(topic.last_run?.status)}
      </div>

      <div className={styles.rowActions}>
        <button className="btn-secondary" onClick={onEdit}>Edit</button>
        <button
          className="btn-primary"
          onClick={onTrigger}
          disabled={triggering}
        >
          {triggering ? <span className="spin" /> : 'Run'}
        </button>
        <button className="btn-danger" onClick={onDelete}>Delete</button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TopicListPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [triggeringId, setTriggeringId] = useState<string | null>(null)
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null)

  const { data: topics = [], isLoading, error } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
  })

  // Maintain local order for optimistic drag-and-drop
  const [localOrder, setLocalOrder] = useState<TopicListItem[] | null>(null)
  const displayed = localOrder ?? topics

  const deleteMutation = useMutation({
    mutationFn: topicsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topics'] }),
  })

  const reorderMutation = useMutation({
    mutationFn: (ids: string[]) => topicsApi.reorder(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      setLocalOrder(null)
    },
  })

  const sensors = useSensors(useSensor(PointerSensor))

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = displayed.findIndex((t) => t.topic_id === active.id)
    const newIndex = displayed.findIndex((t) => t.topic_id === over.id)
    const reordered = arrayMove(displayed, oldIndex, newIndex)
    setLocalOrder(reordered)
    reorderMutation.mutate(reordered.map((t) => t.topic_id))
  }

  const handleTrigger = async (topicId: string) => {
    setTriggeringId(topicId)
    setTriggerMsg(null)
    try {
      const res = await topicsApi.trigger(topicId)
      setTriggerMsg(`Run started — ID: ${res.run_id}`)
    } catch {
      setTriggerMsg('Failed to start run.')
    } finally {
      setTriggeringId(null)
    }
  }

  const handleDelete = (topicId: string, title: string) => {
    if (!confirm(`Delete topic "${title}"? This cannot be undone.`)) return
    deleteMutation.mutate(topicId)
  }

  if (isLoading) return <div className={styles.center}><span className="spin" /></div>
  if (error)     return <p className="error-msg">Failed to load topics.</p>

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Topics</h1>
          <p className={styles.subtitle}>
            {topics.length} topic{topics.length !== 1 ? 's' : ''} — drag to reorder
          </p>
        </div>
        <button className="btn-primary" onClick={() => navigate('/topics/new')}>
          + New topic
        </button>
      </div>

      {triggerMsg && (
        <div className={styles.toast}>{triggerMsg}</div>
      )}

      {displayed.length === 0 ? (
        <div className={`card ${styles.empty}`}>
          <p>No topics yet. Create your first one to get started.</p>
          <button className="btn-primary" onClick={() => navigate('/topics/new')}>
            Create topic
          </button>
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={displayed.map((t) => t.topic_id)} strategy={verticalListSortingStrategy}>
            <div className={styles.list}>
              {displayed.map((topic) => (
                <TopicRow
                  key={topic.topic_id}
                  topic={topic}
                  onEdit={() => navigate(`/topics/${topic.topic_id}/edit`)}
                  onDelete={() => handleDelete(topic.topic_id, topic.title)}
                  onTrigger={() => handleTrigger(topic.topic_id)}
                  triggering={triggeringId === topic.topic_id}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  )
}

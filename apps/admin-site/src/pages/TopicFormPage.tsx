import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { topicsApi } from '../api/topics'
import type { ScheduleType, TopicCreatePayload } from '../types'
import styles from './TopicFormPage.module.css'

const SCHEDULE_OPTIONS: { value: ScheduleType; label: string }[] = [
  { value: 'manual',  label: 'Manual only' },
  { value: 'daily',   label: 'Daily (06:00 UTC)' },
  { value: 'weekly',  label: 'Weekly (Monday 06:00 UTC)' },
  { value: 'custom',  label: 'Custom cron' },
]

export default function TopicFormPage() {
  const navigate = useNavigate()
  const { topicId } = useParams<{ topicId: string }>()
  const isEdit = Boolean(topicId)
  const qc = useQueryClient()

  // Form state
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [instructions, setInstructions] = useState('')
  const [subtopicsRaw, setSubtopicsRaw] = useState('') // comma-separated
  const [scheduleType, setScheduleType] = useState<ScheduleType>('manual')
  const [cronExpression, setCronExpression] = useState('')
  const [formError, setFormError] = useState('')

  // Load existing topic when editing
  const { data: existing, isLoading: loadingExisting } = useQuery({
    queryKey: ['topic', topicId],
    queryFn: () => topicsApi.get(topicId!),
    enabled: isEdit,
  })

  useEffect(() => {
    if (existing) {
      setTitle(existing.title)
      setDescription(existing.description)
      setInstructions(existing.instructions)
      setSubtopicsRaw(existing.subtopics.join(', '))
      setScheduleType(existing.schedule_type)
      setCronExpression(existing.cron_expression ?? '')
    }
  }, [existing])

  const createMutation = useMutation({
    mutationFn: (p: TopicCreatePayload) => topicsApi.create(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      navigate('/topics')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (p: Partial<TopicCreatePayload>) => topicsApi.update(topicId!, p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      qc.invalidateQueries({ queryKey: ['topic', topicId] })
      navigate('/topics')
    },
  })

  const isPending = createMutation.isPending || updateMutation.isPending

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setFormError('')

    if (scheduleType === 'custom' && !cronExpression.trim()) {
      setFormError('Cron expression is required for custom schedule.')
      return
    }

    const payload: TopicCreatePayload = {
      title: title.trim(),
      description: description.trim(),
      instructions: instructions.trim(),
      subtopics: subtopicsRaw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      schedule_type: scheduleType,
      cron_expression: scheduleType === 'custom' ? cronExpression.trim() : null,
    }

    try {
      if (isEdit) {
        await updateMutation.mutateAsync(payload)
      } else {
        await createMutation.mutateAsync(payload)
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Something went wrong.'
      setFormError(msg)
    }
  }

  if (isEdit && loadingExisting) {
    return <div className={styles.center}><span className="spin" /></div>
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button className="btn-secondary" onClick={() => navigate('/topics')}>
          ← Back
        </button>
        <h1 className={styles.title}>{isEdit ? 'Edit topic' : 'New topic'}</h1>
      </div>

      <div className={`card ${styles.formCard}`}>
        <form onSubmit={handleSubmit} className={styles.form}>

          <div className={styles.field}>
            <label htmlFor="title">Title *</label>
            <input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Introduction to LLMs"
              required
              minLength={3}
              maxLength={200}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="description">Description *</label>
            <textarea
              id="description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A brief overview shown on the public site."
              required
              minLength={10}
              maxLength={2000}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="instructions">
              Agent instructions *
              <span className={styles.hint}> — injected into every agent prompt for this topic</span>
            </label>
            <textarea
              id="instructions"
              rows={5}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. Focus on practical applications. Avoid heavy math. Use diagrams for architecture explanations."
              required
              minLength={10}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="subtopics">
              Subtopics
              <span className={styles.hint}> — comma-separated section headings (optional)</span>
            </label>
            <input
              id="subtopics"
              value={subtopicsRaw}
              onChange={(e) => setSubtopicsRaw(e.target.value)}
              placeholder="e.g. Transformer architecture, Training at scale, Prompt engineering"
            />
          </div>

          <div className={styles.row2}>
            <div className={styles.field}>
              <label htmlFor="schedule">Schedule</label>
              <select
                id="schedule"
                value={scheduleType}
                onChange={(e) => setScheduleType(e.target.value as ScheduleType)}
              >
                {SCHEDULE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {scheduleType === 'custom' && (
              <div className={styles.field}>
                <label htmlFor="cron">
                  Cron expression *
                  <span className={styles.hint}> — AWS EventBridge format</span>
                </label>
                <input
                  id="cron"
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  placeholder="cron(0 9 ? * MON *)"
                  required
                />
              </div>
            )}
          </div>

          {formError && <p className="error-msg">{formError}</p>}

          <div className={styles.actions}>
            <button type="button" className="btn-secondary" onClick={() => navigate('/topics')}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isPending}>
              {isPending ? <span className="spin" /> : isEdit ? 'Save changes' : 'Create topic'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

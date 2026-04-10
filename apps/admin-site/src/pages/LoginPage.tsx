import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/topics')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={`card ${styles.card}`}>
        <div className={styles.header}>
          <span className={styles.icon}>📖</span>
          <h1 className={styles.title}>Ebook Admin</h1>
          <p className={styles.subtitle}>Sign in to manage your ebook platform</p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />
          </div>

          {error && <p className="error-msg">{error}</p>}

          <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? <span className="spin" /> : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

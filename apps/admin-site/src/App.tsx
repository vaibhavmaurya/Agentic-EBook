import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import Layout from './components/Layout'
import TopicListPage from './pages/TopicListPage'
import TopicFormPage from './pages/TopicFormPage'
import ReviewQueuePage from './pages/ReviewQueuePage'
import ReviewDetailPage from './pages/ReviewDetailPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/topics" replace />} />
        <Route path="topics" element={<TopicListPage />} />
        <Route path="topics/new" element={<TopicFormPage />} />
        <Route path="topics/:topicId/edit" element={<TopicFormPage />} />
        <Route path="reviews" element={<ReviewQueuePage />} />
        <Route path="topics/:topicId/review/:runId" element={<ReviewDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

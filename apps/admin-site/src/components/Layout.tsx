import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import styles from './Layout.module.css'

export default function Layout() {
  const { email, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className={styles.shell}>
      <nav className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandIcon}>📖</span>
          <span className={styles.brandName}>Ebook Admin</span>
        </div>

        <ul className={styles.nav}>
          <li>
            <NavLink
              to="/topics"
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.active : ''}`
              }
            >
              Topics
            </NavLink>
          </li>
        </ul>

        <div className={styles.user}>
          <span className={styles.userEmail}>{email}</span>
          <button className="btn-secondary" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </nav>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

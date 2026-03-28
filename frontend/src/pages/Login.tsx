import { useState, FormEvent } from 'react'
import { api, LoginResponse } from '../api'
import styles from './Login.module.css'

interface Props {
  onLogin: (email: string, token: string) => void
}

export default function LoginPage({ onLogin }: Props) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email || !password) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.post<LoginResponse>('/login', { email, password })
      onLogin(email, data.token)
    } catch (err: any) {
      setError(err.message || 'Connexion impossible')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        {/* Logo */}
        <div className={styles.logo}>AMOKK</div>
        <p className={styles.subtitle}>Coach IA pour League of Legends</p>

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor="email">Identifiant</label>
            <input
              id="email"
              type="text"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="admin"
              autoFocus
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && <div className={styles.error}>{error}</div>}

          <button type="submit" className={styles.btn} disabled={loading}>
            {loading ? 'En cours...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}

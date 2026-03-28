import { useState, useEffect, useCallback } from 'react'
import { api, LocalData, GameState } from '../api'
import Settings from './Settings'
import styles from './Dashboard.module.css'

const ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY'] as const
type Role = typeof ROLES[number]
type Page = 'coach' | 'settings'

const ROLE_LABELS: Record<Role, string> = {
  TOP: 'Top', JUNGLE: 'Jungle', MIDDLE: 'Mid', BOTTOM: 'Bot', UTILITY: 'Support'
}

export default function Dashboard() {
  const [page, setPage]                 = useState<Page>('coach')
  const [localData, setLocalData]       = useState<LocalData | null>(null)
  const [gameState, setGameState]       = useState<GameState | null>(null)
  const [coachActive, setCoachActive]   = useState(false)
  const [selectedRole, setSelectedRole] = useState<Role>('MIDDLE')
  const [volume, setVolume]             = useState(67)
  const [testing, setTesting]           = useState(false)
  const [statusMsg, setStatusMsg]       = useState<string | null>(null)

  // Charger données locales au démarrage
  useEffect(() => {
    api.get<LocalData>('/get_local_data').then(data => {
      setLocalData(data)
      setVolume(data.volume)
    }).catch(() => {})
  }, [])

  // Polling état de jeu toutes les 2s
  useEffect(() => {
    const poll = async () => {
      try {
        const state = await api.get<GameState>('/game/state')
        setGameState(state)
        // Auto-détecter le rôle depuis l'API LoL si disponible
        if (state.active && state.player?.role) {
          const detectedRole = state.player.role as Role
          if (ROLES.includes(detectedRole)) {
            setSelectedRole(detectedRole)
          }
        }
      } catch {}
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleVolumeChange = useCallback(async (val: number) => {
    setVolume(val)
    try {
      await api.post('/volume', { volume: val })
    } catch {}
  }, [])

  const handleToggleCoach = useCallback(async () => {
    if (!coachActive) {
      try {
        await api.post('/coaching/start', { role: selectedRole })
        setCoachActive(true)
        setStatusMsg('Coach activé')
      } catch {
        setStatusMsg('Erreur au démarrage du coach')
      }
    } else {
      try {
        await api.post('/coaching/stop', {})
        setCoachActive(false)
        setStatusMsg('Coach désactivé')
      } catch {}
    }
    setTimeout(() => setStatusMsg(null), 3000)
  }, [coachActive, selectedRole])

  const handleTestVolume = useCallback(async () => {
    setTesting(true)
    try {
      await api.post('/tts/test', {})
    } catch {}
    setTimeout(() => setTesting(false), 3000)
  }, [])

  const gameTime = gameState?.active ? gameState.game_time ?? 0 : 0
  const minutes = Math.floor(gameTime / 60)
  const seconds = Math.floor(gameTime % 60)

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.logo}>Coach Carter</div>
        <nav className={styles.nav}>
          <span
            className={`${styles.navItem} ${page === 'coach' ? styles.navActive : ''}`}
            onClick={() => setPage('coach')}
          >Coach</span>
          <span
            className={`${styles.navItem} ${page === 'settings' ? styles.navActive : ''}`}
            onClick={() => setPage('settings')}
          >Paramètres</span>
        </nav>
      </aside>

      {/* Main */}
      <main className={styles.main}>

        {/* Page Paramètres */}
        {page === 'settings' && <Settings />}

        {page === 'coach' && <>

        {/* Header */}
        <div className={styles.header}>
          <h1>Configurez votre coach</h1>
          {statusMsg && <span className={styles.statusBadge}>{statusMsg}</span>}
        </div>

        {/* Statut jeu */}
        <div className={`${styles.card} ${styles.gameStatus}`}>
          <div className={styles.cardLabel}>Statut du Coach</div>
          <div className={styles.gameStatusContent}>
            <div className={`${styles.statusDot} ${gameState?.active ? styles.dotActive : styles.dotIdle}`} />
            <span className={styles.statusText}>
              {gameState?.active
                ? `En jeu — ${minutes}:${String(seconds).padStart(2, '0')}`
                : 'En attente d\'une partie'}
            </span>
          </div>
          {gameState?.active && gameState.player && (
            <div className={styles.playerInfo}>
              <span className={styles.champion}>{gameState.player.champion}</span>
              <span className={styles.kda}>
                {gameState.player.kills}/{gameState.player.deaths}/{gameState.player.assists}
              </span>
              <span className={styles.cs}>{gameState.player.cs} CS</span>
              {gameState.position?.description && (
                <span className={styles.zone}>{gameState.position.description}</span>
              )}
            </div>
          )}
        </div>

        {/* Sélection rôle */}
        <div className={styles.card}>
          <div className={styles.cardLabel}>Jouer les matchups</div>
          <div className={styles.roleGrid}>
            {ROLES.map(r => (
              <button
                key={r}
                className={`${styles.roleBtn} ${selectedRole === r ? styles.roleBtnActive : ''}`}
                onClick={() => setSelectedRole(r)}
              >
                {ROLE_LABELS[r]}
              </button>
            ))}
          </div>
        </div>

        {/* Toggle coach */}
        <div className={styles.card}>
          <div className={styles.cardLabel}>Activez le coach</div>
          <p className={styles.cardDesc}>
            {coachActive
              ? 'Basculez l\'interrupteur ci-dessus pour désactiver le coaching'
              : 'Activez le coach pour commencer'}
          </p>
          <div className={styles.toggleRow}>
            <button
              className={`${styles.toggleBtn} ${coachActive ? styles.toggleActive : ''}`}
              onClick={handleToggleCoach}
            >
              <span className={styles.toggleThumb} />
            </button>
            <span className={styles.toggleLabel}>
              {coachActive ? 'Coach actif' : 'Coach désactivé'}
            </span>
          </div>
        </div>

        {/* Volume */}
        <div className={styles.card}>
          <div className={styles.cardLabel}>Test du niveau de volume</div>
          <p className={styles.cardDesc}>Ajustez le niveau du volume de la voix</p>
          <div className={styles.volumeRow}>
            <input
              type="range"
              min={0}
              max={100}
              value={volume}
              className={styles.slider}
              onChange={e => handleVolumeChange(Number(e.target.value))}
            />
            <span className={styles.volumeValue}>{volume}%</span>
          </div>
          <button
            className={styles.testBtn}
            onClick={handleTestVolume}
            disabled={testing}
          >
            {testing ? 'En cours...' : 'Tester le Volume'}
          </button>
        </div>

        {/* Objectifs (si partie active) */}
        {gameState?.active && gameState.objectives && (
          <div className={styles.card}>
            <div className={styles.cardLabel}>Objectifs</div>
            <ObjectiveTimers objectives={gameState.objectives} gameTime={gameTime} />
          </div>
        )}

        </>}

      </main>
    </div>
  )
}

function ObjectiveTimers({ objectives, gameTime }: {
  objectives: NonNullable<GameState['objectives']>
  gameTime: number
}) {
  const fmt = (secs: number | null) => {
    if (secs === null) return '—'
    if (secs <= 0) return 'Disponible !'
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  return (
    <div className={styles.objectivesGrid}>
      {[
        { label: 'Dragon', data: objectives.dragon },
        { label: 'Baron', data: objectives.baron },
        { label: 'Herald', data: objectives.herald },
      ].map(({ label, data }) => (
        <div key={label} className={styles.objectiveItem}>
          <div className={styles.objectiveName}>{label}</div>
          <div className={styles.objectiveKills}>{data.kills} kills</div>
          <div className={`${styles.objectiveTimer} ${data.time_until_spawn !== null && data.time_until_spawn <= 60 ? styles.timerUrgent : ''}`}>
            {fmt(data.time_until_spawn)}
          </div>
        </div>
      ))}
    </div>
  )
}

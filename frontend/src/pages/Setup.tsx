import { useState } from 'react'
import styles from './Setup.module.css'

interface Props {
  onComplete: () => void
}

export default function Setup({ onComplete }: Props) {
  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey, setOpenaiKey]       = useState('')
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState<string | null>(null)

  const openLink = (url: string) => {
    if (window.electronAPI) window.electronAPI.openExternal(url)
    else window.open(url, '_blank')
  }

  const handleSave = async () => {
    if (!anthropicKey.trim() || !openaiKey.trim()) {
      setError('Les deux clés sont requises.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      if (window.electronAPI) {
        await window.electronAPI.setApiKeys({
          anthropicKey: anthropicKey.trim(),
          openaiKey: openaiKey.trim(),
        })
      } else {
        localStorage.setItem('cc_anthropic_key', anthropicKey.trim())
        localStorage.setItem('cc_openai_key', openaiKey.trim())
      }
      onComplete()
    } catch {
      setError('Erreur lors de la sauvegarde.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logo}>COACH CARTER</div>
        <p className={styles.subtitle}>Configuration des clés API</p>
        <p className={styles.hint}>
          Tes clés sont stockées localement sur ton PC et ne sont jamais envoyées à des serveurs tiers.
        </p>

        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Anthropic (Claude)</span>
            <button className={styles.linkBtn} onClick={() => openLink('https://console.anthropic.com/settings/keys')}>
              Obtenir une clé →
            </button>
          </div>
          <input
            className={styles.input}
            type="password"
            placeholder="sk-ant-..."
            value={anthropicKey}
            onChange={e => setAnthropicKey(e.target.value)}
            autoComplete="off"
          />
        </div>

        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>OpenAI (TTS)</span>
            <button className={styles.linkBtn} onClick={() => openLink('https://platform.openai.com/api-keys')}>
              Obtenir une clé →
            </button>
          </div>
          <input
            className={styles.input}
            type="password"
            placeholder="sk-..."
            value={openaiKey}
            onChange={e => setOpenaiKey(e.target.value)}
            autoComplete="off"
          />
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <button className={styles.btn} onClick={handleSave} disabled={loading}>
          {loading ? 'Démarrage...' : 'Enregistrer et lancer'}
        </button>
      </div>
    </div>
  )
}

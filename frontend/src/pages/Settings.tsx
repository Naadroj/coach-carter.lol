import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import styles from './Settings.module.css'

const TRIGGER_LABELS: Record<string, string> = {
  creepscore_alert:                   'Alerte farm',
  ward_score_alert:                   'Alerte vision',
  back_alert:                         'Rappel retour en base',
  item_buy_advice:                    "Conseil achat d'item",
  global_strategic_advice:            'Conseil stratégique global',
  death_advice:                       'Conseil après mort',
  dragon_death_advice:                'Dragon perdu',
  baron_death_advice:                 'Baron perdu',
  herald_death_advice:                'Héraut perdu',
  dragon_next_spawn_alert:            'Dragon — alertes de spawn',
  baron_next_spawn_alert:             'Baron — alertes de spawn',
  herald_next_spawn_alert:            'Héraut — alertes de spawn',
  champion_killed_matchup_advice:     'Conseil après kill ennemi',
  first_turret_killed_on_lane_advice: 'Première tourelle détruite',
  jungler_tracking:                        'Tracking jungler adverse',
  dead_reminder:                           'Alerte pendant la mort (5s)',
  base_reminder:                           'Alerte à la base (5s)',
  first_turret_killed_on_toplane_advice:   '1ère tourelle voie du haut détruite',
  first_turret_killed_on_midlane_advice:   '1ère tourelle voie du milieu détruite',
  first_turret_killed_on_botlane_advice:   '1ère tourelle voie du bas détruite',
  endgame_summary:                         'Résumé fin de partie',
}

const SPAWN_TRIGGERS = new Set([
  'dragon_next_spawn_alert',
  'baron_next_spawn_alert',
  'herald_next_spawn_alert',
])

interface TriggerConfig {
  name: string
  enabled: boolean
  cooldown: number
  spawn_phases?: number[]
}

export default function Settings() {
  const [triggers, setTriggers] = useState<TriggerConfig[]>([])
  const [saving, setSaving]     = useState<string | null>(null)
  const [saved, setSaved]       = useState<string | null>(null)
  const [maskedKeys, setMaskedKeys]     = useState<{ anthropicKey: string; openaiKey: string } | null>(null)
  const [editingKeys, setEditingKeys]   = useState(false)
  const [newAnthKey, setNewAnthKey]     = useState('')
  const [newOaiKey, setNewOaiKey]       = useState('')
  const [savingKeys, setSavingKeys]     = useState(false)
  const [usage, setUsage]               = useState<{ anthropic: { input_tokens: number; output_tokens: number; cost_usd: number }; openai_tts: { chars: number; cost_usd: number }; total_cost_usd: number } | null>(null)

  useEffect(() => {
    api.get<{ triggers: TriggerConfig[] }>('/triggers/config')
      .then(d => setTriggers(d.triggers))
      .catch(() => {})
  }, [])

  useEffect(() => {
    window.electronAPI?.getApiKeysMasked().then(setMaskedKeys).catch(() => {})
    api.get<{ anthropic: { input_tokens: number; output_tokens: number; cost_usd: number }; openai_tts: { chars: number; cost_usd: number }; total_cost_usd: number }>('/usage').then(setUsage).catch(() => {})
  }, [])

  const saveKeys = async () => {
    if (!newAnthKey.trim() || !newOaiKey.trim()) return
    setSavingKeys(true)
    try {
      if (window.electronAPI) {
        await window.electronAPI.setApiKeys({ anthropicKey: newAnthKey.trim(), openaiKey: newOaiKey.trim() })
        const masked = await window.electronAPI.getApiKeysMasked()
        setMaskedKeys(masked)
      }
      setEditingKeys(false)
    } catch {}
    setSavingKeys(false)
  }

  const updateTrigger = useCallback(async (name: string, patch: Partial<TriggerConfig>) => {
    setTriggers(prev => prev.map(t => t.name === name ? { ...t, ...patch } : t))
    setSaving(name)
    try {
      await api.post('/triggers/config', { name, ...patch })
      setSaved(name)
      setTimeout(() => setSaved(null), 1500)
    } catch {}
    setSaving(null)
  }, [])

  const fmtCooldown = (s: number) => {
    if (s >= 1_000_000) return '—'
    if (s >= 60) return `${Math.round(s / 60)} min`
    return `${s} s`
  }

  const fmtPhase = (s: number) => s >= 60 ? `${s / 60} min` : `${s} s`

  const updatePhase = (trigger: TriggerConfig, idx: number, val: number) => {
    const phases = [...(trigger.spawn_phases ?? [])]
    phases[idx] = val
    updateTrigger(trigger.name, { spawn_phases: phases })
  }

  const removePhase = (trigger: TriggerConfig, idx: number) => {
    const phases = (trigger.spawn_phases ?? []).filter((_, i) => i !== idx)
    updateTrigger(trigger.name, { spawn_phases: phases })
  }

  const addPhase = (trigger: TriggerConfig) => {
    const phases = [...(trigger.spawn_phases ?? []), 30]
    updateTrigger(trigger.name, { spawn_phases: phases })
  }

  // Séparer triggers classiques et triggers spawn
  const standardTriggers = triggers.filter(t => !SPAWN_TRIGGERS.has(t.name))
  const spawnTriggers     = triggers.filter(t => SPAWN_TRIGGERS.has(t.name))

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Paramètres du coaching</h1>
        <p className={styles.subtitle}>Activez ou désactivez chaque alerte et ajustez leur fréquence.</p>
      </div>

      {/* ── Triggers classiques ── */}
      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.colName}>Alerte</th>
              <th className={styles.colCooldown}>Fréquence min.</th>
              <th className={styles.colToggle}>Activé</th>
            </tr>
          </thead>
          <tbody>
            {standardTriggers.map(t => (
              <tr key={t.name} className={`${styles.row} ${!t.enabled ? styles.rowDisabled : ''}`}>
                <td className={styles.colName}>
                  <span className={styles.triggerLabel}>{TRIGGER_LABELS[t.name] ?? t.name}</span>
                  {saved === t.name && <span className={styles.savedBadge}>✓</span>}
                </td>
                <td className={styles.colCooldown}>
                  <div className={styles.cooldownRow}>
                    <input
                      type="number"
                      className={styles.cooldownInput}
                      value={t.cooldown >= 1_000_000 ? '' : t.cooldown}
                      min={10} max={3600}
                      disabled={!t.enabled || saving === t.name}
                      placeholder="—"
                      onChange={e => {
                        const v = parseInt(e.target.value)
                        if (!isNaN(v) && v >= 10) updateTrigger(t.name, { cooldown: v })
                      }}
                    />
                    <span className={styles.cooldownUnit}>
                      {t.cooldown < 1_000_000 ? fmtCooldown(t.cooldown) : ''}
                    </span>
                  </div>
                </td>
                <td className={styles.colToggle}>
                  <button
                    className={`${styles.toggle} ${t.enabled ? styles.toggleOn : ''}`}
                    onClick={() => updateTrigger(t.name, { enabled: !t.enabled })}
                    disabled={saving === t.name}
                  >
                    <span className={styles.toggleThumb} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Alertes spawn escaladées ── */}
      <div className={styles.header}>
        <h1>Alertes objectifs</h1>
        <p className={styles.subtitle}>
          Définissez à quels moments (avant le spawn) l'IA vous alerte — de la plus lointaine à la plus proche.
        </p>
      </div>

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.colName}>Objectif</th>
              <th style={{ width: '60%' }}>Phases d'alerte (secondes avant spawn)</th>
              <th className={styles.colToggle}>Activé</th>
            </tr>
          </thead>
          <tbody>
            {spawnTriggers.map(t => (
              <tr key={t.name} className={`${styles.row} ${!t.enabled ? styles.rowDisabled : ''}`}>
                <td className={styles.colName}>
                  <span className={styles.triggerLabel}>{TRIGGER_LABELS[t.name] ?? t.name}</span>
                  {saved === t.name && <span className={styles.savedBadge}>✓</span>}
                </td>
                <td>
                  <div className={styles.phasesRow}>
                    {(t.spawn_phases ?? []).slice().sort((a, b) => b - a).map((phase, i) => (
                      <div key={i} className={styles.phaseTag}>
                        <input
                          type="number"
                          className={styles.phaseInput}
                          value={phase}
                          min={5} max={300}
                          disabled={!t.enabled || saving === t.name}
                          onChange={e => {
                            const v = parseInt(e.target.value)
                            if (!isNaN(v) && v >= 5) updatePhase(t, i, v)
                          }}
                        />
                        <span className={styles.phaseLabel}>{fmtPhase(phase)}</span>
                        <button
                          className={styles.phaseRemove}
                          onClick={() => removePhase(t, i)}
                          disabled={!t.enabled || saving === t.name}
                          title="Supprimer cette phase"
                        >×</button>
                      </div>
                    ))}
                    <button
                      className={styles.phaseAdd}
                      onClick={() => addPhase(t)}
                      disabled={!t.enabled || saving === t.name}
                    >+ Ajouter</button>
                  </div>
                </td>
                <td className={styles.colToggle}>
                  <button
                    className={`${styles.toggle} ${t.enabled ? styles.toggleOn : ''}`}
                    onClick={() => updateTrigger(t.name, { enabled: !t.enabled })}
                    disabled={saving === t.name}
                  >
                    <span className={styles.toggleThumb} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Clés API ── */}
      <div className={styles.header}>
        <h1>Clés API</h1>
        <p className={styles.subtitle}>Stockées localement — jamais transmises à des serveurs tiers.</p>
      </div>
      <div className={styles.card}>
        {!editingKeys ? (
          <table className={styles.table}>
            <tbody>
              <tr className={styles.row}>
                <td className={styles.colName}><span className={styles.triggerLabel}>Anthropic (Claude)</span></td>
                <td className={styles.colCooldown} style={{ fontFamily: 'monospace', color: '#6b7a99' }}>{maskedKeys?.anthropicKey || '—'}</td>
                <td className={styles.colToggle}>
                  <button className={styles.phaseAdd} onClick={() => { setEditingKeys(true); setNewAnthKey(''); setNewOaiKey('') }}>Modifier</button>
                </td>
              </tr>
              <tr className={styles.row}>
                <td className={styles.colName}><span className={styles.triggerLabel}>OpenAI (TTS)</span></td>
                <td className={styles.colCooldown} style={{ fontFamily: 'monospace', color: '#6b7a99' }}>{maskedKeys?.openaiKey || '—'}</td>
                <td className={styles.colToggle}></td>
              </tr>
            </tbody>
          </table>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '8px 0' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '6px' }}>Clé Anthropic</div>
              <input type="password" placeholder="sk-ant-..." value={newAnthKey} onChange={e => setNewAnthKey(e.target.value)}
                style={{ width: '100%', background: '#0a0e1a', border: '1px solid #1e2a45', borderRadius: '6px', padding: '8px 10px', color: '#e8e0d0', fontFamily: 'monospace', fontSize: '13px', outline: 'none' }} />
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '6px' }}>Clé OpenAI</div>
              <input type="password" placeholder="sk-..." value={newOaiKey} onChange={e => setNewOaiKey(e.target.value)}
                style={{ width: '100%', background: '#0a0e1a', border: '1px solid #1e2a45', borderRadius: '6px', padding: '8px 10px', color: '#e8e0d0', fontFamily: 'monospace', fontSize: '13px', outline: 'none' }} />
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className={styles.phaseAdd} onClick={saveKeys} disabled={savingKeys}>{savingKeys ? 'Enregistrement...' : 'Enregistrer'}</button>
              <button className={styles.phaseAdd} onClick={() => setEditingKeys(false)}>Annuler</button>
            </div>
          </div>
        )}
      </div>

      {/* ── Consommation API ── */}
      <div className={styles.header}>
        <h1>Consommation API</h1>
        <p className={styles.subtitle}>Estimations depuis le dernier démarrage de l'application.</p>
      </div>
      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr><th className={styles.colName}>Service</th><th className={styles.colCooldown}>Utilisation</th><th className={styles.colCooldown}>Coût estimé</th><th className={styles.colToggle}></th></tr>
          </thead>
          <tbody>
            <tr className={styles.row}>
              <td className={styles.colName}><span className={styles.triggerLabel}>Anthropic Claude</span></td>
              <td className={styles.colCooldown} style={{ fontSize: '12px', color: '#6b7a99' }}>
                {usage ? `${usage.anthropic.input_tokens.toLocaleString()} in / ${usage.anthropic.output_tokens.toLocaleString()} out tokens` : '—'}
              </td>
              <td className={styles.colCooldown} style={{ color: '#c89b3c' }}>
                {usage ? `$${usage.anthropic.cost_usd.toFixed(4)}` : '—'}
              </td>
              <td className={styles.colToggle}>
                <button className={styles.phaseAdd} onClick={() => window.electronAPI?.openExternal('https://console.anthropic.com/settings/plans')}>Recharger</button>
              </td>
            </tr>
            <tr className={styles.row}>
              <td className={styles.colName}><span className={styles.triggerLabel}>OpenAI TTS</span></td>
              <td className={styles.colCooldown} style={{ fontSize: '12px', color: '#6b7a99' }}>
                {usage ? `${usage.openai_tts.chars.toLocaleString()} caractères` : '—'}
              </td>
              <td className={styles.colCooldown} style={{ color: '#c89b3c' }}>
                {usage ? `$${usage.openai_tts.cost_usd.toFixed(4)}` : '—'}
              </td>
              <td className={styles.colToggle}>
                <button className={styles.phaseAdd} onClick={() => window.electronAPI?.openExternal('https://platform.openai.com/settings/organization/billing/overview')}>Recharger</button>
              </td>
            </tr>
            {usage && (
              <tr className={styles.row}>
                <td className={styles.colName} style={{ fontWeight: 700 }}>Total</td>
                <td></td>
                <td className={styles.colCooldown} style={{ color: '#c89b3c', fontWeight: 700 }}>
                  ${usage.total_cost_usd.toFixed(4)}
                </td>
                <td></td>
              </tr>
            )}
          </tbody>
        </table>
        <p style={{ fontSize: '11px', color: '#4a5568', marginTop: '12px', padding: '0 4px' }}>
          Tarifs estimés : Claude Haiku ~$1/1M tokens input, $5/1M output · OpenAI TTS tts-1 ~$15/1M caractères
        </p>
      </div>
    </div>
  )
}

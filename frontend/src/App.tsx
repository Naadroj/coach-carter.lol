import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import LoadingPage from './pages/Loading'
import Setup from './pages/Setup'
import UpdateBanner from './components/UpdateBanner'

type Screen = 'loading' | 'setup' | 'dashboard'

declare global {
  interface Window {
    electronAPI?: {
      hasApiKeys:         () => Promise<boolean>
      getApiKeysMasked:   () => Promise<{ anthropicKey: string; openaiKey: string }>
      setApiKeys:         (k: { anthropicKey: string; openaiKey: string }) => Promise<{ ok: boolean }>
      openExternal:       (url: string) => void
      onUpdateAvailable:  (cb: () => void) => void
      onUpdateDownloaded: (cb: () => void) => void
      installUpdate:      () => void
      getBackendUrl:      () => Promise<string>
      platform:           string
    }
  }
}

export default function App() {
  const [screen, setScreen]           = useState<Screen>('loading')
  const [updateReady, setUpdateReady] = useState(false)

  useEffect(() => {
    const check = async () => {
      if (window.electronAPI) {
        const hasKeys = await window.electronAPI.hasApiKeys()
        setScreen(hasKeys ? 'dashboard' : 'setup')
      } else {
        // Dev sans Electron: check localStorage fallback
        const hasKeys = Boolean(
          localStorage.getItem('cc_anthropic_key') &&
          localStorage.getItem('cc_openai_key')
        )
        setScreen(hasKeys ? 'dashboard' : 'setup')
      }
    }
    check()

    window.electronAPI?.onUpdateDownloaded(() => setUpdateReady(true))
  }, [])

  if (screen === 'loading') return <LoadingPage />
  if (screen === 'setup')
    return <Setup onComplete={() => setScreen('dashboard')} />

  return (
    <>
      {updateReady && <UpdateBanner />}
      <Dashboard />
    </>
  )
}

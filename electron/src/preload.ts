/**
 * Coach Carter LoL — Preload Script
 */
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl:      ()    => ipcRenderer.invoke('get-backend-url'),
  openExternal:       (url: string) => ipcRenderer.invoke('open-external', url),
  platform:           process.platform,

  // API keys
  hasApiKeys:         ()    => ipcRenderer.invoke('has-api-keys'),
  getApiKeysMasked:   ()    => ipcRenderer.invoke('get-api-keys-masked'),
  setApiKeys:         (keys: { anthropicKey: string; openaiKey: string }) =>
                        ipcRenderer.invoke('set-api-keys', keys),

  // Auto-update
  onUpdateAvailable:  (cb: () => void) => ipcRenderer.on('update-available',  cb),
  onUpdateDownloaded: (cb: () => void) => ipcRenderer.on('update-downloaded', cb),
  installUpdate:      ()    => ipcRenderer.invoke('install-update'),
})

// Inject backend URL
ipcRenderer.invoke('get-backend-url').then((url: string) => {
  ;(window as any).BACKEND_URL = url
})

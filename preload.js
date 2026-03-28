const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Riot Live Client polling
  startPolling: () => ipcRenderer.invoke('start-polling'),
  stopPolling: () => ipcRenderer.invoke('stop-polling'),
  onRiotData: (callback) => {
    ipcRenderer.on('riot-data', (_, payload) => callback(payload));
  },
  removeRiotListener: () => {
    ipcRenderer.removeAllListeners('riot-data');
  },

  // Claude API (via main process pour éviter CORS)
  claudeComplete: (prompt, systemPrompt, apiKey) =>
    ipcRenderer.invoke('claude-complete', { prompt, systemPrompt, apiKey }),

  // OP.GG
  opggSummoner: (summonerName, region) => ipcRenderer.invoke('opgg-summoner', { summonerName, region }),
  opggTier: (position) => ipcRenderer.invoke('opgg-tier', { position }),
  opggBuild: (ddId, position) => ipcRenderer.invoke('opgg-build', { ddId, position }),

  // LCU (champion select)
  startLCUPolling: (customLockfile) => ipcRenderer.invoke('start-lcu-polling', customLockfile),
  stopLCUPolling: () => ipcRenderer.invoke('stop-lcu-polling'),
  onLCUData: (callback) => ipcRenderer.on('lcu-data', (_, payload) => callback(payload)),
  removeLCUListener: () => ipcRenderer.removeAllListeners('lcu-data'),

  // LCU Match history
  fetchMatchHistory: (customLockfile) => ipcRenderer.invoke('lcu-match-history', { customLockfile }),

  // LCU Credentials (pour injection dans la webview lol-brain)
  getLCUCredentials: (customLockfile) => ipcRenderer.invoke('get-lcu-credentials', customLockfile),
});

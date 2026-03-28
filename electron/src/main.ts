/**
 * Coach Carter LoL — Electron Main Process
 */
import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { autoUpdater } from 'electron-updater'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'
import { store, hasApiKeys, maskKey } from './store.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname  = path.dirname(__filename)

const isDev = !app.isPackaged
const BACKEND_PORT = 8000
const BACKEND_HOST = '127.0.0.1'
const BACKEND_URL  = `http://${BACKEND_HOST}:${BACKEND_PORT}`

let mainWindow:   BrowserWindow | null = null
let splashWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null

// ── Splash ────────────────────────────────────────────────────────────────

function createSplash(): void {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 260,
    frame: false,
    resizable: false,
    center: true,
    backgroundColor: '#0a0e1a',
    webPreferences: { nodeIntegration: true, contextIsolation: false },
  })
  const splashPath = isDev
    ? path.join(__dirname, '..', 'splash.html')
    : path.join(__dirname, '..', '..', 'splash.html')
  splashWindow.loadFile(splashPath)
}

function setSplashStatus(msg: string): void {
  splashWindow?.webContents.send('splash-status', msg)
}

// ── Backend ───────────────────────────────────────────────────────────────

function getBackendPath(): string {
  if (isDev) return path.join(__dirname, '..', '..', 'backend', 'main.py')
  const exeWin = path.join(process.resourcesPath, 'backend', 'dist', 'CoachCarter-Backend.exe')
  const exeLin = path.join(process.resourcesPath, 'backend', 'dist', 'CoachCarter-Backend')
  if (fs.existsSync(exeWin)) return exeWin
  if (fs.existsSync(exeLin)) return exeLin
  return path.join(process.resourcesPath, 'backend', 'main.py')
}

async function startBackend(): Promise<void> {
  const backendPath = getBackendPath()
  console.log('[ELECTRON] Starting backend:', backendPath)
  setSplashStatus('Démarrage du backend...')

  const isExe = !backendPath.endsWith('.py')
  const cmd   = isExe ? backendPath : 'python'
  const args  = isExe ? [] : [backendPath]

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    BACKEND_PORT:      String(BACKEND_PORT),
    BACKEND_HOST,
    PYTHONUNBUFFERED:  '1',
    ANTHROPIC_API_KEY: store.get('anthropicKey') || process.env.ANTHROPIC_API_KEY || '',
    OPENAI_API_KEY:    store.get('openaiKey')    || process.env.OPENAI_API_KEY    || '',
  }

  pythonProcess = spawn(cmd, args, {
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    cwd: path.dirname(backendPath),
  })

  pythonProcess.stdout?.on('data', d => console.log('[BACKEND]', d.toString().trim()))
  pythonProcess.stderr?.on('data', d => console.error('[BACKEND ERR]', d.toString().trim()))
  pythonProcess.on('exit', code => console.log('[BACKEND] exited:', code))

  setSplashStatus('En attente du backend...')
  await waitForBackend()
}

async function waitForBackend(maxAttempts = 40): Promise<void> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch(`${BACKEND_URL}/status`)
      if (res.ok) { console.log('[ELECTRON] Backend ready'); return }
    } catch {}
    await new Promise(r => setTimeout(r, 500))
  }
  console.warn('[ELECTRON] Backend did not respond in time')
}

function stopBackend(): void {
  if (pythonProcess) { pythonProcess.kill('SIGTERM'); pythonProcess = null }
}

// ── Window ────────────────────────────────────────────────────────────────

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 940,
    height: 700,
    minWidth: 760,
    minHeight: 580,
    show: false,
    frame: true,
    backgroundColor: '#0a0e1a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Coach Carter LoL',
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(process.resourcesPath, 'dist', 'index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    splashWindow?.destroy()
    splashWindow = null
    mainWindow?.show()
  })

  mainWindow.on('closed', () => { mainWindow = null })
}

// ── Auto-updater ──────────────────────────────────────────────────────────

function setupAutoUpdater(): void {
  if (isDev) return
  autoUpdater.checkForUpdatesAndNotify()
  autoUpdater.on('update-available',  () => mainWindow?.webContents.send('update-available'))
  autoUpdater.on('update-downloaded', () => mainWindow?.webContents.send('update-downloaded'))
}

// ── IPC ───────────────────────────────────────────────────────────────────

ipcMain.handle('get-backend-url',     () => BACKEND_URL)
ipcMain.handle('open-external',  (_, url: string) => shell.openExternal(url))

ipcMain.handle('has-api-keys',        () => hasApiKeys())
ipcMain.handle('get-api-keys-masked', () => ({
  anthropicKey: maskKey(store.get('anthropicKey')),
  openaiKey:    maskKey(store.get('openaiKey')),
}))
ipcMain.handle('set-api-keys', async (_, keys: { anthropicKey: string; openaiKey: string }) => {
  store.set('anthropicKey', keys.anthropicKey)
  store.set('openaiKey',    keys.openaiKey)
  stopBackend()
  await startBackend()
  return { ok: true }
})
ipcMain.handle('install-update', () => autoUpdater.quitAndInstall())

// ── Lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  createSplash()
  await startBackend()
  createWindow()
  setupAutoUpdater()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => { stopBackend(); if (process.platform !== 'darwin') app.quit() })
app.on('before-quit',       () => stopBackend())

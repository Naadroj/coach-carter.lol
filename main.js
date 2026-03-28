const { app, BrowserWindow, ipcMain, globalShortcut } = require('electron');
const path = require('path');
const https = require('https');
const fs = require('fs');

// Ignore le certificat auto-signé de Riot
app.commandLine.appendSwitch('ignore-certificate-errors');

let win;
let pollingTimer = null;
let lcuPollingTimer = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    alwaysOnTop: false,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#12121A',
      symbolColor: '#C89B3C',
      height: 52
    },
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,
    }
  });

  win.loadFile('index.html');
}

// ─── LCU (League Client) ─────────────────────────────────────────────────────

const LOCKFILE_PATHS = [
  'E:\\Riot Games\\League of Legends\\lockfile',
  'C:\\Riot Games\\League of Legends\\lockfile',
  'C:\\Program Files\\Riot Games\\League of Legends\\lockfile',
  'C:\\Program Files (x86)\\Riot Games\\League of Legends\\lockfile',
];

function findLockfile(customPath) {
  const candidates = customPath ? [customPath, ...LOCKFILE_PATHS] : LOCKFILE_PATHS;
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function parseLockfile(lockfilePath) {
  const [, , port, password, protocol] = fs.readFileSync(lockfilePath, 'utf8').split(':');
  return { port: parseInt(port), password, protocol };
}

function fetchLCU(port, password, endpoint) {
  return new Promise((resolve, reject) => {
    const auth = Buffer.from(`riot:${password}`).toString('base64');
    const req = https.request(
      { hostname: '127.0.0.1', port, path: endpoint, method: 'GET',
        headers: { Authorization: `Basic ${auth}`, Accept: 'application/json' },
        rejectUnauthorized: false },
      (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => resolve({ status: res.statusCode, body: data ? JSON.parse(data) : null }));
      }
    );
    req.on('error', reject);
    req.setTimeout(3000, () => { req.destroy(); reject(new Error('Timeout')); });
    req.end();
  });
}

let lastLockfilePath = null;

ipcMain.handle('start-lcu-polling', (_, customLockfile) => {
  if (lcuPollingTimer) return;

  const poll = async () => {
    try {
      const lockfilePath = findLockfile(customLockfile);
      if (!lockfilePath) {
        win?.webContents.send('lcu-data', { ok: false, reason: 'no-client' });
        return;
      }
      lastLockfilePath = lockfilePath;
      const { port, password } = parseLockfile(lockfilePath);
      const { status, body } = await fetchLCU(port, password, '/lol-champ-select/v1/session');
      if (status === 200) {
        win?.webContents.send('lcu-data', { ok: true, inChampSelect: true, session: body });
      } else {
        win?.webContents.send('lcu-data', { ok: true, inChampSelect: false });
      }
    } catch {
      win?.webContents.send('lcu-data', { ok: false, reason: 'error' });
    }
  };

  poll();
  lcuPollingTimer = setInterval(poll, 2000);
});

ipcMain.handle('stop-lcu-polling', () => {
  clearInterval(lcuPollingTimer);
  lcuPollingTimer = null;
});

// ─── Riot Live Client API (in-game) ─────────────────────────────────────────

function fetchRiotData() {
  return new Promise((resolve, reject) => {
    const req = https.get(
      'https://127.0.0.1:2999/liveclientdata/allgamedata',
      { rejectUnauthorized: false },
      (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(data)); }
          catch { reject(new Error('Parse error')); }
        });
      }
    );
    req.on('error', reject);
    req.setTimeout(3000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

ipcMain.handle('start-polling', () => {
  if (pollingTimer) return;
  const poll = async () => {
    try {
      const data = await fetchRiotData();
      win?.webContents.send('riot-data', { ok: true, data });
    } catch {
      win?.webContents.send('riot-data', { ok: false });
    }
  };
  poll();
  pollingTimer = setInterval(poll, 5000);
});

ipcMain.handle('stop-polling', () => {
  clearInterval(pollingTimer);
  pollingTimer = null;
});

// ─── OP.GG ───────────────────────────────────────────────────────────────────

const OPGG_ROLES = { TOP: 'top', JGL: 'jungle', MID: 'mid', ADC: 'adc', SUP: 'support' };
const OPGG_SLUG_OVERRIDES = { MonkeyKing: 'wukong', FiddleSticks: 'fiddlesticks', Nunu: 'nunu-willump' };

function toOpggSlug(ddId) {
  return (OPGG_SLUG_OVERRIDES[ddId] || ddId).toLowerCase();
}

function opggFetch(path) {
  return new Promise((resolve) => {
    const req = https.request({
      hostname: 'op.gg',
      path,
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://op.gg/',
        'Origin': 'https://op.gg',
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => { if (data.length < 300000) data += chunk; });
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, body: null }); }
      });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(7000, () => { req.destroy(); resolve(null); });
    req.end();
  });
}

// Profil joueur → champions les plus joués
// Utilise une fenêtre Electron cachée (vrai Chromium) pour contourner Cloudflare
ipcMain.handle('opgg-summoner', async (_, { summonerName, region }) => {
  const slug = summonerName.replace('#', '-');
  const reg  = region.toLowerCase();
  const url  = `https://www.op.gg/lol/summoners/${reg}/${encodeURIComponent(slug)}`;
  const data = await scrapeWithBrowser(url);
  if (data) return { ok: true, data, source: 'browser-scrape' };
  return { ok: false, tried: slug };
});

function scrapeWithBrowser(url) {
  return new Promise((resolve) => {
    let done = false;
    let loadCount = 0;

    const finish = (result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { scrapeWin.destroy(); } catch {}
      resolve(result);
    };

    const scrapeWin = new BrowserWindow({
      show: false,
      width: 1280, height: 900,
      webPreferences: { nodeIntegration: false, contextIsolation: true, javascript: true }
    });

    // Timeout global 30s — Cloudflare peut prendre quelques secondes
    const timer = setTimeout(() => finish(null), 30000);

    const tryExtract = async () => {
      loadCount++;
      if (done) return;
      try {
        const result = await scrapeWin.webContents.executeJavaScript(`
          (() => {
            const el = document.getElementById('__NEXT_DATA__');
            if (!el) return null; // page Cloudflare, pas encore OP.GG
            try {
              const json = JSON.parse(el.textContent);
              const pp = json?.props?.pageProps;
              // Chercher les données de champions à tous les emplacements connus
              const champData =
                pp?.data?.mostChampions      ||
                pp?.data?.most_champions     ||
                pp?.mostChampions            ||
                pp?.summoner?.most_champions ||
                pp?.championStats            ||
                null;
              if (champData) return { most_champions: champData };
              // Retourner le raw pour debug si la structure est inconnue
              return { _raw: JSON.stringify(pp).substring(0, 1000) };
            } catch(e) { return { _err: e.message }; }
          })()
        `);

        if (result !== null) {
          // __NEXT_DATA__ trouvé → la vraie page OP.GG est chargée
          finish(result);
        }
        // result === null → page Cloudflare, on attend le prochain did-finish-load
        // (Cloudflare résout le challenge et redirige vers la vraie page)
      } catch(e) {
        if (loadCount >= 5) finish(null);
      }
    };

    scrapeWin.webContents.on('did-finish-load', tryExtract);
    scrapeWin.webContents.on('did-fail-load', (_, code) => {
      if (code !== -3) finish(null); // -3 = ERR_ABORTED (redirect normale)
    });

    scrapeWin.loadURL(url, {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    });
  });
}

// Tier list pour un rôle → top picks actuels
ipcMain.handle('opgg-tier', async (_, { position }) => {
  const pos = OPGG_ROLES[position] || 'mid';
  const r = await opggFetch(`/api/v1.0/internal/bypass/meta/champions?queueId=420&tier=PLATINUM_PLUS&region=global&position=${pos}`);
  if (r?.status === 200 && r.body) return { ok: true, data: r.body };
  return { ok: false };
});

// Build complet pour un champion (runes, items, spells)
ipcMain.handle('opgg-build', async (_, { ddId, position }) => {
  const slug = toOpggSlug(ddId);
  const pos = OPGG_ROLES[position] || 'mid';
  const r = await opggFetch(`/api/v1.0/internal/bypass/champions/${slug}/ranked/builds?queueId=420&tier=PLATINUM_PLUS&region=global&position=${pos}`);
  if (r?.status === 200 && r.body) return { ok: true, data: r.body };
  return { ok: false };
});

// ─── LCU Credentials (pour injection dans la webview lol-brain) ─────────────

ipcMain.handle('get-lcu-credentials', async (_, customLockfile) => {
  try {
    const lockfilePath = findLockfile(customLockfile);
    if (!lockfilePath) return { ok: false, reason: 'no-lockfile' };
    const { port, password } = parseLockfile(lockfilePath);
    return { ok: true, port, password };
  } catch (e) {
    return { ok: false, reason: e.message };
  }
});

// ─── LCU Match History ───────────────────────────────────────────────────────

ipcMain.handle('lcu-match-history', async (_, { customLockfile } = {}) => {
  try {
    const lockfilePath = findLockfile(customLockfile);
    if (!lockfilePath) return { ok: false, reason: 'no-client' };
    const { port, password } = parseLockfile(lockfilePath);

    // 1. Récupérer le summoner courant (PUUID)
    const summonerRes = await fetchLCU(port, password, '/lol-summoner/v1/current-summoner');
    if (summonerRes.status !== 200 || !summonerRes.body?.puuid) {
      return { ok: false, reason: 'no-summoner' };
    }
    const { puuid, displayName, profileIconId } = summonerRes.body;

    // 2. Historique des 20 dernières parties
    const histRes = await fetchLCU(
      port, password,
      `/lol-match-history/v1/products/lol/${puuid}/matches?begIndex=0&endIndex=19`
    );
    if (histRes.status !== 200 || !histRes.body) {
      return { ok: false, reason: 'no-history', status: histRes.status };
    }

    return { ok: true, puuid, displayName, profileIconId, data: histRes.body };
  } catch (e) {
    return { ok: false, reason: e.message };
  }
});

// ─── Claude API ──────────────────────────────────────────────────────────────

ipcMain.handle('claude-complete', async (_, { prompt, systemPrompt, apiKey }) => {
  const ANTHROPIC_API_KEY = apiKey || process.env.ANTHROPIC_API_KEY || '';
  if (!ANTHROPIC_API_KEY) throw new Error('ANTHROPIC_API_KEY non définie');

  return new Promise((resolve, reject) => {
    const messages = [{ role: 'user', content: prompt }];
    const bodyObj = { model: 'claude-sonnet-4-20250514', max_tokens: 1000, messages };
    if (systemPrompt) bodyObj.system = systemPrompt;
    const body = JSON.stringify(bodyObj);

    const req = https.request({
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) { reject(new Error(parsed.error.message)); return; }
          resolve(parsed.content?.map(b => b.text || '').join('') || '');
        } catch { reject(new Error('Parse error')); }
      });
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
});

// ─── App lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(() => {
  createWindow();

  globalShortcut.register('Alt+L', () => {
    if (!win) return;
    win.isVisible() ? win.hide() : win.show();
  });

  globalShortcut.register('Alt+T', () => {
    if (!win) return;
    win.setAlwaysOnTop(!win.isAlwaysOnTop());
  });
});

app.on('window-all-closed', () => {
  clearInterval(pollingTimer);
  clearInterval(lcuPollingTimer);
  app.quit();
});

app.on('will-quit', () => globalShortcut.unregisterAll());

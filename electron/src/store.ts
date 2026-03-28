import Store from 'electron-store'

interface Config {
  anthropicKey: string
  openaiKey:    string
}

export const store = new Store<Config>({
  name: 'coach-carter',
  defaults: { anthropicKey: '', openaiKey: '' },
})

export const hasApiKeys = (): boolean =>
  Boolean(store.get('anthropicKey') && store.get('openaiKey'))

export const maskKey = (key: string): string => {
  if (!key || key.length < 10) return key ? '••••••••' : ''
  return key.slice(0, 8) + '••••' + key.slice(-4)
}

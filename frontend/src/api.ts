/**
 * Client API — communique avec le backend Python local sur :8000
 */

const BACKEND_URL = (window as any).BACKEND_URL || 'http://127.0.0.1:8000'

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data as T
}

export const api = {
  get:  <T>(path: string)              => request<T>('GET', path),
  post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
}

// Types réponses
export interface LoginResponse {
  token: string
  remaining_games: number
  plan_id: number
}

export interface LocalData {
  remaining_games: number
  first_launch: boolean
  game_timer: number
  email: string | null
  volume: number
}

export interface UsageStats {
  anthropic: {
    input_tokens:  number
    output_tokens: number
    cost_usd:      number
  }
  openai_tts: {
    chars:    number
    cost_usd: number
  }
  total_cost_usd: number
}

export interface GameState {
  active: boolean
  game_time?: number
  player?: {
    name: string
    champion: string
    role: string
    team: string
    cs: number
    kills: number
    deaths: number
    assists: number
    ward_score: number
    is_dead: boolean
  }
  position?: {
    zone: string | null
    description: string | null
    uv: [number, number]
  }
  objectives?: {
    dragon: { kills: number; time_until_spawn: number | null }
    baron: { kills: number; time_until_spawn: number | null }
    herald: { kills: number; time_until_spawn: number | null }
  }
  flags?: {
    is_in_teamfight: boolean
    is_late_game: boolean
  }
}

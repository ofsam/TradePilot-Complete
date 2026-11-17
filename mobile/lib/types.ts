export type Status = {
  connected?: boolean
  environment?: string
  login?: string
  broker_server?: string
  currency?: string
  equity?: number
  balance?: number
  message?: string
  trade_allowed?: boolean
}

export type Tick = {
  symbol: string
  bid: number
  ask: number
  time?: number
}

export type Position = {
  ticket: number
  symbol: string
  type: string
  volume: number
  price_open: number
  price_current: number
  sl?: number
  tp?: number
  profit: number
}

export type DeskState = {
  mode: "manual" | "auto"
  symbols: string[]
  running: boolean
}

export type ScanProposal = {
  direction: string
  entry: number
  stop_loss: number
  take_profit: number
  dedupe_key: string
  risk_fraction?: number
  volume?: number
}

export type ScanResult = {
  bias: string
  proposal?: ScanProposal | null
  skip_reason?: string
  checks?: Record<string, unknown>
}

export type SignalRow = {
  id: number
  symbol: string
  direction?: string
  status?: string
  entry?: number
  stop_loss?: number
  take_profit?: number
  dedupe_key?: string
  created_at?: string
}

export type ExecuteResult = {
  direction: string
  volume: number
  price: number
  ticket: number
  message?: string
  storage_error?: string
  environment?: string
}

export type PortfolioReport = {
  equity?: number
  balance?: number
  currency?: string
  closed_today?: number
  entries_today?: number
}

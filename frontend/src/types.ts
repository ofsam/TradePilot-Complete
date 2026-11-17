export type Status = {
  connected: boolean
  adapter_mode?: string
  environment?: string
  terminal_name?: string | null
  broker_server?: string | null
  login?: string
  account_company?: string | null
  currency?: string | null
  trade_allowed?: boolean
  balance?: number
  equity?: number
  margin?: number
  free_margin?: number
  message?: string
}

export type Position = {
  ticket: number
  symbol: string
  type: number
  volume: number
  price_open: number
  price_current: number
  sl: number
  tp: number
  profit: number
}

export type Tick = { symbol: string; time: number; bid: number; ask: number; last: number; volume: number }

export type CandleBar = { time: number; open: number; high: number; low: number; close: number }

export type ExecutionMode = "manual" | "auto"

export type Rules = {
  rules_source: string
  execution_enabled: boolean
  risk_fraction: number
  reward_multiple: number
  max_trades_per_day: number
  min_stop_distance: number
  day_boundary: string
  rules: string[]
}

export type Proposal = {
  symbol: string
  direction: string
  signal_time: number
  entry: number
  stop_loss: number
  take_profit: number
  stop_distance: number
  lot_size: number | null
  estimated_risk_cash: number | null
  capped: boolean
  dedupe_key: string
  expires_at: number
}

export type SignalRow = {
  id: number
  symbol: string
  direction: string
  entry: number
  stop_loss: number
  take_profit: number
  lot_size: number | null
  estimated_risk: number | null
  status: string
  bar_time: number | null
  expires_at: number | null
  created_at: string | null
  order_submitted: boolean
  execution_enabled: boolean
  message?: string
}

export type ScanResult = {
  execution_enabled: boolean
  rules_source: string
  database_connected: boolean
  bias: string
  checks?: Record<string, boolean>
  skip_reason: string | null
  proposal: Proposal | null
  stored_signal: SignalRow | null
  created: boolean
  storage_error: string | null
  trades_kept_today: number
  position_open: boolean
  order_submitted: boolean
}

export type TradeRow = {
  direction: string
  signal_time: number
  entry_time: number
  exit_time: number | null
  entry: number
  stop_loss: number
  take_profit: number
  exit_price: number | null
  lot_size: number | null
  estimated_risk_cash: number | null
  cash_pnl: number | null
  r_multiple: number | null
  status: string
  exit_reason: string
  shot?: {
    candles: CandleBar[]
    levels: { name: string; price: number }[]
    mark_time: number
  } | null
}

export type BacktestSummary = {
  trades: number
  resolved_trades: number
  wins: number
  losses: number
  unresolved: number
  net_r: number
  profit_factor_r: number | null
  max_consecutive_losses: number
  skipped: number
}

export type BacktestReport = {
  symbol: string
  source: string
  spread: number
  spread_source: string
  starting_equity: number
  ending_equity: number | null
  from_time: number | null
  to_time: number | null
  bars_h1: number
  bars_h4: number
  rules_source: string
  execution_enabled: boolean
  summary: BacktestSummary
  trades: TradeRow[]
  skipped: { signal_time: number; reason: string; direction: string | null }[]
  disclaimer?: string
  warning?: string
  stored?: boolean
  database_connected?: boolean
  storage_error?: string
  order_submitted: boolean
  requested_from?: string | null
  requested_to?: string | null
}

export type SavedBacktest = {
  id: number
  symbol: string
  source: string
  created_at: string | null
  summary: BacktestSummary
  disclaimer?: string
  trades: TradeRow[]
  skipped: { signal_time: number; reason: string; direction: string | null }[]
  starting_equity: number | null
  ending_equity: number | null
  spread: number | null
  spread_source: string | null
}

export type View = "overview" | "portfolio" | "signals" | "backtest" | "strategy" | "journal" | "intelligence"

export type PortfolioReport = {
  account: Status
  positions: Position[]
  floating_pnl: number
  margin_level: number | null
  stop_risk_cash: number | null
  unprotected_positions: number
  open_positions: number
  history_days: number
  history_error: string | null
  closed_trades: number
  wins: number
  losses: number
  net_profit: number
  our_entries_today: number
  max_trades_per_day: number
  execution: string
  order_submitted: boolean
}

export type ExecuteResult = {
  order_submitted: boolean
  message: string
  ticket: number
  symbol: string
  direction: string
  volume: number
  price: number
  stop_loss: number
  take_profit: number
  estimated_risk: number
  auto_execution: boolean
  storage_error?: string
}

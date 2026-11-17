import type { BacktestReport, CandleBar, ExecuteResult, PortfolioReport, Position, Rules, SavedBacktest, ScanResult, SignalRow, Status, Tick } from "./types"

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
const SESSION_KEY = "tradepilot.session"

export function getSessionToken(): string {
  return localStorage.getItem(SESSION_KEY) || ""
}

export function setSessionToken(token: string) {
  localStorage.setItem(SESSION_KEY, token)
}

export function clearSessionToken() {
  localStorage.removeItem(SESSION_KEY)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {})
  const token = getSessionToken()
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`)
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  const response = await fetch(`${BASE}${path}`, { ...init, headers })
  const text = await response.text()
  let body: unknown = null
  if (text) {
    try { body = JSON.parse(text) } catch { body = text }
  }
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? String((body as { detail: unknown }).detail) : text
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return body as T
}

export const requestLoginCode = (email: string) =>
  request<{ ok: boolean; email: string }>("/api/v1/auth/request", {
    method: "POST",
    body: JSON.stringify({ email, purpose: "login" }),
  })

export const verifyLoginCode = (email: string, code: string) =>
  request<{ token: string; email: string }>("/api/v1/auth/verify", {
    method: "POST",
    body: JSON.stringify({ email, code, purpose: "login" }),
  })

export const getAuthMe = () => request<{ email: string }>("/api/v1/auth/me")

export type DeskState = { mode: "manual" | "auto"; symbols: string[]; running: boolean }

export const getDesk = () => request<DeskState>("/api/v1/desk")
export const setDeskMode = (mode: "manual" | "auto", symbols?: string[]) =>
  request<DeskState>("/api/v1/desk/mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(symbols ? { mode, symbols } : { mode }),
  })
export const setDeskSymbols = (symbols: string[]) =>
  request<DeskState>("/api/v1/desk/symbols", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbols }),
  })
export const getStatus = () => request<Status>("/api/v1/mt5/status")
export const connectMT5 = () => request<Status>("/api/v1/mt5/connect", { method: "POST" })
export const disconnectMT5 = () => request<Status>("/api/v1/mt5/disconnect", { method: "POST" })
export const getTick = (symbol: string) => request<Tick>(`/api/v1/mt5/tick?symbol=${encodeURIComponent(symbol)}`)
export const getCandles = (symbol: string, timeframe: "H1" | "H4", count = 48) => request<{ symbol: string; timeframe: string; items: CandleBar[] }>(`/api/v1/mt5/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&count=${count}`)
export const getPositions = () => request<{ items: Position[] }>("/api/v1/mt5/positions")
export const getRules = () => request<Rules>("/api/v1/strategy/rules")
export const scanMarket = (symbol: string) => request<ScanResult>("/api/v1/strategy/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol }) })
export const runBacktest = (source: "sample" | "mt5", symbol: string, range?: { from: string; to: string }, rules: "order_block" | "agent" = "order_block") => request<BacktestReport>("/api/v1/strategy/backtest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source, symbol, from_date: range?.from, to_date: range?.to, rules }) })
export const getSignals = () => request<{ items: SignalRow[]; database_connected: boolean; execution_enabled: boolean }>("/api/v1/signals")
export const decideSignal = (id: number, action: "approve" | "reject") => request<SignalRow>(`/api/v1/signals/${id}/${action}`, { method: "POST" })
export const getBacktests = () => request<{ items: SavedBacktest[]; database_connected: boolean; execution_enabled: boolean }>("/api/v1/strategy/backtests")
export const getPortfolio = () => request<PortfolioReport>("/api/v1/portfolio")
export const executeDemo = (symbol: string, dedupeKey: string) => request<ExecuteResult>("/api/v1/strategy/execute", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol, dedupe_key: dedupeKey }) })

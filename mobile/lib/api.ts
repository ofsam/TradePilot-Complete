import type {
  DeskState,
  ExecuteResult,
  PortfolioReport,
  Position,
  ScanResult,
  SignalRow,
  Status,
  Tick,
} from "./types"

const BASE = (process.env.EXPO_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "")

let authToken = ""

export function setApiToken(token: string) {
  authToken = token
}

export function getApiBase() {
  return BASE
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {})
  if (authToken && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${authToken}`)
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  const response = await fetch(`${BASE}${path}`, { ...init, headers })
  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : text
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return body as T
}

export const getHealth = () =>
  request<{ status: string; execution_enabled: boolean; require_auth?: boolean }>("/health")

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

export const getStatus = () => request<Status>("/api/v1/mt5/status")
export const connectMT5 = () => request<Status>("/api/v1/mt5/connect", { method: "POST" })
export const getTick = (symbol: string) =>
  request<Tick>(`/api/v1/mt5/tick?symbol=${encodeURIComponent(symbol)}`)
export const getPositions = () => request<{ items: Position[] }>("/api/v1/mt5/positions")
export const getDesk = () => request<DeskState>("/api/v1/desk")
export const setDeskMode = (mode: "manual" | "auto", symbols?: string[]) =>
  request<DeskState>("/api/v1/desk/mode", {
    method: "POST",
    body: JSON.stringify(symbols ? { mode, symbols } : { mode }),
  })
export const setDeskSymbols = (symbols: string[]) =>
  request<DeskState>("/api/v1/desk/symbols", {
    method: "POST",
    body: JSON.stringify({ symbols }),
  })
export const scanMarket = (symbol: string) =>
  request<ScanResult>("/api/v1/strategy/scan", {
    method: "POST",
    body: JSON.stringify({ symbol }),
  })
export const executeOrder = (symbol: string, dedupeKey: string) =>
  request<ExecuteResult>("/api/v1/strategy/execute", {
    method: "POST",
    body: JSON.stringify({ symbol, dedupe_key: dedupeKey }),
  })
export const getSignals = () =>
  request<{ items: SignalRow[]; execution_enabled: boolean }>("/api/v1/signals")
export const getPortfolio = () => request<PortfolioReport>("/api/v1/portfolio")

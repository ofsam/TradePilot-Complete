import type { ReactNode } from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Activity, Brain, ChartCandlestick, History, LayoutDashboard, Moon, ShieldCheck, SlidersHorizontal, Sun, Wallet } from "lucide-react"
import { clearSessionToken, connectMT5, disconnectMT5, executeDemo, getAuthMe, getPositions, getSessionToken, getStatus, getTick, scanMarket, setDeskSymbols } from "./api"
import { price, validSymbol } from "./format"
import { Backtest } from "./Backtest"
import { Briefing } from "./Briefing"
import { Intelligence } from "./Intelligence"
import { Journal } from "./Journal"
import { LoginGate } from "./LoginGate"
import { Overview } from "./Overview"
import { Portfolio } from "./Portfolio"
import { Signals } from "./Signals"
import { Strategy } from "./Strategy"
import type { ExecutionMode, Position, Status, Tick, View } from "./types"

const VIEWS: { id: View; label: string; icon: ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard /> },
  { id: "portfolio", label: "Portfolio", icon: <Wallet /> },
  { id: "signals", label: "Signals", icon: <Activity /> },
  { id: "backtest", label: "Backtest", icon: <History /> },
  { id: "strategy", label: "Strategy", icon: <SlidersHorizontal /> },
  { id: "journal", label: "Journal", icon: <ShieldCheck /> },
  { id: "intelligence", label: "Intelligence", icon: <Brain /> },
]

export default function App() {
  const [sessionEmail, setSessionEmail] = useState<string | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [view, setView] = useState<View>("overview")
  const [symbol, setSymbol] = useState(() => localStorage.getItem("tradepilot.symbol") || "XAUUSD")
  const [status, setStatus] = useState<Status | null>(null)
  const [tick, setTick] = useState<Tick | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("MT5 is not connected yet.")
  const [error, setError] = useState("")
  const [bias, setBias] = useState("unknown")
  const [backtestLabel, setBacktestLabel] = useState("Not run")
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("manual")
  const [autoNote, setAutoNote] = useState("")
  const [theme, setTheme] = useState<"dark" | "light">(() => localStorage.getItem("tradepilot.theme") === "light" ? "light" : "dark")
  const autoSent = useRef(new Set<string>())
  const autoRunning = useRef(false)

  useEffect(() => {
    let cancelled = false
    async function boot() {
      if (!getSessionToken()) {
        if (!cancelled) {
          setSessionEmail(null)
          setAuthReady(true)
        }
        return
      }
      try {
        const me = await getAuthMe()
        if (!cancelled) setSessionEmail(me.email)
      } catch {
        clearSessionToken()
        if (!cancelled) setSessionEmail(null)
      } finally {
        if (!cancelled) setAuthReady(true)
      }
    }
    void boot()
    return () => { cancelled = true }
  }, [])

  function chooseTheme(next: "dark" | "light") {
    setTheme(next)
    document.documentElement.dataset.theme = next
    localStorage.setItem("tradepilot.theme", next)
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "light" ? "#f3efe6" : "#0b1220")
  }

  useEffect(() => {
    const tradable = status?.environment === "demo" || status?.environment === "live"
    if (tradable && localStorage.getItem("tradepilot.execution") === "auto") setExecutionMode("auto")
    if (status?.environment && !tradable) setExecutionMode("manual")
  }, [status?.environment])

  function chooseExecution(next: ExecutionMode) {
    setExecutionMode(next)
    localStorage.setItem("tradepilot.execution", next)
    if (next === "manual") setAutoNote("")
  }

  useEffect(() => {
    const tradable = status?.environment === "demo" || status?.environment === "live"
    if (!status?.connected || executionMode !== "auto" || !tradable || !validSymbol(symbol)) return
    let stopped = false
    async function runAuto() {
      if (autoRunning.current || stopped) return
      autoRunning.current = true
      try {
        const result = await scanMarket(symbol)
        if (stopped) return
        setBias(result.bias)
        const proposal = result.proposal
        if (!proposal || autoSent.current.has(proposal.dedupe_key)) return
        const key = proposal.dedupe_key
        autoSent.current.add(key)
        const order = await executeDemo(symbol, key)
        if (stopped) return
        setAutoNote(order.storage_error || `Sent a ${order.direction} of ${order.volume} lots at ${price(order.price)}. Ticket ${order.ticket}.`)
        setError("")
      } catch (err) {
        if (!stopped) setAutoNote(err instanceof Error ? err.message : "Auto scan failed")
      } finally {
        autoRunning.current = false
      }
    }
    void runAuto()
    const id = window.setInterval(() => { void runAuto() }, 15000)
    return () => { stopped = true; window.clearInterval(id) }
  }, [executionMode, status?.connected, status?.environment, symbol])

  const refresh = useCallback(async () => {
    try {
      const next = await getStatus()
      setStatus(next)
      if (next.connected) {
        setMessage(prev => prev === "MT5 is not connected yet."
          ? (next.environment === "live"
            ? "Live account connected. Manual waits for two clicks on Signals. Auto keeps sending on every page and uses real money."
            : next.environment === "demo"
            ? "Demo account connected. Manual waits for two clicks on Signals. Auto keeps sending on every page."
            : "Connected. This account type cannot send orders.")
          : prev)
      }
      if (next.connected && validSymbol(symbol)) {
        const [positionData, quote] = await Promise.all([
          getPositions().catch(() => ({ items: [] as Position[] })),
          getTick(symbol).catch(() => null),
        ])
        setPositions(positionData.items ?? [])
        setTick(quote)
      } else {
        setPositions([])
        setTick(null)
      }
      setError("")
    } catch {
      setError("Cannot reach API. Start the FastAPI backend on this computer.")
    }
  }, [symbol])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    const id = window.setInterval(() => { void refresh() }, 10000)
    return () => window.clearInterval(id)
  }, [refresh])
  useEffect(() => {
    if (!status?.connected || !validSymbol(symbol)) return
    const id = window.setInterval(() => { void getTick(symbol).then(setTick).catch(() => undefined) }, 2000)
    return () => window.clearInterval(id)
  }, [status?.connected, symbol])

  useEffect(() => {
    if (!validSymbol(symbol)) return
    void setDeskSymbols([symbol]).catch(() => undefined)
  }, [symbol])

  function updateSymbol(value: string) {
    const next = value.toUpperCase()
    setSymbol(next)
    localStorage.setItem("tradepilot.symbol", next)
  }

  async function connect() {
    setBusy(true)
    setError("")
    try {
      const next = await connectMT5()
      setStatus(next)
      setMessage(next.environment === "live" ? "Connected to the live MT5 account. Confirmed orders use real money." : next.environment === "demo" ? "Connected to the MT5 demo account." : "Connected. This account type cannot send orders.")
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "MT5 connection failed")
    } finally {
      setBusy(false)
    }
  }

  async function disconnect() {
    setBusy(true)
    try {
      await disconnectMT5()
      setMessage("MT5 adapter disconnected.")
      setBias("unknown")
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed")
    } finally {
      setBusy(false)
    }
  }

  const title = VIEWS.find(item => item.id === view)?.label ?? "Overview"
  if (!authReady) return <div className="gate"><p>Checking this PC…</p></div>
  if (!sessionEmail) return <LoginGate onDone={email => setSessionEmail(email)} />
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="mark"><ChartCandlestick /></div><div><b>TradePilot</b><small>MT5 CONTROL CENTER</small></div></div>
      <label>WORKSPACE</label>
      <nav>
        {VIEWS.map(item => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>{item.icon}{item.label}</button>)}
      </nav>
      <div className="safe"><ShieldCheck /><b>{status?.environment !== "demo" && status?.environment !== "live" ? "Orders blocked" : status?.environment === "live" ? (executionMode === "auto" ? "Auto live" : "Manual live") : executionMode === "auto" ? "Auto demo" : "Manual demo"}</b><p>{executionMode === "auto" ? (autoNote || "New setups are sent on every page while this app stays open. Switch to Manual to stop.") : "Each order waits for two clicks. Auto stays off until you confirm it."}</p></div>
      <footer>Milestone 3 <span>v0.3.0</span></footer>
    </aside>
    <main>
      <header>
        <div className="mobile-brand"><ChartCandlestick /> TradePilot</div>
        <span>Workspace / {title}</span>
        <div className="head-actions">
          <label className="symbol-field">SYMBOL<input value={symbol} maxLength={32} onChange={event => updateSymbol(event.target.value)} /></label>
          <button type="button" className="theme-switch" onClick={() => chooseTheme(theme === "dark" ? "light" : "dark")} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}</button>
          <i>{status?.environment !== "demo" && status?.environment !== "live" ? "ORDERS OFF" : status?.environment === "live" ? (executionMode === "auto" ? "AUTO LIVE" : "MANUAL LIVE") : executionMode === "auto" ? "AUTO DEMO" : "MANUAL"}</i>
        </div>
      </header>
      <section className="content">
        {view === "overview" && <Overview status={status} tick={tick} positions={positions} bias={bias} backtestLabel={backtestLabel} message={message} error={error} busy={busy} symbol={symbol} executionMode={executionMode} onConnect={() => void connect()} onDisconnect={() => void disconnect()} onRefresh={() => void refresh()} onBias={setBias} />}
        {view === "portfolio" && <Portfolio />}
        {view === "signals" && <Signals symbol={symbol} connected={!!status?.connected && validSymbol(symbol)} environment={status?.environment || "unknown"} currency={status?.currency || "USD"} mode={executionMode} onMode={chooseExecution} onConnect={() => void connect()} onBias={setBias} />}
        {view === "backtest" && <Backtest symbol={symbol} connected={!!status?.connected && validSymbol(symbol)} onReport={report => setBacktestLabel(`${report.summary.resolved_trades} resolved · net ${report.summary.net_r}R`)} />}
        {view === "strategy" && <Strategy />}
        {view === "journal" && <Journal />}
        {view === "intelligence" && <Intelligence symbol={symbol} connected={!!status?.connected && validSymbol(symbol)} status={status} tick={tick} positions={positions} mode={executionMode} backtestLabel={backtestLabel} />}
        <Briefing symbol={symbol} connected={!!status?.connected && validSymbol(symbol)} status={status} tick={tick} positions={positions} mode={executionMode} page={view} backtestLabel={backtestLabel} onOpen={() => setView("intelligence")} />
        <footer className="page-footer">TradePilot MT5 · {status?.environment === "live" ? "Live" : "Demo"} {executionMode === "auto" ? "auto" : "manual"} <span><ShieldCheck size={14} /> Contest accounts stay blocked</span></footer>
      </section>
    </main>
    <nav className="mobile-nav">
      {VIEWS.map(item => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>{item.label}</button>)}
    </nav>
  </div>
}

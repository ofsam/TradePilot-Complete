import { useEffect, useRef, useState } from "react"
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, History, ShieldCheck, Wifi, WifiOff } from "lucide-react"
import { getCandles, getPortfolio, scanMarket } from "./api"
import { Detail } from "./components"
import { CHECK_LABELS, money, price, reasonText, when } from "./format"
import type { CandleBar, ExecutionMode, Position, ScanResult, Status, Tick } from "./types"

function sessions(now = new Date()) {
  const hour = now.getUTCHours() + now.getUTCMinutes() / 60
  return { london: hour >= 7 && hour < 16, newYork: hour >= 12 && hour < 21 }
}

function Spark({ candles }: { candles: CandleBar[] }) {
  if (candles.length < 2) return <p className="footnote">Waiting for H1 candles.</p>
  const width = 320
  const height = 84
  const closes = candles.map(candle => candle.close)
  const max = Math.max(...closes)
  const min = Math.min(...closes)
  const span = max - min || 1
  const line = closes.map((value, index) => {
    const x = (index / (closes.length - 1)) * width
    const y = height - ((value - min) / span) * (height - 8) - 4
    return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(" ")
  const up = closes[closes.length - 1] >= closes[0]
  return <svg className="spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Recent H1 closes">
    <path d={line} className={up ? "up" : "down"} />
  </svg>
}

export function Overview({
  status, tick, positions, bias, backtestLabel, message, error, busy, symbol, executionMode, onConnect, onDisconnect, onRefresh,
}: {
  status: Status | null
  tick: Tick | null
  positions: Position[]
  bias: string
  backtestLabel: string
  message: string
  error: string
  busy: boolean
  symbol: string
  executionMode: ExecutionMode
  onConnect: () => void
  onDisconnect: () => void
  onRefresh: () => void
  onBias: (bias: string) => void
}) {
  const connected = !!status?.connected
  const currency = status?.currency || "USD"
  const env = status?.environment || "unknown"
  const spread = tick ? tick.ask - tick.bid : null
  const [candles, setCandles] = useState<CandleBar[]>([])
  const [entriesToday, setEntriesToday] = useState<number | null>(null)
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [clock, setClock] = useState(() => sessions())
  const previousBid = useRef<number | null>(null)
  const [move, setMove] = useState<"up" | "down" | "flat">("flat")

  useEffect(() => {
    const id = window.setInterval(() => setClock(sessions()), 30000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    if (!connected) return
    let stopped = false
    async function load() {
      try {
        const [bars, book, next] = await Promise.all([
          getCandles(symbol, "H1", 48),
          getPortfolio().catch(() => null),
          scanMarket(symbol).catch(() => null),
        ])
        if (stopped) return
        setCandles(bars.items)
        setEntriesToday(book ? book.our_entries_today : null)
        if (next) {
          setScan(next)
          onBias(next.bias)
        }
      } catch {
        if (!stopped) setCandles([])
      }
    }
    void load()
    const id = window.setInterval(() => { void load() }, 15000)
    return () => { stopped = true; window.clearInterval(id) }
  }, [connected, onBias, symbol])

  useEffect(() => {
    if (!tick) return
    if (previousBid.current != null && tick.bid !== previousBid.current) setMove(tick.bid > previousBid.current ? "up" : "down")
    previousBid.current = tick.bid
  }, [tick])

  const shownBias = scan?.bias || bias
  const biasLabel = shownBias === "long" ? "Long" : shownBias === "short" ? "Short" : shownBias === "neutral" ? "Waiting" : "Not scanned"
  const used = entriesToday ?? 0

  return <>
    <div className="heading">
      <div>
        <small>TRADING WORKSPACE</small>
        <h1>Overview</h1>
        <p>{symbol} on the connected terminal. H4 bias comes from a close beyond the prior H4 high or low. The entry is a later return to an H1 close.</p>
      </div>
      {connected
        ? <button className="secondary" disabled={busy} onClick={onDisconnect}><WifiOff size={16} /> Disconnect</button>
        : <button className="primary" disabled={busy} onClick={onConnect}><Wifi size={16} />{busy ? "Connecting…" : "Connect MT5"}</button>}
    </div>
    {error && <div className="alert error"><AlertTriangle />{error}</div>}
    {message && <div className="alert"><ShieldCheck />{message}</div>}
    <section className="hero">
      <div className="hero-main">
        <div className="hero-top">
          <span className={`live-pill ${connected ? "on" : ""}`}><i />{connected ? "Live" : "Offline"}</span>
          <strong>{symbol}</strong>
          <span className={`tag ${env}`}>{env.toUpperCase()}</span>
          <span className={`tag ${shownBias}`}>{biasLabel}</span>
        </div>
        <div className={`hero-price ${move}`}>{tick ? price(tick.bid) : "—"}</div>
        <div className="hero-meta">
          <span>Ask <b>{tick ? price(tick.ask) : "—"}</b></span>
          <span>Spread <b>{spread === null ? "—" : price(spread)}</b></span>
          <span>Updated <b>{tick ? when(tick.time) : "—"}</b></span>
        </div>
        <Spark candles={candles} />
      </div>
      <div className="hero-side">
        <div className="session-card">
          <small>SESSIONS · UTC</small>
          <div className={clock.london ? "session open" : "session"}><b>London</b><span>{clock.london ? "Open" : "Closed"}</span></div>
          <div className={clock.newYork ? "session open" : "session"}><b>New York</b><span>{clock.newYork ? "Open" : "Closed"}</span></div>
          <p>These sessions are context. This H4 and H1 plan can propose a trade outside them.</p>
        </div>
        <div className="session-card">
          <small>ENTRIES TODAY</small>
          <div className="allowance" aria-label={`${used} of 2 entries used`}>
            <i className={used > 0 ? "used" : ""} />
            <i className={used > 1 ? "used" : ""} />
          </div>
          <b>{entriesToday === null ? "—" : `${used} of 2`}</b>
          <p>UTC day. The third setup is skipped.</p>
        </div>
      </div>
    </section>
    <div className="metrics">
      <div className="metric"><div className="metric-label"><span><Activity size={16} /></span>Balance</div><h2>{connected ? money(status?.balance, currency) : "—"}</h2><small>{connected ? currency : "Connect MT5 to load"}</small></div>
      <div className="metric"><div className="metric-label"><span><Activity size={16} /></span>Equity</div><h2>{connected ? money(status?.equity, currency) : "—"}</h2><small>Free margin {connected ? money(status?.free_margin, currency) : "—"}</small></div>
      <div className="metric"><div className="metric-label"><span><ShieldCheck size={16} /></span>Execution</div><h2>{env !== "demo" && env !== "live" ? "Blocked" : executionMode === "auto" ? "Auto" : "Manual"}</h2><small>{env === "live" ? "Live account" : env === "demo" ? "Demo account" : "This account cannot send"}</small></div>
      <div className="metric"><div className="metric-label"><span><History size={16} /></span>Research</div><h2>{backtestLabel}</h2><small>Not an 80% win-rate claim</small></div>
    </div>
    {scan?.checks && <div className="checks">{Object.entries(CHECK_LABELS).map(([key, label]) => <span key={key} className={scan.checks?.[key] ? "pass" : "fail"}>{label}</span>)}</div>}
    {scan && !scan.proposal && <div className="alert"><ShieldCheck />{reasonText(scan.skip_reason) || "No confirmed setup on the latest closed hour."}</div>}
    <div className="two-col">
      <section className="panel">
        <div className="panel-head"><div><b>Account</b><small>{status?.broker_server || "Not connected"}</small></div><button className="iconbtn" onClick={onRefresh}><Activity size={16} /></button></div>
        <Detail label="Login" value={status?.login || "—"} />
        <Detail label="Company" value={status?.account_company || "—"} />
        <Detail label="Trade permission" value={connected ? (status?.trade_allowed ? "Yes" : "No") : "—"} />
        <Detail label="Floating positions" value={String(positions.length)} />
        <div className="warning"><AlertTriangle />{env === "live" ? "Live orders use real money. Manual needs two clicks on Signals. Auto keeps sending on every page until you switch to Manual." : env === "demo" ? "Manual needs two clicks on Signals. Auto keeps sending on every page until you switch to Manual." : "This account type cannot place an order from this app."}</div>
      </section>
      <section className="panel">
        <div className="panel-head"><div><b>What the desk is waiting for</b><small>Closed candles only</small></div></div>
        <Detail label="H4 direction" value={biasLabel} />
        <Detail label="H4 bias" value={scan?.checks?.h4_bias ? biasLabel : "Not confirmed"} />
        <Detail label="H1 break" value={scan?.checks?.h1_setup ? "Saved" : "None"} />
        <Detail label="Retest" value={scan?.checks?.retest ? "Touched" : "Waiting"} />
        <Detail label="Stop cap" value={scan?.checks?.stop_cap ? "Within 10,000 points" : "Not accepted"} />
        <div className="warning"><ShieldCheck />Planned risk stays at or under 2% only when a setup passes. Gaps and slippage can still lose more than that.</div>
      </section>
    </div>
    <section className="panel positions">
      <div className="panel-head"><div><b>Open positions</b><small>Snapshot from MT5</small></div><span className="tag">{positions.length} positions</span></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Symbol</th><th>Direction</th><th>Volume</th><th>Open</th><th>Current</th><th>SL / TP</th><th>Floating P/L</th></tr></thead>
          <tbody>
            {positions.length === 0 ? <tr><td colSpan={7} className="empty"><History /><b>No open positions</b><small>{connected ? "The terminal is flat." : "Connect MT5 to read positions."}</small></td></tr> : positions.map(position => (
              <tr key={position.ticket}>
                <td>{position.symbol}<small>#{position.ticket}</small></td>
                <td className={position.type === 0 ? "green" : "red"}>{position.type === 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />} {position.type === 0 ? "Buy" : "Sell"}</td>
                <td>{position.volume}</td>
                <td>{price(position.price_open)}</td>
                <td>{price(position.price_current)}</td>
                <td>{position.sl ? price(position.sl) : "—"} / {position.tp ? price(position.tp) : "—"}</td>
                <td className={position.profit >= 0 ? "green" : "red"}>{money(position.profit, currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  </>
}

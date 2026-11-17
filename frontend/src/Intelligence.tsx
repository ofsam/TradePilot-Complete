import { useEffect, useState } from "react"
import { Brain } from "lucide-react"
import { getPortfolio, getSignals, scanMarket } from "./api"
import { CHECK_LABELS, money, price, when } from "./format"
import { buildDesk } from "./insight"
import type { ExecutionMode, PortfolioReport, Position, ScanResult, SignalRow, Status, Tick } from "./types"

export function Intelligence({
  symbol, connected, status, tick, positions, mode, backtestLabel,
}: {
  symbol: string
  connected: boolean
  status: Status | null
  tick: Tick | null
  positions: Position[]
  mode: ExecutionMode
  backtestLabel: string
}) {
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [portfolio, setPortfolio] = useState<PortfolioReport | null>(null)
  const [signals, setSignals] = useState<SignalRow[]>([])
  const [database, setDatabase] = useState<boolean | null>(null)
  const currency = status?.currency || "USD"

  useEffect(() => {
    if (!connected) return
    let stopped = false
    async function load() {
      const [nextScan, nextBook, nextSignals] = await Promise.all([
        scanMarket(symbol).catch(() => null),
        getPortfolio().catch(() => null),
        getSignals().catch(() => null),
      ])
      if (stopped) return
      setScan(nextScan)
      setPortfolio(nextBook)
      setSignals(nextSignals?.items ?? [])
      setDatabase(nextSignals ? nextSignals.database_connected : false)
    }
    void load()
    const id = window.setInterval(() => { void load() }, 30000)
    return () => { stopped = true; window.clearInterval(id) }
  }, [connected, symbol])

  const read = buildDesk({
    connected, symbol, status, tick, positions, mode, scan, portfolio, signals, signalsDatabase: database, page: "intelligence", backtestLabel,
  })
  const proposal = scan?.proposal

  return <>
    <div className="heading">
      <div>
        <small>DECISION SUPPORT</small>
        <h1>Intelligence</h1>
        <p>A read of the current setup, the terminal history, and the stored signals. It explains the desk. It does not promise a win.</p>
      </div>
      <span className={`tag ${read.stance}`}>{read.stanceLabel}</span>
    </div>
    <div className="knowledge-grid">
      {read.knowledge.map(item => <article key={item.title} className="panel knowledge-card"><b>{item.title}</b><p>{item.text}</p></article>)}
    </div>
    <section className="panel positions">
      <div className="panel-head"><div><b>Setup map</b><small>{scan ? scan.rules_source : "Waiting for a scan"} · {symbol}</small></div><Brain size={16} /></div>
      {read.checks.length === 0 ? <p className="footnote">Connect MT5 to score the closed candles.</p> : <div className="table-wrap"><table>
        <thead><tr><th>Check</th><th>Now</th><th>What it means for the decision</th></tr></thead>
        <tbody>{read.checks.map(check => <tr key={check.key}><td>{CHECK_LABELS[check.key] || check.label}</td><td><span className={`tag ${check.pass ? "approved" : "rejected"}`}>{check.pass ? "Pass" : "Fail"}</span></td><td>{check.meaning}</td></tr>)}</tbody>
      </table></div>}
      {proposal && <div className="warning">The passing plan is a {proposal.direction} of {proposal.lot_size ?? "—"} lots. Planned risk {money(proposal.estimated_risk_cash, currency)}. It expires {when(proposal.expires_at)}.</div>}
    </section>
    <div className="two-col">
      <section className="panel">
        <div className="panel-head"><div><b>History insight</b><small>Closing deals from the terminal</small></div></div>
        <ul className="insight-list">{read.history.map(item => <li key={item.title}><b>{item.title}</b>{item.text}</li>)}</ul>
        {portfolio && <div className="metrics compact-metrics">
          <div className="metric"><div className="metric-label">Closed</div><h2>{portfolio.closed_trades}</h2><small>{portfolio.history_days} days</small></div>
          <div className="metric"><div className="metric-label">Net</div><h2>{money(portfolio.net_profit, currency)}</h2><small>{portfolio.wins} wins · {portfolio.losses} losses</small></div>
        </div>}
      </section>
      <section className="panel">
        <div className="panel-head"><div><b>Signal book</b><small>{database === false ? "PostgreSQL is offline" : "Stored decisions"}</small></div></div>
        <ul className="insight-list">{read.signals.map(item => <li key={item.title}><b>{item.title}</b>{item.text}</li>)}</ul>
      </section>
    </div>
    <section className="panel positions">
      <div className="panel-head"><div><b>Recent stored signals</b><small>Newest rows from the database</small></div><span className="tag">{signals.length}</span></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Status</th><th>Symbol</th><th>Direction</th><th>Entry</th><th>Stop</th><th>Target</th><th>Risk</th><th>Candle</th></tr></thead>
        <tbody>{signals.length === 0 ? <tr><td colSpan={8} className="empty"><b>No stored signals</b><small>Start PostgreSQL, then scan, to build this book.</small></td></tr> : signals.slice(0, 8).map(row => (
          <tr key={row.id}><td><span className={`tag ${row.status}`}>{row.status}</span></td><td>{row.symbol}</td><td className={row.direction === "buy" ? "green" : "red"}>{row.direction}</td><td>{price(row.entry)}</td><td>{price(row.stop_loss)}</td><td>{price(row.take_profit)}</td><td>{money(row.estimated_risk, currency)}</td><td>{when(row.bar_time)}</td></tr>
        ))}</tbody>
      </table></div>
    </section>
    <section className="panel">
      <div className="panel-head"><div><b>Open positions in this read</b><small>Included because an open trade changes the next decision</small></div></div>
      {positions.length === 0 ? <p className="footnote">No open position. A new setup is not blocked by inventory.</p> : <div className="table-wrap"><table>
        <thead><tr><th>Symbol</th><th>Volume</th><th>Open</th><th>Stop</th><th>Floating</th></tr></thead>
        <tbody>{positions.map(position => <tr key={position.ticket}><td>{position.symbol}</td><td>{position.volume}</td><td>{price(position.price_open)}</td><td>{position.sl ? price(position.sl) : "None"}</td><td className={position.profit >= 0 ? "green" : "red"}>{money(position.profit, currency)}</td></tr>)}</tbody>
      </table></div>}
    </section>
  </>
}

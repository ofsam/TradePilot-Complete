import { useEffect, useState } from "react"
import { getBacktests, getSignals } from "./api"
import { money, price, when } from "./format"
import type { SavedBacktest, SignalRow } from "./types"

export function Journal() {
  const [signals, setSignals] = useState<SignalRow[]>([])
  const [runs, setRuns] = useState<SavedBacktest[]>([])
  const [database, setDatabase] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    void (async () => {
      try {
        const [signalData, runData] = await Promise.all([getSignals(), getBacktests()])
        setSignals(signalData.items)
        setRuns(runData.items)
        setDatabase(signalData.database_connected && runData.database_connected)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load the journal")
      }
    })()
  }, [])

  return <>
    <div className="heading"><div><small>HISTORY</small><h1>Journal</h1><p>Stored signal decisions and backtest runs. Nothing here was sent as an order.</p></div></div>
    {error && <div className="alert error">{error}</div>}
    {!database && <div className="alert">PostgreSQL is not connected, so this journal is empty even if you have already scanned.</div>}
    <section className="panel positions">
      <div className="panel-head"><div><b>Signal decisions</b><small>Approve and reject write an audit row</small></div></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Status</th><th>Symbol</th><th>Direction</th><th>Entry</th><th>Stop</th><th>Target</th><th>Lots</th><th>Risk</th><th>Candle</th></tr></thead>
        <tbody>{signals.length === 0 ? <tr><td colSpan={9} className="empty"><b>No decisions stored</b></td></tr> : signals.map(row => (
          <tr key={row.id}><td><span className={`tag ${row.status}`}>{row.status}</span></td><td>{row.symbol}</td><td>{row.direction}</td><td>{price(row.entry)}</td><td>{price(row.stop_loss)}</td><td>{price(row.take_profit)}</td><td>{row.lot_size ?? "—"}</td><td>{money(row.estimated_risk)}</td><td>{when(row.bar_time)}</td></tr>
        ))}</tbody>
      </table></div>
    </section>
    <section className="panel">
      <div className="panel-head"><div><b>Backtest runs</b><small>Newest first</small></div></div>
      <div className="table-wrap"><table>
        <thead><tr><th>When</th><th>Symbol</th><th>Source</th><th>Trades</th><th>Net R</th><th>Ending equity</th></tr></thead>
        <tbody>{runs.length === 0 ? <tr><td colSpan={6} className="empty"><b>No backtests stored</b></td></tr> : runs.map(run => (
          <tr key={run.id}><td>{run.created_at ? new Date(run.created_at).toLocaleString() : "—"}</td><td>{run.symbol}</td><td>{run.source}</td><td>{run.summary?.resolved_trades ?? "—"}</td><td>{run.summary?.net_r ?? "—"}</td><td>{money(run.ending_equity)}</td></tr>
        ))}</tbody>
      </table></div>
    </section>
  </>
}

import { useEffect, useState } from "react"
import { AlertTriangle, ShieldCheck } from "lucide-react"
import { getPortfolio } from "./api"
import { Detail } from "./components"
import { money, price } from "./format"
import type { PortfolioReport } from "./types"

export function Portfolio() {
  const [report, setReport] = useState<PortfolioReport | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    let stopped = false
    async function load() {
      try {
        const next = await getPortfolio()
        if (!stopped) {
          setReport(next)
          setError("")
        }
      } catch (err) {
        if (!stopped) setError(err instanceof Error ? err.message : "Portfolio is unavailable")
      }
    }
    void load()
    const id = window.setInterval(() => { void load() }, 5000)
    return () => { stopped = true; window.clearInterval(id) }
  }, [])

  const account = report?.account
  const currency = account?.currency || "USD"
  const tradable = account?.environment === "demo" || account?.environment === "live"
  const live = account?.environment === "live"
  return <>
    <div className="heading">
      <div>
        <small>RISK AND RESULTS</small>
        <h1>Portfolio</h1>
        <p>Live account, open positions, stop risk, and closed-trade results from the terminal.</p>
      </div>
    </div>
    {error && <div className="alert error"><AlertTriangle />{error}</div>}
    {report?.history_error && <div className="alert error"><AlertTriangle />{report.history_error}</div>}
    <div className="alert"><ShieldCheck />{live ? "This is a live account. A confirmed order on Signals uses real money." : tradable ? "This is a demo account. A trade is sent only after you confirm it on Signals." : "This account type cannot send orders."}</div>
    <div className="metrics">
      <div className="metric"><div className="metric-label">Equity</div><h2>{money(account?.equity, currency)}</h2><small>Balance {money(account?.balance, currency)}</small></div>
      <div className="metric"><div className="metric-label">Floating P/L</div><h2 className={(report?.floating_pnl ?? 0) >= 0 ? "green" : "red"}>{money(report?.floating_pnl, currency)}</h2><small>{report?.open_positions ?? 0} open positions</small></div>
      <div className="metric"><div className="metric-label">Risk at stops</div><h2>{report?.stop_risk_cash == null ? "—" : money(report.stop_risk_cash, currency)}</h2><small>{report?.unprotected_positions ? `${report.unprotected_positions} without a stop` : "Estimated from current price to stop"}</small></div>
      <div className="metric"><div className="metric-label">Margin level</div><h2>{report?.margin_level == null ? "—" : `${report.margin_level.toFixed(0)}%`}</h2><small>Free margin {money(account?.free_margin, currency)}</small></div>
    </div>
    <div className="two-col">
      <section className="panel">
        <div className="panel-head"><div><b>30-day closed trades</b><small>From the terminal deal history</small></div></div>
        <Detail label="Closed trades" value={String(report?.closed_trades ?? "—")} />
        <Detail label="Wins" value={String(report?.wins ?? "—")} />
        <Detail label="Losses" value={String(report?.losses ?? "—")} />
        <Detail label="Net profit" value={money(report?.net_profit, currency)} />
      </section>
      <section className="panel">
        <div className="panel-head"><div><b>Today's limit</b><small>Ghana day, orders sent by this app</small></div></div>
        <Detail label="Sent today" value={`${report?.our_entries_today ?? "—"} of ${report?.max_trades_per_day ?? 2}`} />
        <Detail label="Environment" value={account?.environment || "unknown"} />
        <Detail label="Sending" value={report?.execution === "confirm" ? "After confirmation on Signals" : "Blocked"} />
        <Detail label="Automatic bot" value="Off" />
      </section>
    </div>
    <section className="panel positions">
      <div className="panel-head"><div><b>Open positions</b><small>Refreshes about every 5 seconds</small></div></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Symbol</th><th>Direction</th><th>Volume</th><th>Open</th><th>Current</th><th>Stop</th><th>Target</th><th>P/L</th></tr></thead>
        <tbody>
          {!report || report.positions.length === 0 ? <tr><td colSpan={8} className="empty"><b>No open positions</b></td></tr> : report.positions.map(position => (
            <tr key={position.ticket}>
              <td>{position.symbol}<small>#{position.ticket}</small></td>
              <td className={position.type === 0 ? "green" : "red"}>{position.type === 0 ? "Buy" : "Sell"}</td>
              <td>{position.volume}</td>
              <td>{price(position.price_open)}</td>
              <td>{price(position.price_current)}</td>
              <td>{position.sl ? price(position.sl) : "None"}</td>
              <td>{position.tp ? price(position.tp) : "—"}</td>
              <td className={position.profit >= 0 ? "green" : "red"}>{money(position.profit, currency)}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
    </section>
  </>
}

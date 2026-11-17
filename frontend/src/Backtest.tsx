import { useState } from "react"
import { AlertTriangle, Download, ShieldCheck } from "lucide-react"
import { runBacktest } from "./api"
import { downloadBacktestPdf } from "./backtestPdf"
import { equitySeries, returnPercent, rulesLabel, sourceLabel, winRate } from "./backtestStats"
import { money, price, reasonText, when } from "./format"
import type { BacktestReport, TradeRow } from "./types"

function percent(value: number | null, digits = 1) {
  return value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(digits)}%`
}

function EquityChart({ points }: { points: { equity: number }[] }) {
  if (points.length < 2) return <p className="footnote">Equity needs at least one closed trade.</p>
  const width = 720
  const height = 190
  const padLeft = 8
  const padRight = 72
  const padY = 16
  const values = points.map(point => point.equity)
  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = max - min || 1
  const plotWidth = width - padLeft - padRight
  const plotHeight = height - padY * 2
  const x = (index: number) => padLeft + (index / (points.length - 1)) * plotWidth
  const y = (value: number) => padY + ((max - value) / span) * plotHeight
  const line = points.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(point.equity).toFixed(1)}`).join(" ")
  const floor = padY + plotHeight
  const area = `${line} L${x(points.length - 1).toFixed(1)},${floor.toFixed(1)} L${x(0).toFixed(1)},${floor.toFixed(1)} Z`
  return <svg className="equity" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Equity curve">
    {[0, 0.5, 1].map(step => {
      const value = min + span * step
      const yPos = y(value)
      return <g key={step}>
        <line x1={padLeft} x2={width - padRight} y1={yPos} y2={yPos} className="grid" />
        <text x={width - padRight + 8} y={yPos + 3} className="axis">{money(value)}</text>
      </g>
    })}
    <path d={area} className="equity-fill" />
    <path d={line} className="equity-line" />
  </svg>
}

function levelKind(name: string) {
  if (name.startsWith("H4")) return "lvl-h4"
  if (name.startsWith("Zone") || name.startsWith("Breakout") || name === "Retest") return "lvl-zone"
  if (name === "Stop") return "lvl-stop"
  if (name === "Target") return "lvl-target"
  return "lvl-entry"
}

function TradeShot({ trade }: { trade: TradeRow }) {
  const shot = trade.shot
  if (!shot || shot.candles.length < 2) return null
  const candles = shot.candles
  const width = 640
  const height = 220
  const padLeft = 8
  const padRight = 16
  const padY = 16
  const values = [...candles.flatMap(candle => [candle.high, candle.low]), ...shot.levels.map(level => level.price)]
  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = max - min || 1
  const plotWidth = width - padLeft - padRight
  const plotHeight = height - padY * 2
  const slot = plotWidth / candles.length
  const y = (value: number) => padY + ((max - value) / span) * plotHeight
  return <figure className="chart shot">
    <figcaption><b>{trade.direction} · {trade.status}</b><small>{when(trade.signal_time)} · {trade.exit_reason}</small></figcaption>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${trade.direction} setup on ${when(trade.signal_time)}`}>
      {shot.levels.map(level => <line key={level.name} x1={padLeft} x2={width - padRight} y1={y(level.price)} y2={y(level.price)} className={levelKind(level.name)} />)}
      {candles.map((candle, index) => {
        const up = candle.close >= candle.open
        const x = padLeft + index * slot + slot / 2
        const bodyTop = y(Math.max(candle.open, candle.close))
        const bodyBottom = y(Math.min(candle.open, candle.close))
        const marked = candle.time === shot.mark_time
        return <g key={candle.time}>
          {marked && <rect x={x - slot / 2} y={padY} width={slot} height={plotHeight} className="mark" />}
          <line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} className={up ? "up" : "down"} />
          <rect x={x - Math.max(slot * 0.28, 1.5)} y={bodyTop} width={Math.max(slot * 0.56, 3)} height={Math.max(bodyBottom - bodyTop, 1)} className={up ? "up" : "down"} />
        </g>
      })}
    </svg>
    <div className="shot-key">{shot.levels.map(level => <span key={level.name}><i className={levelKind(level.name)} />{level.name} {price(level.price)}</span>)}</div>
  </figure>
}

function utcDay(daysAgo: number) {
  const date = new Date()
  date.setUTCDate(date.getUTCDate() - daysAgo)
  return date.toISOString().slice(0, 10)
}

export function Backtest({ symbol, connected, onReport }: { symbol: string; connected: boolean; onReport: (report: BacktestReport) => void }) {
  const [report, setReport] = useState<BacktestReport | null>(null)
  const [busy, setBusy] = useState<"sample" | "mt5" | "agent" | null>(null)
  const [error, setError] = useState("")
  const [fromDate, setFromDate] = useState(() => utcDay(30))
  const [toDate, setToDate] = useState(() => utcDay(0))

  async function run(source: "sample" | "mt5", rules: "order_block" | "agent" = "order_block") {
    const task = rules === "agent" ? "agent" : source
    setBusy(task)
    setError("")
    if (source === "mt5" && fromDate > toDate) {
      setError("The end date is before the start date.")
      setBusy(null)
      return
    }
    try {
      const next = await runBacktest(source, symbol, source === "mt5" ? { from: fromDate, to: toDate } : undefined, rules)
      setReport(next)
      onReport(next)
    }
    catch (err) { setError(err instanceof Error ? err.message : "Backtest failed") }
    finally { setBusy(null) }
  }

  async function download() {
    if (!report) return
    setError("")
    try { await downloadBacktestPdf(report) }
    catch (err) { setError(err instanceof Error ? err.message : "The PDF could not be created") }
  }

  const summary = report?.summary
  const series = report ? equitySeries(report) : null
  const rate = report ? winRate(report) : null
  const change = report ? returnPercent(report) : null
  const mixTotal = summary ? summary.wins + summary.losses + summary.unresolved + summary.skipped : 0

  return <>
    <div className="heading">
      <div>
        <small>RESEARCH</small>
        <h1>Backtest</h1>
        <p>Your H4 bias and H1 retest rules use Run selected range. The agent button replays the same dates with a different model and does not send an order.</p>
      </div>
      <div className="row-actions">
        <button className="secondary" disabled={busy !== null} onClick={() => void run("sample")}>{busy === "sample" ? "Running…" : "Run sample fixture"}</button>
        <button className="primary" disabled={!connected || busy !== null} onClick={() => void run("mt5")}>{busy === "mt5" ? "Running…" : "Run selected range"}</button>
        <button className="secondary" disabled={!connected || busy !== null} onClick={() => void run("mt5", "agent")}>{busy === "agent" ? "Running…" : "Run range with agent logic"}</button>
        <button className="secondary" disabled={!report || busy !== null} onClick={download}><Download size={14} />Download PDF</button>
      </div>
    </div>
    <div className="date-range">
      <label>FROM<input type="date" value={fromDate} max={toDate} onChange={event => setFromDate(event.target.value)} /></label>
      <label>TO<input type="date" value={toDate} min={fromDate} max={utcDay(0)} onChange={event => setToDate(event.target.value)} /></label>
      <p>UTC days. Terminal history uses this window. The sample fixture ignores it. The longest range is 365 days.</p>
    </div>
    {error && <div className="alert error"><AlertTriangle />{error}</div>}
    {!connected && <div className="alert"><ShieldCheck />MT5 history needs a connected terminal. The sample fixture runs without it.</div>}
    {!report && <div className="source-cards">
      <section className="panel source-card">
        <div className="panel-head"><div><b>Sample fixture</b><small>No terminal required</small></div></div>
        <p>One planned win, one planned loss, and a setup skipped for the daily limit. It checks the engine. It is not market performance.</p>
        <button className="secondary" disabled={busy !== null} onClick={() => void run("sample")}>{busy === "sample" ? "Running…" : "Run sample"}</button>
      </section>
      <section className="panel source-card">
        <div className="panel-head"><div><b>MT5 history</b><small>{connected ? `${symbol} from the terminal` : "Connect MT5 first"}</small></div></div>
        <p>Closed H4 and H1 candles inside the dates above. Run range uses the H4 bias and H1 level-retest rules, with a 5R target. Run range with agent logic waits for an H4 trend and an H1 sweep that closes back through the prior hour. Research only. Nothing is sent to the broker.</p>
        <div className="row-actions">
          <button className="primary" disabled={!connected || busy !== null} onClick={() => void run("mt5")}>{busy === "mt5" ? "Running…" : "Run range"}</button>
          <button className="secondary" disabled={!connected || busy !== null} onClick={() => void run("mt5", "agent")}>{busy === "agent" ? "Running…" : "Run range with agent logic"}</button>
        </div>
      </section>
    </div>}
    {report && summary && series && <>
      <div className="alert"><ShieldCheck />{report.disclaimer}</div>
      {report.warning && <div className="alert error"><AlertTriangle />{report.warning}</div>}
      {report.storage_error && <div className="alert error"><AlertTriangle />{report.storage_error}</div>}
      <div className="metrics">
        <div className="metric"><div className="metric-label">Resolved</div><h2>{summary.resolved_trades}</h2><small>{summary.wins} wins · {summary.losses} losses · {summary.unresolved} open at the end</small></div>
        <div className="metric"><div className="metric-label">Net R</div><h2>{summary.net_r}</h2><small>Profit factor {summary.profit_factor_r ?? "—"} · win rate {percent(rate == null ? null : rate * 100)}</small></div>
        <div className="metric"><div className="metric-label">Return</div><h2 className={change != null && change < 0 ? "red" : "green"}>{percent(change, 2)}</h2><small>{money(report.starting_equity)} to {money(report.ending_equity)}</small></div>
        <div className="metric"><div className="metric-label">Max drawdown</div><h2>{money(series.maxDrawdown)}</h2><small>Peak to later trough · longest loss streak {summary.max_consecutive_losses}</small></div>
      </div>
      <section className="panel">
        <div className="panel-head">
          <div><b>Equity path</b><small>{sourceLabel(report.source)} · {rulesLabel(report.rules_source)} · spread {price(report.spread)} ({report.spread_source})</small></div>
          <span className="tag">{summary.skipped} skipped</span>
        </div>
        <EquityChart points={series.points} />
        {mixTotal > 0 && <div className="mix-wrap">
          <div className="mix" aria-hidden="true">
            <i className="win" style={{ width: `${summary.wins / mixTotal * 100}%` }} />
            <i className="loss" style={{ width: `${summary.losses / mixTotal * 100}%` }} />
            <i className="open" style={{ width: `${summary.unresolved / mixTotal * 100}%` }} />
            <i className="skip" style={{ width: `${summary.skipped / mixTotal * 100}%` }} />
          </div>
          <div className="mix-key"><span>Wins {summary.wins}</span><span>Losses {summary.losses}</span><span>Open {summary.unresolved}</span><span>Skipped {summary.skipped}</span></div>
        </div>}
      </section>
      {report.trades.some(trade => (trade.shot?.candles.length ?? 0) >= 2) && <section className="panel shot-panel">
        <details className="shot-accordion">
          <summary className="panel-head shot-summary">
            <div><b>Setup shots</b><small>Each picture is the H1 window around that signal. The lines are the levels that rule used.</small></div>
          </summary>
          <div className="shot-grid">{report.trades.map(trade => <TradeShot key={`${trade.signal_time}-${trade.entry_time}`} trade={trade} />)}</div>
        </details>
      </section>}
      <section className="panel positions">
        <div className="panel-head"><div><b>{report.symbol} trades</b><small>{report.bars_h1} H1 bars · {report.bars_h4} H4 bars · {report.requested_from && report.requested_to ? `${report.requested_from} to ${report.requested_to} UTC` : `${when(report.from_time)} to ${when(report.to_time)}`}</small></div><span className="tag">{sourceLabel(report.source)}</span></div>
        <div className="table-wrap"><table>
          <thead><tr><th>Result</th><th>Direction</th><th>Signal</th><th>Entry</th><th>Stop</th><th>Target</th><th>Exit</th><th>Lots</th><th>Risk</th><th>R</th><th>P/L</th></tr></thead>
          <tbody>
            {report.trades.length === 0 ? <tr><td colSpan={11} className="empty"><b>No trades in this run</b><small>The rules found nothing that passed the risk checks.</small></td></tr> : report.trades.map(trade => (
              <tr key={`${trade.signal_time}-${trade.direction}`}>
                <td><span className={`tag ${trade.status}`}>{trade.status}</span><small>{trade.exit_reason}</small></td>
                <td className={trade.direction === "buy" ? "green" : "red"}>{trade.direction}</td>
                <td>{when(trade.signal_time)}</td>
                <td>{price(trade.entry)}</td>
                <td>{price(trade.stop_loss)}</td>
                <td>{price(trade.take_profit)}</td>
                <td>{price(trade.exit_price)}</td>
                <td>{trade.lot_size ?? "—"}</td>
                <td>{money(trade.estimated_risk_cash)}</td>
                <td className={(trade.r_multiple ?? 0) >= 0 ? "green" : "red"}>{trade.r_multiple ?? "—"}</td>
                <td className={(trade.cash_pnl ?? 0) >= 0 ? "green" : "red"}>{money(trade.cash_pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>
      {report.skipped.length > 0 && <section className="panel"><div className="panel-head"><div><b>Skipped setups</b><small>These passed the candle rule and then failed a safety check</small></div></div>
        <div className="table-wrap"><table>
          <thead><tr><th>Time</th><th>Direction</th><th>Reason</th></tr></thead>
          <tbody>{report.skipped.map(skip => <tr key={`${skip.signal_time}-${skip.reason}`}><td>{when(skip.signal_time)}</td><td>{skip.direction ?? "—"}</td><td>{reasonText(skip.reason)}</td></tr>)}</tbody>
        </table></div>
      </section>}
    </>}
  </>
}

import type { BacktestReport } from "./types"

export type EquityPoint = { equity: number; time: number | null }

export function equitySeries(report: BacktestReport) {
  const points: EquityPoint[] = [{ equity: report.starting_equity, time: report.from_time }]
  let equity = report.starting_equity
  let peak = report.starting_equity
  let maxDrawdown = 0
  for (const trade of report.trades) {
    if (typeof trade.cash_pnl !== "number") continue
    equity = Math.round((equity + trade.cash_pnl) * 100) / 100
    peak = Math.max(peak, equity)
    maxDrawdown = Math.max(maxDrawdown, Math.round((peak - equity) * 100) / 100)
    points.push({ equity, time: trade.exit_time })
  }
  return { points, maxDrawdown, peak }
}

export function winRate(report: BacktestReport) {
  const resolved = report.summary.resolved_trades
  return resolved > 0 ? report.summary.wins / resolved : null
}

export function returnPercent(report: BacktestReport) {
  if (report.ending_equity == null || report.starting_equity <= 0) return null
  return ((report.ending_equity - report.starting_equity) / report.starting_equity) * 100
}

export function sourceLabel(source: string) {
  if (source === "sample") return "Sample fixture"
  if (source === "mt5") return "MT5 history"
  return source
}

export function rulesLabel(source: string) {
  if (source.includes("provisional")) return "Provisional H4/H1 template"
  if (source.includes("reclaim")) return "H4 trend and H1 reclaim"
  if (source.includes("h4_bias_h1_retest")) return "H4 bias and H1 level retest"
  if (source.includes("h1_close_beyond_h4")) return "H1 close beyond the H4 range"
  if (source.includes("h4_close_mitigation")) return "H4 close and prior-candle zone"
  if (source.includes("order_block")) return "H4 break and H1 order block"
  return source.replace(/_/g, " ")
}

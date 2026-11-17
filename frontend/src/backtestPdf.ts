import { jsPDF } from "jspdf"
import autoTable from "jspdf-autotable"
import { equitySeries, returnPercent, rulesLabel, sourceLabel, winRate } from "./backtestStats"
import { money, price, reasonText, when } from "./format"
import type { BacktestReport } from "./types"

function fileName(report: BacktestReport) {
  const symbol = report.symbol.replace(/[^A-Za-z0-9._-]/g, "") || "symbol"
  const day = new Date().toISOString().slice(0, 10)
  return `tradepilot-${symbol}-${report.source}-backtest-${day}.pdf`
}

function finalY(doc: jsPDF, fallback: number) {
  const placed = doc as jsPDF & { lastAutoTable?: { finalY: number } }
  return placed.lastAutoTable?.finalY ?? fallback
}

export function downloadBacktestPdf(report: BacktestReport) {
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" })
  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  const series = equitySeries(report)
  const rate = winRate(report)
  const change = returnPercent(report)
  const summary = report.summary

  const paintChrome = () => {
    doc.setFillColor(217, 173, 87)
    doc.rect(0, 0, pageWidth, 6, "F")
    doc.setFont("helvetica", "normal")
    doc.setFontSize(8)
    doc.setTextColor(110, 120, 135)
    doc.text("TradePilot research report. This is not an order and not a promise of profit.", 36, pageHeight - 18)
    doc.text(String(doc.getNumberOfPages()), pageWidth - 36, pageHeight - 18, { align: "right" })
  }

  paintChrome()
  doc.setTextColor(23, 32, 48)
  doc.setFont("helvetica", "bold")
  doc.setFontSize(18)
  doc.text(`${report.symbol} backtest`, 36, 36)
  doc.setFont("helvetica", "normal")
  doc.setFontSize(10)
  doc.setTextColor(70, 82, 99)
  doc.text(`${sourceLabel(report.source)} · ${rulesLabel(report.rules_source)} · ${report.requested_from && report.requested_to ? `${report.requested_from} to ${report.requested_to} UTC` : `${when(report.from_time)} to ${when(report.to_time)}`}`, 36, 54)

  const note = doc.splitTextToSize(report.disclaimer || "Results are research, not a promise of profit.", pageWidth - 72)
  doc.setFontSize(9)
  doc.text(note, 36, 74)
  let cursor = 74 + note.length * 12 + 8

  autoTable(doc, {
    startY: cursor,
    margin: { left: 36, right: 36, bottom: 36 },
    theme: "grid",
    styles: { font: "helvetica", fontSize: 8, textColor: [23, 32, 48], cellPadding: 5 },
    headStyles: { fillColor: [23, 32, 48], textColor: [247, 242, 230], fontStyle: "bold" },
    head: [["Resolved", "Wins", "Losses", "Open at end", "Skipped", "Net R", "Profit factor", "Win rate", "Return", "Max drawdown"]],
    body: [[
      String(summary.resolved_trades),
      String(summary.wins),
      String(summary.losses),
      String(summary.unresolved),
      String(summary.skipped),
      String(summary.net_r),
      summary.profit_factor_r == null ? "—" : String(summary.profit_factor_r),
      rate == null ? "—" : `${(rate * 100).toFixed(1)}%`,
      change == null ? "—" : `${change.toFixed(2)}%`,
      money(series.maxDrawdown),
    ]],
  })

  autoTable(doc, {
    startY: finalY(doc, cursor) + 10,
    margin: { left: 36, right: 36, bottom: 36 },
    theme: "plain",
    styles: { font: "helvetica", fontSize: 9, textColor: [70, 82, 99], cellPadding: 2 },
    body: [[
      `Started ${money(report.starting_equity)}`,
      `Ended ${money(report.ending_equity)}`,
      `Spread ${price(report.spread)} (${report.spread_source})`,
      `${report.bars_h1} H1 bars · ${report.bars_h4} H4 bars`,
      `Longest loss streak ${summary.max_consecutive_losses}`,
    ]],
  })

  doc.setFont("helvetica", "bold")
  doc.setFontSize(12)
  doc.setTextColor(23, 32, 48)
  cursor = finalY(doc, cursor) + 22
  doc.text("Trades", 36, cursor)

  autoTable(doc, {
    startY: cursor + 8,
    margin: { left: 36, right: 36, bottom: 36 },
    theme: "striped",
    styles: { font: "helvetica", fontSize: 8, textColor: [23, 32, 48], cellPadding: 4 },
    headStyles: { fillColor: [217, 173, 87], textColor: [23, 27, 35], fontStyle: "bold" },
    alternateRowStyles: { fillColor: [246, 244, 238] },
    head: [["Result", "Direction", "Signal", "Entry", "Stop", "Target", "Exit", "Lots", "Risk", "R", "P/L"]],
    body: report.trades.length === 0
      ? [["No trades passed the risk checks.", "", "", "", "", "", "", "", "", "", ""]]
      : report.trades.map(trade => [
        trade.status,
        trade.direction,
        when(trade.signal_time),
        price(trade.entry),
        price(trade.stop_loss),
        price(trade.take_profit),
        price(trade.exit_price),
        trade.lot_size == null ? "—" : String(trade.lot_size),
        money(trade.estimated_risk_cash),
        trade.r_multiple == null ? "—" : String(trade.r_multiple),
        money(trade.cash_pnl),
      ]),
    didParseCell: data => {
      if (data.section !== "body") return
      const result = String(data.row.raw && Array.isArray(data.row.raw) ? data.row.raw[0] : "")
      if (data.column.index === 0 && result === "win") data.cell.styles.textColor = [22, 120, 78]
      if (data.column.index === 0 && result === "loss") data.cell.styles.textColor = [166, 48, 48]
    },
    didDrawPage: paintChrome,
  })

  if (report.skipped.length > 0) {
    cursor = finalY(doc, cursor) + 22
    if (cursor > pageHeight - 80) {
      doc.addPage()
      paintChrome()
      cursor = 36
    }
    doc.setFont("helvetica", "bold")
    doc.setFontSize(12)
    doc.setTextColor(23, 32, 48)
    doc.text("Skipped setups", 36, cursor)
    autoTable(doc, {
      startY: cursor + 8,
      margin: { left: 36, right: 36, bottom: 36 },
      theme: "striped",
      styles: { font: "helvetica", fontSize: 8, textColor: [23, 32, 48], cellPadding: 4 },
      headStyles: { fillColor: [217, 173, 87], textColor: [23, 27, 35], fontStyle: "bold" },
      head: [["Time", "Direction", "Reason"]],
      body: report.skipped.map(skip => [when(skip.signal_time), skip.direction ?? "—", reasonText(skip.reason)]),
      didDrawPage: paintChrome,
    })
  }

  if (report.warning) {
    cursor = finalY(doc, cursor) + 18
    doc.setFont("helvetica", "normal")
    doc.setFontSize(9)
    doc.setTextColor(140, 70, 40)
    doc.text(doc.splitTextToSize(report.warning, pageWidth - 72), 36, cursor)
  }

  return doc.save(fileName(report))
}

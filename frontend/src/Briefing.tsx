import { useEffect, useState } from "react"
import { Brain, Minus, Plus } from "lucide-react"
import { getPortfolio, getSignals, scanMarket } from "./api"
import { buildDesk } from "./insight"
import type { ExecutionMode, PortfolioReport, Position, ScanResult, SignalRow, Status, Tick, View } from "./types"

export function Briefing({
  symbol, connected, status, tick, positions, mode, page, backtestLabel, onOpen,
}: {
  symbol: string
  connected: boolean
  status: Status | null
  tick: Tick | null
  positions: Position[]
  mode: ExecutionMode
  page: View
  backtestLabel: string
  onOpen: () => void
}) {
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [portfolio, setPortfolio] = useState<PortfolioReport | null>(null)
  const [signals, setSignals] = useState<SignalRow[]>([])
  const [database, setDatabase] = useState<boolean | null>(null)

  useEffect(() => {
    if (!connected) {
      setScan(null)
      setPortfolio(null)
      return
    }
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
    connected, symbol, status, tick, positions, mode, scan, portfolio, signals, signalsDatabase: database, page, backtestLabel,
  })

  return <section className="briefing" aria-label="Desk conclusion">
    <div className="briefing-head">
      <div>
        <small>DESK READ</small>
        <b>{read.stanceLabel}</b>
      </div>
      {page === "intelligence"
        ? <span className="tag">Intelligence portal</span>
        : <button type="button" className="secondary" onClick={onOpen}><Brain size={15} /> Intelligence</button>}
    </div>
    <p className="conclusion"><span>Conclusion</span>{read.conclusion}</p>
    <p className="advice"><span>Advice</span>{read.advice}</p>
    <div className="comment-grid">
      <div>
        <h3><Plus size={14} /> Positive</h3>
        <ul>{read.positive.slice(0, 4).map(item => <li key={item.title}><b>{item.title}</b>{item.text}</li>)}</ul>
      </div>
      <div>
        <h3><Minus size={14} /> Negative</h3>
        <ul>{read.negative.slice(0, 4).map(item => <li key={item.title}><b>{item.title}</b>{item.text}</li>)}</ul>
      </div>
    </div>
  </section>
}

import { useCallback, useEffect, useRef, useState } from "react"
import { AlertTriangle, ShieldCheck } from "lucide-react"
import { decideSignal, executeDemo, getCandles, getSignals, scanMarket } from "./api"
import { CandleChart } from "./Candles"
import { CHECK_LABELS, money, price, reasonText, when } from "./format"
import type { CandleBar, ExecutionMode, ScanResult, SignalRow } from "./types"

export function Signals({ symbol, connected, environment, currency, mode, onMode, onConnect, onBias }: { symbol: string; connected: boolean; environment: string; currency: string; mode: ExecutionMode; onMode: (mode: ExecutionMode) => void; onConnect: () => void; onBias: (bias: string) => void }) {
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [rows, setRows] = useState<SignalRow[]>([])
  const [database, setDatabase] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [note, setNote] = useState("")
  const [armed, setArmed] = useState<string | null>(null)
  const [armAuto, setArmAuto] = useState(false)
  const armingAuto = useRef(false)
  const [sending, setSending] = useState(false)
  const [h4, setH4] = useState<CandleBar[]>([])
  const [h1, setH1] = useState<CandleBar[]>([])
  const [candleError, setCandleError] = useState("")
  const running = useRef(false)

  async function load() {
    const data = await getSignals()
    setRows(data.items)
    setDatabase(data.database_connected)
  }

  useEffect(() => { void load().catch(() => setDatabase(false)) }, [])

  const scanNow = useCallback(async () => {
    if (running.current) return
    running.current = true
    setBusy(true)
    setError("")
    try {
      const result = await scanMarket(symbol)
      setScan(result)
      onBias(result.bias)
      if (result.storage_error) {
        setNote(result.storage_error)
      } else if (mode === "auto" && result.proposal) {
        setNote("Auto is on. This setup is sent once from any page while the app stays open.")
      } else if (result.proposal) {
        setNote("Manual is on. Review the candles, then use Send and confirm.")
      } else if (!armingAuto.current) {
        setNote("")
      }
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed")
    } finally {
      running.current = false
      setBusy(false)
    }
  }, [mode, onBias, symbol])

  useEffect(() => {
    if (!connected) return
    let stopped = false
    async function loadCandles() {
      try {
        const [higher, lower] = await Promise.all([getCandles(symbol, "H4", 40), getCandles(symbol, "H1", 48)])
        if (!stopped) {
          setH4(higher.items)
          setH1(lower.items)
          setCandleError("")
        }
      } catch (err) {
        if (!stopped) setCandleError(err instanceof Error ? err.message : "Candles are unavailable")
      }
    }
    void loadCandles()
    const id = window.setInterval(() => { void loadCandles() }, 15000)
    return () => { stopped = true; window.clearInterval(id) }
  }, [connected, symbol])

  const tradable = environment === "demo" || environment === "live"
  const live = environment === "live"

  function chooseMode(next: ExecutionMode) {
    if (next === "manual") {
      armingAuto.current = false
      setArmAuto(false)
      onMode("manual")
      setNote("Manual is on. An order waits for Send, then Confirm.")
      return
    }
    if (!tradable) return
    if (!armAuto) {
      armingAuto.current = true
      setArmAuto(true)
      setNote(live
        ? "Auto sends the current live setup and later ones on every page while this app stays open. This uses real money. Click Confirm auto to turn it on."
        : "Auto sends the current demo setup and later ones on every page while this app stays open. Click Confirm auto to turn it on.")
      return
    }
    armingAuto.current = false
    setArmAuto(false)
    onMode("auto")
  }

  useEffect(() => {
    if (!connected) return
    void scanNow()
    const id = window.setInterval(() => { void scanNow() }, 30000)
    return () => window.clearInterval(id)
  }, [connected, scanNow])

  async function send(key: string) {
    if (armed !== key) {
      setArmed(key)
      setNote(live ? "Check the lots and cash risk. Confirm live order sends a real market order." : "Check the lots and cash risk. Confirm demo order sends a market order on the demo account.")
      return
    }
    setSending(true)
    setError("")
    try {
      const result = await executeDemo(symbol, key)
      setArmed(null)
      setNote(result.storage_error || `${result.message} Ticket ${result.ticket}, ${result.volume} lots at ${price(result.price)}.`)
      await load()
    } catch (err) {
      setArmed(null)
      setError(err instanceof Error ? err.message : "The order was not sent")
    } finally {
      setSending(false)
    }
  }

  async function decide(id: number, action: "approve" | "reject") {
    setError("")
    try {
      const row = await decideSignal(id, action)
      setNote(row.message || "Decision stored. No order was sent to MT5.")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed")
    }
  }

  const proposal = scan?.stored_signal ?? null
  const setup = scan?.proposal ?? null
  return <>
    <div className="heading">
      <div>
        <small>APPROVAL QUEUE</small>
        <h1>Signals</h1>
        <p>H4 bias is a close beyond the prior H4 high or low. A buy fills at the ask only after price returns to the previous hour's high from above.</p>
      </div>
      <div className="row-actions">
        <div className="mode-toggle" role="group" aria-label="Execution mode">
          <button type="button" className={mode === "manual" ? "active" : ""} onClick={() => chooseMode("manual")}>Manual</button>
          <button type="button" className={mode === "auto" ? "active" : ""} disabled={!tradable} onClick={() => chooseMode("auto")}>{mode === "auto" ? "Auto on" : armAuto ? "Confirm auto" : "Auto"}</button>
        </div>
        {connected ? <button className="primary" disabled={busy} onClick={() => void scanNow()}>{busy ? "Scanning…" : "Scan now"}</button> : <button className="primary" onClick={onConnect}>Connect MT5</button>}
      </div>
    </div>
    <div className="alert"><ShieldCheck />{mode === "auto" ? `Auto is on for this ${live ? "live" : "demo"} account. A new setup is sent from any page. Switch to Manual to stop it.` : `Manual is on. Nothing is sent until you click Send and then Confirm. ${live ? "This account is live, so a confirmed order uses real money." : "Auto is a second choice."}`}</div>
    {error && <div className="alert error"><AlertTriangle />{error}</div>}
    {note && <div className="alert"><ShieldCheck />{note}</div>}
    {database === false && <div className="alert"><AlertTriangle />PostgreSQL is not connected, so the decision history is not saved. A confirmed order from the latest scan can still be sent.</div>}
    <div className="metrics">
      <div className="metric"><div className="metric-label">H4 bias</div><h2>{scan ? scan.bias : "—"}</h2><small>Latest closed candles</small></div>
      <div className="metric"><div className="metric-label">Kept today</div><h2>{scan ? String(scan.trades_kept_today) : "—"}</h2><small>Entries today, limit 2</small></div>
      <div className="metric"><div className="metric-label">Open position</div><h2>{scan ? (scan.position_open ? "Yes" : "No") : "—"}</h2><small>Blocks a new setup on this symbol</small></div>
      <div className="metric"><div className="metric-label">Execution</div><h2>{!tradable ? "Blocked" : mode === "auto" ? "Auto" : "Manual"}</h2><small>{live ? "Live account" : environment === "demo" ? "Demo account" : "This account cannot send"}</small></div>
    </div>
    {scan?.checks && <div className="checks">{Object.entries(CHECK_LABELS).map(([key, label]) => <span key={key} className={scan.checks?.[key] ? "pass" : "fail"}>{label}</span>)}</div>}
    <div className="two-col">
      <section className="panel"><CandleChart candles={h4} label="H4 bias" /></section>
      <section className="panel"><CandleChart candles={h1} highlight={setup?.signal_time} label="H1 setup" /></section>
    </div>
    {candleError && <div className="alert error"><AlertTriangle />{candleError}</div>}
    <section className="panel positions">
      <div className="panel-head"><div><b>Recent H1 candles</b><small>Open, high, low, close. The newest bar is still forming.</small></div></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th></th></tr></thead>
        <tbody>{h1.slice(-8).reverse().map(candle => <tr key={candle.time} className={setup?.signal_time === candle.time ? "marked" : ""}><td>{when(candle.time)}</td><td>{price(candle.open)}</td><td>{price(candle.high)}</td><td>{price(candle.low)}</td><td className={candle.close >= candle.open ? "green" : "red"}>{price(candle.close)}</td><td>{setup?.signal_time === candle.time ? "Signal" : candle === h1[h1.length - 1] ? "Forming" : ""}</td></tr>)}</tbody>
      </table></div>
    </section>
    <section className="panel positions">
      <div className="panel-head"><div><b>Latest scan</b><small>{scan?.rules_source ?? "Waiting for a scan"}</small></div></div>
      {!scan && <p className="footnote">Connect MT5 and scan. The page repeats the scan every 30 seconds while it is open.</p>}
      {scan && !scan.proposal && <p className="footnote">{reasonText(scan.skip_reason) || "No setup on the latest closed hour."}</p>}
      {setup && <div className="table-wrap"><table>
        <thead><tr><th>Direction</th><th>Entry</th><th>Stop</th><th>Target</th><th>Lots</th><th>Risk</th><th>Signal time</th><th></th></tr></thead>
        <tbody><tr>
          <td className={setup.direction === "buy" ? "green" : "red"}>{setup.direction}</td>
          <td>{price(setup.entry)}</td>
          <td>{price(setup.stop_loss)}</td>
          <td>{price(setup.take_profit)}</td>
          <td>{setup.lot_size ?? "—"}{setup.capped ? " capped" : ""}</td>
          <td>{money(setup.estimated_risk_cash, currency)}</td>
          <td>{when(setup.signal_time)}</td>
          <td><span className="row-actions">
            {tradable && mode === "manual" && <button className="primary" disabled={sending} onClick={() => void send(setup.dedupe_key)}>{armed === setup.dedupe_key ? (live ? "Confirm live order" : "Confirm demo order") : (live ? "Send live order" : "Send on demo")}</button>}
            {tradable && mode === "auto" && <span className="tag">Auto sends this</span>}
            {!tradable && <span className="tag">Account cannot send</span>}
            {proposal && proposal.status === "pending" && <button className="secondary" onClick={() => void decide(proposal.id, "reject")}>Reject</button>}
          </span></td>
        </tr></tbody>
      </table></div>}
    </section>
    <section className="panel">
      <div className="panel-head"><div><b>Stored decisions</b><small>PostgreSQL</small></div><span className="tag">{rows.length}</span></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Status</th><th>Symbol</th><th>Direction</th><th>Entry</th><th>Stop</th><th>Target</th><th>Lots</th><th>Risk</th><th>Candle</th><th></th></tr></thead>
        <tbody>
          {rows.length === 0 ? <tr><td colSpan={10} className="empty"><b>No stored signals</b><small>Start PostgreSQL, then scan.</small></td></tr> : rows.map(row => (
            <tr key={row.id}>
              <td><span className={`tag ${row.status}`}>{row.status}</span></td>
              <td>{row.symbol}</td>
              <td className={row.direction === "buy" ? "green" : "red"}>{row.direction}</td>
              <td>{price(row.entry)}</td>
              <td>{price(row.stop_loss)}</td>
              <td>{price(row.take_profit)}</td>
              <td>{row.lot_size ?? "—"}</td>
              <td>{money(row.estimated_risk, currency)}</td>
              <td>{when(row.bar_time)}</td>
              <td>{row.status === "pending" && <span className="row-actions"><button className="primary" onClick={() => void decide(row.id, "approve")}>Approve</button><button className="danger" onClick={() => void decide(row.id, "reject")}>Reject</button></span>}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
    </section>
  </>
}

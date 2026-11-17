import { useEffect, useState } from "react"
import { ShieldCheck } from "lucide-react"
import { getRules } from "./api"
import { Detail } from "./components"
import type { Rules } from "./types"

export function Strategy() {
  const [rules, setRules] = useState<Rules | null>(null)
  const [error, setError] = useState("")
  useEffect(() => { void getRules().then(setRules).catch(err => setError(err instanceof Error ? err.message : "Could not load rules")) }, [])
  return <>
    <div className="heading">
      <div>
        <small>RULES</small>
        <h1>Strategy</h1>
        <p>H4 bias comes from a close beyond the prior H4 high or low. An H1 close beyond the previous hour's high or low saves that level, and the order waits for price to come back to it.</p>
      </div>
    </div>
    {error && <div className="alert error">{error}</div>}
    <div className="two-col">
      <section className="panel">
        <div className="panel-head"><div><b>Locked safety limits</b><small>The API does not accept overrides</small></div><ShieldCheck /></div>
        <Detail label="Risk per trade" value="2% of equity, floored to the lot step" />
        <Detail label="Reward to risk" value="1:5" />
        <Detail label="Trades per Ghana day" value="2 entries" />
        <Detail label="Duplicate position" value="Blocked on the same symbol" />
        <Detail label="Order submission" value="Demo and live, after confirmation. Contest accounts stay blocked." />
        <Detail label="Rules source" value={rules?.rules_source ?? "Loading"} />
      </section>
      <section className="panel">
        <div className="panel-head"><div><b>How a scan behaves</b><small>Closed candles only</small></div></div>
        <Detail label="Live entry" value="Ask for a buy, bid for a sell" />
        <Detail label="Backtest entry" value="Return to the prior H1 high or low on a later bar" />
        <Detail label="Same-candle stop and target" value="Counted as a loss" />
        <Detail label="Market Watch" value="Reading a symbol selects it in the terminal" />
        <Detail label="Mobile" value="Use the TradePilot Expo app against your cloud VPS API" />
      </section>
    </div>
    <section className="panel">
      <div className="panel-head"><div><b>Template steps</b><small>Replace backend/app/strategy/engine.py when your original rules are available</small></div></div>
      <ol className="rules">{(rules?.rules ?? []).map(rule => <li key={rule}>{rule}</li>)}</ol>
    </section>
  </>
}

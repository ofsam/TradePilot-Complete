import { Server } from "lucide-react"
import { Detail } from "./components"
import { money } from "./format"
import type { Status } from "./types"

export function Accounts({ status }: { status: Status | null }) {
  const connected = !!status?.connected
  return <>
    <div className="heading">
      <div>
        <small>TERMINAL</small>
        <h1>Accounts</h1>
        <p>This build reads the single MetaTrader 5 terminal logged in on this computer.</p>
      </div>
    </div>
    <section className="panel">
      <div className="panel-head"><div><b>{connected ? status?.login || "Connected account" : "No terminal account"}</b><small>{status?.broker_server || "Connect MT5 from Overview"}</small></div><Server /></div>
      <Detail label="Environment" value={status?.environment || "unknown"} />
      <Detail label="Company" value={status?.account_company || "—"} />
      <Detail label="Balance" value={connected ? money(status?.balance, status?.currency || "USD") : "—"} />
      <Detail label="Equity" value={connected ? money(status?.equity, status?.currency || "USD") : "—"} />
      <Detail label="Additional accounts" value="Later milestone" />
    </section>
    <p className="footnote">A scan stores this login when PostgreSQL is running. Switching brokers means logging into that account in the desktop terminal, then connecting again.</p>
  </>
}

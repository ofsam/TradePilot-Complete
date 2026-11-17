import { useState } from "react"
import { ChartCandlestick } from "lucide-react"
import { requestLoginCode, setSessionToken, verifyLoginCode } from "./api"

export function LoginGate({ onDone }: { onDone: (email: string) => void }) {
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function sendCode() {
    setBusy(true)
    setError("")
    try {
      await requestLoginCode(email.trim())
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the code.")
    } finally {
      setBusy(false)
    }
  }

  async function verify() {
    setBusy(true)
    setError("")
    try {
      const result = await verifyLoginCode(email.trim(), code.trim())
      setSessionToken(result.token)
      onDone(result.email)
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code did not work.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="gate">
      <div className="gate-card">
        <div className="brand"><div className="mark"><ChartCandlestick /></div><div><b>TradePilot</b><small>EMAIL LOGIN</small></div></div>
        <p>Enter your email for a one-time code. Orders and Auto stay behind this login on cloud hosts.</p>
        <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label>
        {sent && <label>Code<input value={code} maxLength={4} onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 4))} inputMode="numeric" /></label>}
        {error && <p className="error">{error}</p>}
        {!sent
          ? <button type="button" disabled={busy || email.trim().length < 6} onClick={() => void sendCode()}>{busy ? "Sending…" : "Send code"}</button>
          : <button type="button" disabled={busy || code.length !== 4} onClick={() => void verify()}>{busy ? "Checking…" : "Open desk"}</button>}
      </div>
    </div>
  )
}

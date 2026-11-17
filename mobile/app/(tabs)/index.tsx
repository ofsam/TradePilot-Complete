import { useCallback, useEffect, useState } from "react"
import { AppState, ScrollView, StyleSheet, Text } from "react-native"
import { connectMT5, getDesk, getPortfolio, getStatus, getTick } from "../../lib/api"
import { money, price } from "../../lib/format"
import type { DeskState, PortfolioReport, Status, Tick } from "../../lib/types"
import { colors } from "../../lib/theme"
import { Card, ErrorText, PrimaryButton, Row, Screen, SecondaryButton, Title } from "../../components/ui"

export default function OverviewScreen() {
  const [status, setStatus] = useState<Status | null>(null)
  const [desk, setDesk] = useState<DeskState | null>(null)
  const [tick, setTick] = useState<Tick | null>(null)
  const [portfolio, setPortfolio] = useState<PortfolioReport | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState(AppState.currentState === "active")

  const symbol = desk?.symbols?.[0] || "EURUSD"

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextDesk, nextPortfolio] = await Promise.all([
        getStatus(),
        getDesk(),
        getPortfolio().catch(() => null),
      ])
      setStatus(nextStatus)
      setDesk(nextDesk)
      setPortfolio(nextPortfolio)
      const sym = nextDesk.symbols?.[0] || "EURUSD"
      if (nextStatus.connected) {
        const quote = await getTick(sym).catch(() => null)
        setTick(quote)
      } else {
        setTick(null)
      }
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cannot reach the cloud API.")
    }
  }, [])

  useEffect(() => {
    const sub = AppState.addEventListener("change", state => setActive(state === "active"))
    return () => sub.remove()
  }, [])

  useEffect(() => {
    if (!active) return
    void refresh()
    const id = setInterval(() => void refresh(), 10000)
    return () => clearInterval(id)
  }, [active, refresh])

  useEffect(() => {
    if (!active || !status?.connected) return
    const id = setInterval(() => {
      void getTick(symbol).then(setTick).catch(() => undefined)
    }, 3000)
    return () => clearInterval(id)
  }, [active, status?.connected, symbol])

  async function connect() {
    setBusy(true)
    setError("")
    try {
      await connectMT5()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Title>Overview</Title>
        <Card>
          <Text style={styles.hero}>{symbol}</Text>
          <Text style={styles.price}>
            {tick ? `${price(tick.bid)} / ${price(tick.ask)}` : "No quote"}
          </Text>
          <Row label="Account" value={status?.login ? String(status.login) : "—"} />
          <Row label="Environment" value={status?.environment || "unknown"} />
          <Row label="Equity" value={money(portfolio?.equity ?? status?.equity, status?.currency || "USD")} />
          <Row label="Desk" value={desk ? `${desk.mode}${desk.running ? " · running" : ""}` : "—"} />
          <Row label="Server" value={status?.broker_server || "—"} />
        </Card>
        <ErrorText>{error}</ErrorText>
        {status?.connected ? (
          <SecondaryButton label="Refresh" onPress={() => void refresh()} />
        ) : (
          <PrimaryButton label="Connect MT5 on VPS" onPress={() => void connect()} busy={busy} />
        )}
      </ScrollView>
    </Screen>
  )
}

const styles = StyleSheet.create({
  scroll: { gap: 12, paddingBottom: 24 },
  hero: { color: colors.muted, fontSize: 12, fontWeight: "700", letterSpacing: 1 },
  price: { color: colors.text, fontSize: 28, fontWeight: "800", marginBottom: 6 },
})

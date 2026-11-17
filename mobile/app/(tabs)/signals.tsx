import { useCallback, useEffect, useState } from "react"
import { AppState, FlatList, StyleSheet, Text, View } from "react-native"
import { ConfirmSheet } from "../../components/ConfirmSheet"
import { executeOrder, getDesk, getSignals, scanMarket } from "../../lib/api"
import { price } from "../../lib/format"
import type { ScanProposal, SignalRow } from "../../lib/types"
import { colors } from "../../lib/theme"
import { Card, ErrorText, PrimaryButton, Screen, SecondaryButton, Title } from "../../components/ui"

export default function SignalsScreen() {
  const [items, setItems] = useState<SignalRow[]>([])
  const [executionEnabled, setExecutionEnabled] = useState(false)
  const [symbol, setSymbol] = useState("EURUSD")
  const [proposal, setProposal] = useState<ScanProposal | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [scanBusy, setScanBusy] = useState(false)
  const [error, setError] = useState("")
  const [note, setNote] = useState("")
  const [active, setActive] = useState(AppState.currentState === "active")

  const refresh = useCallback(async () => {
    try {
      const [desk, signals] = await Promise.all([getDesk(), getSignals()])
      setSymbol(desk.symbols?.[0] || "EURUSD")
      setItems(signals.items || [])
      setExecutionEnabled(!!signals.execution_enabled)
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load signals.")
    }
  }, [])

  useEffect(() => {
    const sub = AppState.addEventListener("change", state => setActive(state === "active"))
    return () => sub.remove()
  }, [])

  useEffect(() => {
    if (!active) return
    void refresh()
    const id = setInterval(() => void refresh(), 15000)
    return () => clearInterval(id)
  }, [active, refresh])

  async function scan() {
    setScanBusy(true)
    setError("")
    setNote("")
    try {
      const result = await scanMarket(symbol)
      if (result.proposal) {
        setProposal(result.proposal)
        setConfirmOpen(true)
      } else {
        setProposal(null)
        setNote(result.skip_reason || `No setup (${result.bias}).`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed")
    } finally {
      setScanBusy(false)
    }
  }

  async function confirm() {
    if (!proposal) return
    setBusy(true)
    setError("")
    try {
      const order = await executeOrder(symbol, proposal.dedupe_key)
      setNote(order.storage_error || order.message || `Sent ${order.direction} ticket ${order.ticket}`)
      setConfirmOpen(false)
      setProposal(null)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Screen>
      <Title>Signals</Title>
      <Text style={styles.meta}>
        Symbol {symbol} · Execution {executionEnabled ? "on" : "off"}
      </Text>
      <PrimaryButton label="Scan & confirm" onPress={() => void scan()} busy={scanBusy} />
      <SecondaryButton label="Refresh list" onPress={() => void refresh()} />
      <ErrorText>{error}</ErrorText>
      {note ? <Text style={styles.note}>{note}</Text> : null}
      <FlatList
        data={items}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>No stored signals yet.</Text>}
        renderItem={({ item }) => (
          <Card>
            <View style={styles.head}>
              <Text style={styles.symbol}>{item.symbol}</Text>
              <Text style={styles.status}>{item.status || "—"}</Text>
            </View>
            <Text style={styles.meta}>
              {item.direction || "—"} · entry {price(item.entry)} · SL {price(item.stop_loss)} · TP {price(item.take_profit)}
            </Text>
          </Card>
        )}
      />
      <ConfirmSheet
        visible={confirmOpen}
        symbol={symbol}
        proposal={proposal}
        busy={busy}
        error={error}
        onCancel={() => {
          if (!busy) {
            setConfirmOpen(false)
            setProposal(null)
          }
        }}
        onConfirm={() => void confirm()}
      />
    </Screen>
  )
}

const styles = StyleSheet.create({
  list: { gap: 10, paddingBottom: 40 },
  empty: { color: colors.muted, marginTop: 20, textAlign: "center" },
  head: { flexDirection: "row", justifyContent: "space-between" },
  symbol: { color: colors.text, fontWeight: "800", fontSize: 16 },
  status: { color: colors.accent, fontWeight: "700" },
  meta: { color: colors.muted, fontSize: 12 },
  note: { color: colors.success, fontSize: 13 },
})

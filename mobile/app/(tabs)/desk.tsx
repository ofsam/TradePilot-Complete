import { useCallback, useEffect, useState } from "react"
import { AppState, StyleSheet, Text, View } from "react-native"
import { getDesk, setDeskMode, setDeskSymbols } from "../../lib/api"
import { validSymbol } from "../../lib/format"
import type { DeskState } from "../../lib/types"
import { colors } from "../../lib/theme"
import { Card, ErrorText, Field, PrimaryButton, Screen, SecondaryButton, Title } from "../../components/ui"

export default function DeskScreen() {
  const [desk, setDesk] = useState<DeskState | null>(null)
  const [symbolsText, setSymbolsText] = useState("EURUSD")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [active, setActive] = useState(AppState.currentState === "active")

  const refresh = useCallback(async () => {
    try {
      const next = await getDesk()
      setDesk(next)
      setSymbolsText((next.symbols || []).join(", ") || "EURUSD")
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load desk.")
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

  function parseSymbols() {
    return symbolsText
      .split(/[,\s]+/)
      .map(s => s.trim().toUpperCase())
      .filter(validSymbol)
      .slice(0, 12)
  }

  async function saveSymbols() {
    const symbols = parseSymbols()
    if (!symbols.length) {
      setError("Enter at least one broker symbol.")
      return
    }
    setBusy(true)
    setError("")
    try {
      const next = await setDeskSymbols(symbols)
      setDesk(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save symbols.")
    } finally {
      setBusy(false)
    }
  }

  async function setMode(mode: "manual" | "auto") {
    setBusy(true)
    setError("")
    try {
      const symbols = parseSymbols()
      const next = await setDeskMode(mode, symbols.length ? symbols : undefined)
      setDesk(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change mode.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Screen>
      <Title>Auto desk</Title>
      <Card>
        <Text style={styles.mode}>Mode: {desk?.mode || "—"}</Text>
        <Text style={styles.meta}>
          VPS Auto loop {desk?.running ? "is running" : "is idle"}. The phone only flips mode; orders in Auto are sent by the worker.
        </Text>
        <View style={styles.toggle}>
          <SecondaryButton
            label="Manual"
            onPress={() => void setMode("manual")}
            disabled={busy || desk?.mode === "manual"}
          />
          <PrimaryButton
            label="Auto"
            onPress={() => void setMode("auto")}
            busy={busy && desk?.mode !== "auto"}
            disabled={busy || desk?.mode === "auto"}
          />
        </View>
      </Card>
      <Field
        label="WATCHLIST (comma separated)"
        value={symbolsText}
        onChangeText={setSymbolsText}
        autoCapitalize="characters"
      />
      <PrimaryButton label="Save watchlist" onPress={() => void saveSymbols()} busy={busy} />
      <SecondaryButton label="Refresh" onPress={() => void refresh()} />
      <ErrorText>{error}</ErrorText>
    </Screen>
  )
}

const styles = StyleSheet.create({
  mode: { color: colors.text, fontSize: 18, fontWeight: "800" },
  meta: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  toggle: { flexDirection: "row", gap: 8, marginTop: 8 },
})

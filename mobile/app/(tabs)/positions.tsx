import { useCallback, useEffect, useState } from "react"
import { AppState, FlatList, StyleSheet, Text, View } from "react-native"
import { getPositions } from "../../lib/api"
import { money, price } from "../../lib/format"
import type { Position } from "../../lib/types"
import { colors } from "../../lib/theme"
import { Card, ErrorText, Screen, SecondaryButton, Title } from "../../components/ui"

export default function PositionsScreen() {
  const [items, setItems] = useState<Position[]>([])
  const [error, setError] = useState("")
  const [active, setActive] = useState(AppState.currentState === "active")

  const refresh = useCallback(async () => {
    try {
      const data = await getPositions()
      setItems(data.items || [])
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load positions.")
    }
  }, [])

  useEffect(() => {
    const sub = AppState.addEventListener("change", state => setActive(state === "active"))
    return () => sub.remove()
  }, [])

  useEffect(() => {
    if (!active) return
    void refresh()
    const id = setInterval(() => void refresh(), 5000)
    return () => clearInterval(id)
  }, [active, refresh])

  return (
    <Screen>
      <Title>Positions</Title>
      <SecondaryButton label="Refresh" onPress={() => void refresh()} />
      <ErrorText>{error}</ErrorText>
      <FlatList
        data={items}
        keyExtractor={item => String(item.ticket)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>No open positions.</Text>}
        renderItem={({ item }) => (
          <Card>
            <View style={styles.head}>
              <Text style={styles.symbol}>{item.symbol}</Text>
              <Text style={[styles.pnl, { color: item.profit >= 0 ? colors.success : colors.danger }]}>
                {money(item.profit)}
              </Text>
            </View>
            <Text style={styles.meta}>
              {item.type} · {item.volume} lots · #{item.ticket}
            </Text>
            <Text style={styles.meta}>
              Open {price(item.price_open)} · Now {price(item.price_current)}
            </Text>
            <Text style={styles.meta}>
              SL {price(item.sl)} · TP {price(item.tp)}
            </Text>
          </Card>
        )}
      />
    </Screen>
  )
}

const styles = StyleSheet.create({
  list: { gap: 10, paddingBottom: 40 },
  empty: { color: colors.muted, marginTop: 20, textAlign: "center" },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  symbol: { color: colors.text, fontWeight: "800", fontSize: 16 },
  pnl: { fontWeight: "800", fontSize: 16 },
  meta: { color: colors.muted, fontSize: 12 },
})

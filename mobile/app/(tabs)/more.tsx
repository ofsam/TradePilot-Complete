import { useEffect, useState } from "react"
import { StyleSheet, Text } from "react-native"
import { useAuth } from "../../lib/auth"
import { getApiBase, getHealth } from "../../lib/api"
import { colors } from "../../lib/theme"
import { Card, ErrorText, Row, Screen, SecondaryButton, Title } from "../../components/ui"

export default function MoreScreen() {
  const { email, signOut } = useAuth()
  const [health, setHealth] = useState<string>("—")
  const [execution, setExecution] = useState("—")
  const [error, setError] = useState("")

  useEffect(() => {
    void getHealth()
      .then(h => {
        setHealth(h.status)
        setExecution(h.execution_enabled ? "enabled" : "disabled")
      })
      .catch(err => setError(err instanceof Error ? err.message : "Health check failed"))
  }, [])

  return (
    <Screen>
      <Title>More</Title>
      <Card>
        <Row label="Signed in" value={email || "—"} />
        <Row label="API" value={getApiBase()} />
        <Row label="Health" value={health} />
        <Row label="Execution" value={execution} />
      </Card>
      <Text style={styles.hint}>
        Point EXPO_PUBLIC_API_BASE_URL at your Windows VPS HTTPS URL. MT5 and Auto run on that worker, not on this phone.
      </Text>
      <ErrorText>{error}</ErrorText>
      <SecondaryButton label="Sign out" onPress={() => void signOut()} />
    </Screen>
  )
}

const styles = StyleSheet.create({
  hint: { color: colors.muted, fontSize: 13, lineHeight: 18 },
})

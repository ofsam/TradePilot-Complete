import { useState } from "react"
import { StyleSheet, Text, View } from "react-native"
import { useAuth } from "../lib/auth"
import { getApiBase } from "../lib/api"
import { colors } from "../lib/theme"
import { ErrorText, Field, PrimaryButton, Screen } from "../components/ui"

export default function LoginScreen() {
  const { requestCode, verify } = useAuth()
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function send() {
    setBusy(true)
    setError("")
    try {
      await requestCode(email)
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the code.")
    } finally {
      setBusy(false)
    }
  }

  async function check() {
    setBusy(true)
    setError("")
    try {
      await verify(email, code)
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code did not work.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Screen>
      <View style={styles.hero}>
        <Text style={styles.brand}>TradePilot</Text>
        <Text style={styles.sub}>Cloud desk · Android & iPhone</Text>
        <Text style={styles.hint}>API: {getApiBase()}</Text>
      </View>
      <Field label="EMAIL" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
      {sent ? (
        <Field
          label="CODE"
          value={code}
          onChangeText={v => setCode(v.replace(/\D/g, "").slice(0, 4))}
          keyboardType="number-pad"
          maxLength={4}
        />
      ) : null}
      <ErrorText>{error}</ErrorText>
      {!sent ? (
        <PrimaryButton label="Send code" onPress={() => void send()} busy={busy} disabled={email.trim().length < 6} />
      ) : (
        <PrimaryButton label="Open desk" onPress={() => void check()} busy={busy} disabled={code.length !== 4} />
      )}
    </Screen>
  )
}

const styles = StyleSheet.create({
  hero: { gap: 6, marginBottom: 8, marginTop: 40 },
  brand: { color: colors.accent, fontSize: 32, fontWeight: "800" },
  sub: { color: colors.text, fontSize: 16, fontWeight: "600" },
  hint: { color: colors.muted, fontSize: 12 },
})

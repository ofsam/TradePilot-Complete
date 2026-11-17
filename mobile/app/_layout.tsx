import { Stack, useRouter, useSegments } from "expo-router"
import { useEffect } from "react"
import { ActivityIndicator, View } from "react-native"
import { StatusBar } from "expo-status-bar"
import { AuthProvider, useAuth } from "../lib/auth"
import { colors } from "../lib/theme"

function AuthGate({ children }: { children: React.ReactNode }) {
  const { ready, email } = useAuth()
  const segments = useSegments()
  const router = useRouter()

  useEffect(() => {
    if (!ready) return
    const onLogin = segments[0] === "login"
    if (!email && !onLogin) router.replace("/login")
    if (email && onLogin) router.replace("/(tabs)")
  }, [ready, email, segments, router])

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    )
  }

  return <>{children}</>
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <StatusBar style="light" />
      <AuthGate>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }} />
      </AuthGate>
    </AuthProvider>
  )
}

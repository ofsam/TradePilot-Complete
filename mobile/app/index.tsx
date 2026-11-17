import { Redirect } from "expo-router"
import { useAuth } from "../lib/auth"

export default function Index() {
  const { email, ready } = useAuth()
  if (!ready) return null
  return <Redirect href={email ? "/(tabs)" : "/login"} />
}

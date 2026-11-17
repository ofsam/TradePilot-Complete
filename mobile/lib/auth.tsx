import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import * as SecureStore from "expo-secure-store"
import { getAuthMe, setApiToken, verifyLoginCode, requestLoginCode } from "./api"

const TOKEN_KEY = "tradepilot.session"
const EMAIL_KEY = "tradepilot.email"

type AuthState = {
  ready: boolean
  email: string | null
  requestCode: (email: string) => Promise<void>
  verify: (email: string, code: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function boot() {
      try {
        const token = await SecureStore.getItemAsync(TOKEN_KEY)
        if (!token) {
          if (!cancelled) setEmail(null)
          return
        }
        setApiToken(token)
        const me = await getAuthMe()
        if (!cancelled) setEmail(me.email)
      } catch {
        await SecureStore.deleteItemAsync(TOKEN_KEY)
        setApiToken("")
        if (!cancelled) setEmail(null)
      } finally {
        if (!cancelled) setReady(true)
      }
    }
    void boot()
    return () => {
      cancelled = true
    }
  }, [])

  const requestCode = useCallback(async (value: string) => {
    await requestLoginCode(value.trim().toLowerCase())
  }, [])

  const verify = useCallback(async (value: string, code: string) => {
    const result = await verifyLoginCode(value.trim().toLowerCase(), code.trim())
    setApiToken(result.token)
    await SecureStore.setItemAsync(TOKEN_KEY, result.token)
    await SecureStore.setItemAsync(EMAIL_KEY, result.email)
    setEmail(result.email)
  }, [])

  const signOut = useCallback(async () => {
    setApiToken("")
    setEmail(null)
    await SecureStore.deleteItemAsync(TOKEN_KEY)
    await SecureStore.deleteItemAsync(EMAIL_KEY)
  }, [])

  const value = useMemo(
    () => ({ ready, email, requestCode, verify, signOut }),
    [ready, email, requestCode, verify, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}

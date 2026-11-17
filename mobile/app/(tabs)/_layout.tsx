import { Tabs } from "expo-router"
import { colors } from "../../lib/theme"

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        tabBarStyle: { backgroundColor: "#0e1624", borderTopColor: colors.border },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Overview" }} />
      <Tabs.Screen name="positions" options={{ title: "Positions" }} />
      <Tabs.Screen name="signals" options={{ title: "Signals" }} />
      <Tabs.Screen name="desk" options={{ title: "Auto" }} />
      <Tabs.Screen name="more" options={{ title: "More" }} />
    </Tabs>
  )
}

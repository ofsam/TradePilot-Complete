import type { ReactNode } from "react"

export function Metric({ icon, label, value, note }: { icon: ReactNode; label: string; value: string; note: string }) {
  return <div className="metric"><div className="metric-label"><span>{icon}</span>{label}</div><h2>{value}</h2><small>{note}</small></div>
}

export function Detail({ label, value }: { label: string; value: string }) {
  return <div className="detail"><span>{label}</span><b>{value}</b></div>
}

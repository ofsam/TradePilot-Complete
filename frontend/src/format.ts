export function money(value?: number | null, currency = "USD") {
  if (typeof value !== "number" || Number.isNaN(value)) return "—"
  const code = /^[A-Z]{3}$/.test(currency) ? currency : "USD"
  return new Intl.NumberFormat("en-US", { style: "currency", currency: code, maximumFractionDigits: 2 }).format(value)
}

export function price(value?: number | null, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—"
}

export function validSymbol(symbol: string) {
  return /^[A-Z0-9._#-]{2,32}$/.test(symbol)
}

export function when(unix?: number | null) {
  return typeof unix === "number" ? new Date(unix * 1000).toLocaleString() : "—"
}

const REASONS: Record<string, string> = {
  daily_limit: "This Ghana day already has two kept signals.",
  position_open: "This symbol already has an open position.",
  below_min_lot: "Sizing at 2% is below the broker minimum lot, so the setup was skipped.",
  stop_too_small: "The stop is closer than the minimum distance.",
  stop_too_wide: "The stop distance is outside the range this model allows, so the setup is skipped.",
  invalid_geometry: "Entry and stop do not form a valid order.",
  invalid_symbol_spec: "The terminal did not provide a usable tick value or lot step.",
  invalid_prices: "The candle prices could not be used.",
  not_enough_candles: "There are not enough closed H1 or H4 candles yet.",
  neutral_bias: "No H4 close, and no H1 close, has finished beyond the prior H4 high or low.",
  no_setup: "There is no H1 close beyond the previous hour's high or low waiting for a retest.",
  waiting_retest: "The H1 break is saved. Price has not returned to that high or low from the breakout side.",
}

export const CHECK_LABELS: Record<string, string> = {
  enough_h4: "H4 bar",
  h4_bias: "H4 bias",
  h1_setup: "H1 break",
  retest: "Retest",
  stop_cap: "Stop cap",
}

export function reasonText(reason?: string | null) {
  if (!reason) return ""
  return REASONS[reason] ?? reason
}

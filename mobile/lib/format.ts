export function money(value?: number | null, currency = "USD") {
  if (value == null || Number.isNaN(value)) return "—"
  return `${value.toFixed(2)} ${currency}`
}

export function price(value?: number | null, digits = 5) {
  if (value == null || Number.isNaN(value)) return "—"
  return value.toFixed(digits)
}

export function validSymbol(value: string) {
  return /^[A-Za-z0-9 ._()#-]{2,32}$/.test(value.trim())
}

import type { CandleBar } from "./types"

export function CandleChart({ candles, highlight, label }: { candles: CandleBar[]; highlight?: number | null; label: string }) {
  if (candles.length < 2) return <p className="footnote">Waiting for {label} candles.</p>
  const width = 720
  const height = 230
  const padLeft = 8
  const padRight = 58
  const padY = 14
  const max = Math.max(...candles.map(candle => candle.high))
  const min = Math.min(...candles.map(candle => candle.low))
  const span = max - min || 1
  const plotWidth = width - padLeft - padRight
  const plotHeight = height - padY * 2
  const slot = plotWidth / candles.length
  const y = (value: number) => padY + ((max - value) / span) * plotHeight
  const last = candles[candles.length - 1]
  return <figure className="chart">
    <figcaption><b>{label}</b><small>{candles.length} bars · last close {last.close.toFixed(2)} · the rightmost bar is still forming</small></figcaption>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} candlestick chart`}>
      {[0, 0.5, 1].map(step => {
        const value = min + span * step
        const yPos = y(value)
        return <g key={step}>
          <line x1={padLeft} x2={width - padRight} y1={yPos} y2={yPos} className="grid" />
          <text x={width - padRight + 6} y={yPos + 3} className="axis">{value.toFixed(2)}</text>
        </g>
      })}
      {candles.map((candle, index) => {
        const up = candle.close >= candle.open
        const x = padLeft + index * slot + slot / 2
        const bodyTop = y(Math.max(candle.open, candle.close))
        const bodyBottom = y(Math.min(candle.open, candle.close))
        const marked = highlight != null && candle.time === highlight
        return <g key={candle.time}>
          {marked && <rect x={x - slot / 2} y={padY} width={slot} height={plotHeight} className="mark" />}
          <line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} className={up ? "up" : "down"} />
          <rect x={x - Math.max(slot * 0.28, 1.5)} y={bodyTop} width={Math.max(slot * 0.56, 3)} height={Math.max(bodyBottom - bodyTop, 1)} className={up ? "up" : "down"} />
        </g>
      })}
    </svg>
  </figure>
}

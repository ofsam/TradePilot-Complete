import { money, price, reasonText } from "./format"
import type { ExecutionMode, PortfolioReport, Position, ScanResult, SignalRow, Status, Tick } from "./types"

export type Note = { title: string; text: string }
export type CheckRead = { key: string; label: string; pass: boolean; meaning: string }

export type DeskRead = {
  stance: "offline" | "wait" | "ready" | "blocked"
  stanceLabel: string
  conclusion: string
  advice: string
  positive: Note[]
  negative: Note[]
  checks: CheckRead[]
  knowledge: Note[]
  history: Note[]
  signals: Note[]
}

const CHECKS: Record<string, { label: string; pass: string; fail: string }> = {
  enough_h4: {
    label: "H4 bar",
    pass: "A closed H4 bar is available as the bias reference.",
    fail: "There is no closed H4 bar yet, so bias cannot be judged.",
  },
  h4_bias: {
    label: "H4 bias",
    pass: "A closed H4, or an H1 inside the forming H4, has closed beyond the prior H4 high or low.",
    fail: "No close has finished beyond the prior H4 high or low. A wick alone does not count.",
  },
  h1_setup: {
    label: "H1 break",
    pass: "The latest closed hour closed beyond the previous hour's high or low, and that level is the retest.",
    fail: "There is no saved H1 high or low waiting for price to come back.",
  },
  retest: {
    label: "Retest",
    pass: "Price has returned to that high or low from the breakout side.",
    fail: "Price has not returned to the saved high or low from the breakout side.",
  },
  stop_cap: {
    label: "Stop cap",
    pass: "The stop is the breakout hour's wick and is under 100 pips.",
    fail: "The stop is 100 pips or more, so this H1 setup is invalid.",
  },
}

const PAGE_NOTE: Record<string, string> = {
  overview: "Overview is the quote and the account. An order is still sent from Signals.",
  portfolio: "Use the open risk on this page before you add another position.",
  signals: "This is the page that can send. Manual still needs Send, then Confirm.",
  backtest: "A backtest is research on past candles. It is not a promise about the next trade.",
  strategy: "These written rules are the only entry path. A comment here does not add a new rule.",
  journal: "Journal is the stored audit. An empty list means PostgreSQL has no saved decisions.",
  intelligence: "This portal is the full read of the same scan, history, and rules.",
}

function push(list: Note[], title: string, text: string) {
  list.push({ title, text })
}

export function buildDesk(input: {
  connected: boolean
  symbol: string
  status: Status | null
  tick: Tick | null
  positions: Position[]
  mode: ExecutionMode
  scan: ScanResult | null
  portfolio: PortfolioReport | null
  signals: SignalRow[]
  signalsDatabase: boolean | null
  page: string
  backtestLabel: string
}): DeskRead {
  const { connected, symbol, status, tick, positions, mode, scan, portfolio, signals, signalsDatabase, page, backtestLabel } = input
  const currency = status?.currency || "USD"
  const env = status?.environment || "unknown"
  const tradable = env === "demo" || env === "live"
  const spread = tick ? tick.ask - tick.bid : null
  const capital = typeof status?.equity === "number" ? status.equity : status?.balance
  const twoPercent = typeof capital === "number" ? capital * 0.02 : null
  const proposal = scan?.proposal ?? null
  const positive: Note[] = []
  const negative: Note[] = []

  if (!connected) {
    push(positive, "Rules stay fixed", "Risk stays at or under 2%, the target stays at 5 times the stop, and the Ghana day still allows only two entries.")
    push(negative, "No terminal read", "There is no quote, so this desk cannot judge structure, spread, or open risk.")
    return {
      stance: "offline",
      stanceLabel: "Offline",
      conclusion: `${symbol} has no connected terminal, so there is no trade to accept or reject.`,
      advice: `Connect MT5, then read the scan before you decide. ${PAGE_NOTE[page] ?? ""}`.trim(),
      positive,
      negative,
      checks: [],
      knowledge: knowledge({ symbol, bias: "unknown", twoPercent, currency, proposal: false }),
      history: [note("History unavailable", "Deal history is read from the terminal after it connects.")],
      signals: [note("Signals unavailable", "Stored decisions need both a connection and PostgreSQL.")],
    }
  }

  if (spread !== null && spread <= 0.8) push(positive, "Spread is usable", `The quote spread is ${price(spread)}.`)
  else if (spread !== null) push(negative, "Spread is wide", `The quote spread is ${price(spread)}. This H4 and H1 plan does not block on spread, but a wide spread worsens the fill.`)

  if (status?.trade_allowed && tradable) push(positive, "Orders are allowed", env === "live" ? "This login can send, and a confirmed order uses real money." : "This demo login can send after you confirm.")
  else push(negative, "Orders are blocked", tradable ? "The terminal reports that trading is not allowed." : "Contest and unknown accounts cannot send from this app.")

  if (env === "live") push(negative, "Real money", "A live fill can lose cash. Auto, once confirmed, sends without another click on any page.")
  if (mode === "auto" && tradable) push(negative, "Auto is armed", "A new setup can leave while you are on any page. Switch to Manual on Signals to stop it.")
  else if (tradable) push(positive, "Manual is in control", "Nothing is sent until you click Send and then Confirm.")

  if (scan?.bias === "long" || scan?.bias === "short") push(positive, "H4 bias is set", `A close beyond the prior H4 high or low is confirmed. Bias is ${scan.bias}.`)
  else if (scan) push(negative, "No H4 bias", "No H4 close, and no H1 close, has finished beyond the prior H4 high or low.")

  if (proposal) {
    push(positive, "A setup passed", `${proposal.direction} ${symbol} at ${price(proposal.entry)}, stop ${price(proposal.stop_loss)}, target ${price(proposal.take_profit)}.`)
    if (proposal.estimated_risk_cash != null) {
      push(positive, "Risk is sized", `${money(proposal.estimated_risk_cash, currency)} planned risk on ${proposal.lot_size ?? "—"} lots, floored so it stays at or under 2%.`)
    }
  } else if (scan?.skip_reason) {
    push(negative, "Setup skipped", reasonText(scan.skip_reason))
  } else if (scan) {
    push(negative, "No entry yet", "Price has not returned to the saved H1 high or low.")
  }

  const kept = scan?.trades_kept_today ?? portfolio?.our_entries_today
  if (typeof kept === "number") {
    if (kept >= 2) push(negative, "Daily cap is full", "Two entries are already counted for this Ghana day. The next setup waits until the next Ghana day.")
    else push(positive, "Room in the daily cap", `${kept} of 2 entries used this Ghana day.`)
  }

  if (scan?.position_open || positions.length > 0) {
    push(negative, "A position is open", positions.length > 0
      ? `${positions.length} open position${positions.length === 1 ? "" : "s"}. A new setup on the same symbol is skipped while one is open.`
      : "The scan sees an open position, so a second trade on this symbol waits.")
  } else push(positive, "Symbol is flat", "No open position is blocking a new setup on this symbol.")

  const unprotected = positions.filter(position => !position.sl || position.sl <= 0).length
  if (unprotected > 0) push(negative, "A stop is missing", `${unprotected} open position${unprotected === 1 ? " has" : "s have"} no stop. Cash risk is not capped.`)
  const floating = positions.reduce((sum, position) => sum + position.profit, 0)
  if (positions.length > 0 && floating < 0) push(negative, "Open trades are down", `Floating result is ${money(floating, currency)}.`)
  else if (positions.length > 0 && floating > 0) push(positive, "Open trades are up", `Floating result is ${money(floating, currency)}. That can reverse before the stop or target.`)

  const history = historyNotes(portfolio, currency)
  for (const item of history) {
    if (item.title === "Closed book is ahead" || item.title === "Sample is still small") positive.push(item)
    if (item.title === "Closed book is behind" || item.title === "History did not load") negative.push(item)
  }

  if (signalsDatabase === false) push(negative, "Decisions are not stored", "PostgreSQL is down, so approve, reject, and scan history will not be saved.")
  const pending = signals.filter(row => row.status === "pending").length
  if (pending > 0) push(negative, "Decisions are waiting", `${pending} stored signal${pending === 1 ? " is" : "s are"} still pending. Approving one does not send an order.`)

  push(negative, "The plan can still lose more", "A gap or slippage can pass the stop. Planned risk is a ceiling only when the stop fills near the planned price.")

  const checks = Object.entries(CHECKS).map(([key, copy]) => {
    const pass = !!scan?.checks?.[key]
    return { key, label: copy.label, pass, meaning: pass ? copy.pass : copy.fail }
  })

  const stance: DeskRead["stance"] = !tradable || status?.trade_allowed === false ? "blocked" : proposal ? "ready" : "wait"
  const direction = proposal?.direction === "sell" ? "sell" : "buy"
  const conclusion = !scan
    ? `${symbol} is connected. The first scan has not returned a read yet.`
    : proposal
      ? `${symbol} has a confirmed ${direction}. Entry ${price(proposal.entry)}, stop ${price(proposal.stop_loss)}, target ${price(proposal.take_profit)}.`
      : scan.bias === "long" || scan.bias === "short"
        ? `${symbol} bias is ${scan.bias}. ${reasonText(scan.skip_reason) || "Price has not returned to the saved H1 high or low."}`
        : `${symbol} has no H4 bias, so the decision is to wait.`

  const adviceCore = proposal
    ? (mode === "auto"
      ? "Auto can send this setup from any page. Switch to Manual if you do not want it sent."
      : "If you still want it, open Signals, check the lots and cash risk, then Send and Confirm.")
    : scan?.skip_reason
      ? `Leave the order unsent. ${reasonText(scan.skip_reason)}`
      : "Leave the order unsent until price returns to the saved H1 high or low."
  const research = page === "backtest" && backtestLabel !== "Not run" ? ` Latest saved label: ${backtestLabel}.` : ""
  const advice = `${adviceCore} ${PAGE_NOTE[page] ?? ""}${research}`.trim()

  return {
    stance,
    stanceLabel: stance === "ready" ? "Setup ready" : stance === "blocked" ? "Blocked" : "Wait",
    conclusion,
    advice,
    positive: unique(positive).slice(0, 6),
    negative: unique(negative).slice(0, 6),
    checks,
    knowledge: knowledge({ symbol, bias: scan?.bias || "unknown", twoPercent, currency, proposal: !!proposal }),
    history,
    signals: signalNotes(signals, signalsDatabase),
  }
}

function note(title: string, text: string): Note {
  return { title, text }
}

function unique(items: Note[]) {
  const seen = new Set<string>()
  return items.filter(item => {
    if (seen.has(item.title)) return false
    seen.add(item.title)
    return true
  })
}

function historyNotes(portfolio: PortfolioReport | null, currency: string): Note[] {
  if (!portfolio) return [note("History unavailable", "The portfolio read has not returned yet.")]
  if (portfolio.history_error) return [note("History did not load", portfolio.history_error)]
  const closed = portfolio.closed_trades
  if (closed <= 0) return [note("No closed sample", `No closing deals in the last ${portfolio.history_days} days. Past results cannot support this decision.`)]
  const rate = portfolio.wins / closed
  const net = `${money(portfolio.net_profit, currency)} net over ${portfolio.history_days} days, from ${portfolio.wins} wins and ${portfolio.losses} losses.`
  if (closed < 8) return [note("Sample is still small", `${closed} closed deals. ${net} That count is too small to treat as a record.`)]
  if (portfolio.net_profit >= 0) return [note("Closed book is ahead", `${net} Win share ${(rate * 100).toFixed(0)}%. This is account history, not proof the next setup wins.`)]
  return [note("Closed book is behind", `${net} Win share ${(rate * 100).toFixed(0)}%. A losing book is a reason to stay selective, not a reason to force a trade.`)]
}

function signalNotes(signals: SignalRow[], database: boolean | null): Note[] {
  if (database === false) return [note("Signal store is down", "PostgreSQL is not connected, so this portal cannot read old approvals.")]
  if (signals.length === 0) return [note("No stored signals", "A scan that finds a setup will appear here after PostgreSQL is running.")]
  const approved = signals.filter(row => row.status === "approved").length
  const rejected = signals.filter(row => row.status === "rejected").length
  const pending = signals.filter(row => row.status === "pending").length
  const sent = signals.filter(row => row.order_submitted).length
  return [
    note("Decision mix", `${signals.length} stored signals: ${pending} pending, ${approved} approved, ${rejected} rejected, ${sent} marked sent.`),
    note("What a row means", "Approve and reject are audit decisions. An order is sent only from a confirmed setup on a demo or live account."),
  ]
}

function knowledge(input: { symbol: string; bias: string; twoPercent: number | null; currency: string; proposal: boolean }): Note[] {
  const budget = input.twoPercent == null ? "2% of equity" : money(input.twoPercent, input.currency)
  return [
    note("How a side is chosen", input.bias === "long"
      ? `${input.symbol} is long because a close finished above the prior H4 high.`
      : input.bias === "short"
        ? `${input.symbol} is short because a close finished below the prior H4 low.`
        : `${input.symbol} has no side until an H4 close, or an H1 close inside the forming H4, finishes beyond the prior H4 high or low.`),
    note("How an entry is chosen", "The latest closed hour must close beyond the previous hour's high for a buy, or its low for a sell. That high or low is the level. A buy fills at the ask after price returns to it from above. A sell fills at the bid after price returns to it from below. The setup is saved only from 08:00 to 17:00 in London or New York."),
    note("How size is chosen", `The stop is the breakout hour's low for a buy and its high for a sell. A stop of 100 pips or more invalidates the setup. The target is 5 times the stop distance. Lots are floored so planned cash risk stays at or under ${budget}.`),
    note("When to stand aside", "No H4 bias, no return to the saved level, an open position, or two entries already taken this Ghana day are all reasons to do nothing."),
    note("What this read is not", input.proposal
      ? "A passing setup is permission to consider the trade. It is not a forecast that the target will hit."
      : "Waiting is a decision. An 80% win rate is a research target, and this desk does not claim it."),
  ]
}

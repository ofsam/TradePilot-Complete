"""Desk-aware TradePilot chat: rich context, read-only tools, session memory, optional OpenAI."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from app import desk
from app.mt5.adapter import mt5_adapter
from app.mt5.execution import MAGIC
from app.strategy.engine import MAX_STOP_PIPS, RULES, RULES_SOURCE, TARGET_R
from app.strategy.risk import MAX_TRADES_PER_DAY, RISK_FRACTION

# Load backend/.env so OPENAI_* is available via os.getenv (not only pydantic Settings fields).
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

MEMORY_LIMIT = 20
TOOL_ROUNDS = 4
ACCRA = ZoneInfo("Africa/Accra")

SYSTEM_RULES = """You are TradePilot's desk assistant for a MetaTrader 5 control center on this PC.

Hard rules:
1. Use only TradePilot/MT5 data from tools or the provided context. If data is missing, say so.
2. Never invent tickets, fills, balances, or win rates. Never claim an 80% win rate.
3. Explain skips clearly when relevant: waiting_retest, below_min_lot, stop_too_wide, daily_limit, Auto on a different symbol than Watchlist, trade_allowed false.
4. No financial advice and no promises about future profits. Describe what the system reports.
5. Read-only: you cannot Send, Confirm, or place orders. Say that if asked to execute.
6. Be concise and factual. Prefer short paragraphs over fluff.
7. When Auto symbol and Watchlist symbol differ, call that out first.
"""

_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_desk",
            "description": "Desk Auto/Manual mode and which symbols Auto is scanning.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account",
            "description": "Connected MT5 account status: environment, balance, trade_allowed.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scan",
            "description": "Live H4/H1 scan for a symbol: bias, checks, skip_reason, proposal.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "Broker/watchlist symbol such as EURUSD"}},
                "required": ["symbol"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Open risk, wins/losses, floating P/L, entries today.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_signals",
            "description": "Recent stored signals including approved-but-not-submitted.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notices",
            "description": "Recent desk notices and skip alerts.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bars",
            "description": "Recent H1 and H4 closed-bar summary for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_strategy",
            "description": "Strategy rules, risk fraction, reward multiple, daily cap, stop pip limit.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_magic_deals",
            "description": "Recent MT5 deals with TradePilot magic 20261030.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]

_lock = threading.Lock()
_sessions: dict[str, list[dict[str, str]]] = {}


def _safe(call, default=None):
    try:
        return call()
    except Exception as exc:
        if isinstance(default, dict):
            return {**default, "error": str(exc)}
        return default


def _openai_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _openai_model() -> str:
    return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"


def _trim_scan(scan: Any) -> dict[str, Any] | None:
    if not isinstance(scan, dict):
        return None
    proposal = scan.get("proposal")
    return {
        "bias": scan.get("bias"),
        "skip_reason": scan.get("skip_reason"),
        "checks": scan.get("checks"),
        "proposal": None
        if not proposal
        else {
            "direction": proposal.get("direction"),
            "entry": proposal.get("entry"),
            "stop_loss": proposal.get("stop_loss"),
            "take_profit": proposal.get("take_profit"),
            "lot_size": proposal.get("lot_size"),
            "estimated_risk_cash": proposal.get("estimated_risk_cash") or proposal.get("estimated_risk"),
            "dedupe_key": proposal.get("dedupe_key"),
        },
        "error": scan.get("error") or scan.get("detail"),
    }


def _run_scan(symbol: str) -> dict[str, Any]:
    try:
        from app.routers.strategy import ScanBody, scan as scan_endpoint

        return scan_endpoint(ScanBody(symbol=symbol))
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        return {"error": str(detail or exc)}


def _list_signals(limit: int = 12) -> list[dict[str, Any]]:
    try:
        from app.strategy import store as strategy_store

        db = strategy_store.open_session()
        if db is None:
            return []
        try:
            rows = strategy_store.list_signals(db, limit)
            out = []
            for row in rows or []:
                if hasattr(strategy_store, "signal_dict"):
                    out.append(strategy_store.signal_dict(row))
                elif isinstance(row, dict):
                    out.append(row)
            return out
        finally:
            db.close()
    except Exception:
        return []


def _saved_limits() -> dict[str, Any]:
    try:
        from app.strategy import store as strategy_store

        db = strategy_store.open_session()
        if db is None:
            return {
                "risk_fraction": RISK_FRACTION,
                "reward_multiple": TARGET_R,
                "max_stop_pips": MAX_STOP_PIPS,
                "max_trades_per_day": MAX_TRADES_PER_DAY,
                "source": "code_defaults",
            }
        try:
            limits = strategy_store.saved_limits(db)
            if isinstance(limits, dict):
                return limits
            return {"raw": str(limits)}
        finally:
            db.close()
    except Exception:
        return {
            "risk_fraction": RISK_FRACTION,
            "reward_multiple": TARGET_R,
            "max_stop_pips": MAX_STOP_PIPS,
            "max_trades_per_day": MAX_TRADES_PER_DAY,
            "source": "code_defaults",
        }


def notify_items(limit: int = 12) -> list[dict[str, Any]]:
    from app import notify

    raw = notify.list_notices(limit) if hasattr(notify, "list_notices") else []
    if isinstance(raw, dict):
        return list(raw.get("items") or [])[:limit]
    if isinstance(raw, list):
        return raw[:limit]
    return []


def _bar_summary(symbol: str, timeframe: str, count: int = 6) -> list[dict[str, Any]]:
    rows = _safe(lambda: mt5_adapter.rates(symbol, timeframe, count), [])
    out = []
    for row in rows[-count:] if isinstance(rows, list) else []:
        ts = int(row.get("time") or 0)
        out.append(
            {
                "time_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
            }
        )
    return out


def _magic_deals(days: int = 7) -> list[dict[str, Any]]:
    deals = _safe(lambda: mt5_adapter.deals(days), [])
    if not isinstance(deals, list):
        return []
    chosen = [d for d in deals if int(d.get("magic") or 0) == MAGIC]
    chosen.sort(key=lambda d: int(d.get("time") or 0), reverse=True)
    out = []
    for d in chosen[:20]:
        ts = int(d.get("time") or 0)
        out.append(
            {
                "ticket": d.get("ticket"),
                "symbol": d.get("symbol"),
                "type": d.get("type"),
                "entry": d.get("entry"),
                "volume": d.get("volume"),
                "price": d.get("price"),
                "profit": d.get("profit"),
                "time_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
                "magic": d.get("magic"),
            }
        )
    return out


def tool_get_desk() -> dict[str, Any]:
    state = desk.state()
    return {
        "mode": state.get("mode"),
        "symbols": state.get("symbols") or [],
        "running": state.get("running"),
    }


def tool_get_account() -> dict[str, Any]:
    status = _safe(mt5_adapter.status, {"connected": False})
    if not isinstance(status, dict):
        return {"connected": False}
    return {
        "connected": status.get("connected"),
        "environment": status.get("environment"),
        "login": status.get("login"),
        "broker_server": status.get("broker_server"),
        "currency": status.get("currency"),
        "trade_allowed": status.get("trade_allowed"),
        "balance": status.get("balance"),
        "equity": status.get("equity"),
        "free_margin": status.get("free_margin"),
    }


def tool_get_scan(symbol: str) -> dict[str, Any]:
    return _trim_scan(_run_scan(symbol)) or {"error": "No scan result"}


def tool_get_portfolio() -> dict[str, Any]:
    portfolio = _safe(lambda: mt5_adapter.portfolio(30), {})
    positions = _safe(mt5_adapter.positions, [])
    if not isinstance(portfolio, dict):
        portfolio = {}
    return {
        "open_positions": portfolio.get("open_positions"),
        "floating_pnl": portfolio.get("floating_pnl"),
        "stop_risk_cash": portfolio.get("stop_risk_cash"),
        "our_entries_today": portfolio.get("our_entries_today"),
        "max_trades_per_day": portfolio.get("max_trades_per_day", MAX_TRADES_PER_DAY),
        "wins": portfolio.get("wins"),
        "losses": portfolio.get("losses"),
        "net_profit": portfolio.get("net_profit"),
        "closed_trades": portfolio.get("closed_trades"),
        "positions": positions[:20] if isinstance(positions, list) else [],
    }


def tool_get_signals() -> dict[str, Any]:
    rows = _list_signals(12)
    slim = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        slim.append(
            {
                "id": row.get("id"),
                "symbol": row.get("symbol"),
                "direction": row.get("direction"),
                "status": row.get("status"),
                "order_submitted": row.get("order_submitted"),
                "order_ticket": row.get("order_ticket"),
                "entry": row.get("entry"),
                "stop_loss": row.get("stop_loss"),
                "take_profit": row.get("take_profit"),
                "created_at": row.get("created_at"),
                "expires_at": row.get("expires_at"),
            }
        )
    approved_unsent = [r for r in slim if r.get("status") == "approved" and not r.get("order_submitted")]
    return {"items": slim, "approved_not_submitted": approved_unsent}


def tool_get_notices() -> dict[str, Any]:
    items = []
    for row in notify_items(12):
        if isinstance(row, dict):
            items.append(
                {
                    "id": row.get("id"),
                    "kind": row.get("kind"),
                    "title": row.get("title"),
                    "body": row.get("body"),
                    "created_at": row.get("created_at"),
                }
            )
    return {"items": items}


def tool_get_bars(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "h1": _bar_summary(symbol, "H1", 6),
        "h4": _bar_summary(symbol, "H4", 4),
    }


def tool_get_strategy() -> dict[str, Any]:
    limits = _saved_limits()
    return {
        "rules_source": RULES_SOURCE,
        "rules": RULES,
        "code_target_r": TARGET_R,
        "code_risk_fraction": RISK_FRACTION,
        "code_max_stop_pips": MAX_STOP_PIPS,
        "code_max_trades_per_day": MAX_TRADES_PER_DAY,
        "saved_limits": limits,
        "magic": MAGIC,
    }


def tool_get_magic_deals() -> dict[str, Any]:
    return {"magic": MAGIC, "items": _magic_deals(7)}


def _dispatch_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "get_desk":
        return tool_get_desk()
    if name == "get_account":
        return tool_get_account()
    if name == "get_scan":
        return tool_get_scan(str(args.get("symbol") or "XAUUSD"))
    if name == "get_portfolio":
        return tool_get_portfolio()
    if name == "get_signals":
        return tool_get_signals()
    if name == "get_notices":
        return tool_get_notices()
    if name == "get_bars":
        return tool_get_bars(str(args.get("symbol") or "XAUUSD"))
    if name == "get_strategy":
        return tool_get_strategy()
    if name == "get_magic_deals":
        return tool_get_magic_deals()
    return {"error": f"Unknown tool {name}"}


def build_context(symbol: str | None = None) -> dict[str, Any]:
    desk_state = tool_get_desk()
    auto_syms = desk_state.get("symbols") or []
    chosen = (symbol or "").strip() or (auto_syms[0] if auto_syms else "XAUUSD")
    account = tool_get_account()
    scan = tool_get_scan(chosen) if account.get("connected") else {"error": "MT5 not connected"}
    portfolio = tool_get_portfolio()
    signals = tool_get_signals()
    notices = tool_get_notices()
    strategy = tool_get_strategy()
    bars = _safe(lambda: tool_get_bars(chosen), {"symbol": chosen, "h1": [], "h4": []})
    deals = _safe(tool_get_magic_deals, {"magic": MAGIC, "items": []})
    mismatch = bool(auto_syms) and chosen not in auto_syms
    return {
        "watch_symbol": chosen,
        "auto_symbols": auto_syms,
        "auto_watchlist_mismatch": mismatch,
        "desk": desk_state,
        "account": account,
        "scan": scan,
        "portfolio": {
            "open_positions": portfolio.get("open_positions"),
            "floating_pnl": portfolio.get("floating_pnl"),
            "our_entries_today": portfolio.get("our_entries_today"),
            "max_trades_per_day": portfolio.get("max_trades_per_day"),
            "wins": portfolio.get("wins"),
            "losses": portfolio.get("losses"),
            "net_profit": portfolio.get("net_profit"),
            "closed_trades": portfolio.get("closed_trades"),
        },
        "positions": portfolio.get("positions") or [],
        "signals": signals.get("items") or [],
        "approved_not_submitted": signals.get("approved_not_submitted") or [],
        "notices": notices.get("items") or [],
        "bars": bars,
        "strategy": strategy,
        "magic_deals": deals.get("items") or [],
        "ghana_now": datetime.now(ACCRA).isoformat(),
    }


def _public_ctx(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "watch_symbol": ctx.get("watch_symbol"),
        "auto_symbols": ctx.get("auto_symbols"),
        "auto_watchlist_mismatch": ctx.get("auto_watchlist_mismatch"),
        "desk": ctx.get("desk"),
        "account": ctx.get("account"),
        "scan": ctx.get("scan"),
        "portfolio": ctx.get("portfolio"),
        "approved_not_submitted": ctx.get("approved_not_submitted"),
        "notices": (ctx.get("notices") or [])[:5],
        "bars": ctx.get("bars"),
        "strategy": {
            "rules_source": (ctx.get("strategy") or {}).get("rules_source"),
            "saved_limits": (ctx.get("strategy") or {}).get("saved_limits"),
            "code_target_r": (ctx.get("strategy") or {}).get("code_target_r"),
            "code_risk_fraction": (ctx.get("strategy") or {}).get("code_risk_fraction"),
            "magic": MAGIC,
        },
        "magic_deals": (ctx.get("magic_deals") or [])[:8],
        "ghana_now": ctx.get("ghana_now"),
    }


def _session_id(raw: str | None) -> str:
    value = (raw or "").strip()
    if value and len(value) <= 80:
        return value
    return uuid.uuid4().hex


def _memory_get(session_id: str) -> list[dict[str, str]]:
    with _lock:
        return list(_sessions.get(session_id) or [])


def _memory_append(session_id: str, role: str, content: str) -> None:
    with _lock:
        hist = _sessions.setdefault(session_id, [])
        hist.append({"role": role, "content": content})
        if len(hist) > MEMORY_LIMIT:
            _sessions[session_id] = hist[-MEMORY_LIMIT:]


def answer(message: str, symbol: str | None = None, session_id: str | None = None) -> dict[str, Any]:
    text = (message or "").strip()
    sid = _session_id(session_id)
    if not text:
        return {
            "reply": "Ask about the desk, Auto, a setup, wins/losses, or why an order was not sent.",
            "source": "desk",
            "session_id": sid,
        }
    ctx = build_context(symbol)
    _memory_append(sid, "user", text)
    history = _memory_get(sid)

    if _openai_key():
        reply = _openai_agent(history, ctx)
        source = "openai"
        if not reply:
            reply = _local_reply(text, ctx, history)
            source = "desk_fallback"
    else:
        reply = _local_reply(text, ctx, history)
        source = "desk"

    _memory_append(sid, "assistant", reply)
    return {
        "reply": reply,
        "source": source,
        "session_id": sid,
        "model": _openai_model() if source.startswith("openai") else None,
        "openai_configured": bool(_openai_key()),
        "context": _public_ctx(ctx),
    }


def _openai_post(payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_openai_key()}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _openai_agent(history: list[dict[str, str]], ctx: dict[str, Any]) -> str | None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_RULES},
        {
            "role": "system",
            "content": "Fresh desk snapshot JSON:\n" + json.dumps(_public_ctx(ctx), default=str)[:14000],
        },
    ]
    for item in history[-MEMORY_LIMIT:]:
        role = item.get("role")
        if role in {"user", "assistant"} and item.get("content"):
            messages.append({"role": role, "content": item["content"]})

    try:
        for _ in range(TOOL_ROUNDS):
            data = _openai_post(
                {
                    "model": _openai_model(),
                    "temperature": 0.2,
                    "tools": _TOOL_DEFS,
                    "tool_choice": "auto",
                    "messages": messages,
                }
            )
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                content = (msg.get("content") or "").strip()
                return content or None
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.get("content"),
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                fn = (call.get("function") or {})
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = _dispatch_tool(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, default=str)[:8000],
                    }
                )
        # Final pass without tools if still looping
        data = _openai_post(
            {
                "model": _openai_model(),
                "temperature": 0.2,
                "messages": messages
                + [{"role": "user", "content": "Give the final concise answer now using the tool results."}],
            }
        )
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip() or None
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, TimeoutError):
        return None


def _local_reply(message: str, ctx: dict[str, Any], history: list[dict[str, str]] | None = None) -> str:
    q = message.lower()
    desk_state = ctx.get("desk") or {}
    account = ctx.get("account") or {}
    scan = ctx.get("scan") or {}
    portfolio = ctx.get("portfolio") or {}
    symbol = ctx.get("watch_symbol") or "-"
    auto_syms = ctx.get("auto_symbols") or []
    mode = desk_state.get("mode") or "manual"
    mismatch = bool(ctx.get("auto_watchlist_mismatch"))
    prior_users = [h.get("content") or "" for h in (history or []) if h.get("role") == "user"][:-1][-4:]

    preface = ""
    if mismatch:
        preface = f"Mismatch: Watchlist/context is {symbol}, Auto is reading {auto_syms}. "

    if prior_users and any(k in q for k in ("what did i", "i just", "earlier", "remember", "mentioned", "last question", "i said")):
        return preface + "From this chat session you said: " + " | ".join(prior_users)

    if any(k in q for k in ("who are you", "what can you", "help", "commands")):
        return (
            preface
            + "I am the TradePilot desk assistant. I can explain Auto vs Watchlist, account state, "
            "setups/skips, strategy limits, wins/losses, signals, notices, and magic deals. "
            "Add OPENAI_API_KEY to backend/.env for tool-using smarter answers."
        )

    if any(k in q for k in ("auto", "watchlist", "reading", "scanning", "mismatch", "hard code", "hardcoded")):
        reading = ", ".join(auto_syms) if auto_syms else "(none)"
        line = f"Desk mode is {mode}. Auto is reading: {reading}. Chat/watch context symbol is {symbol}."
        if mismatch:
            line += " Those do not match - Auto is not scanning your selected market."
        return line

    if any(k in q for k in ("balance", "equity", "account", "margin", "trade permission", "trade_allowed")):
        if not account.get("connected"):
            return preface + "MT5 is not connected. Connect from Overview first."
        return (
            preface
            + f"Account {account.get('login')} on {account.get('broker_server')} "
            f"({account.get('environment')}). Balance ${account.get('balance')}, "
            f"equity ${account.get('equity')}, trade_allowed={account.get('trade_allowed')}, "
            f"currency {account.get('currency')}."
        )

    if any(k in q for k in ("setup", "scan", "bias", "retest", "skip", "why no", "not taken", "didn't take", "did not take")):
        if scan.get("error"):
            return preface + f"Scan failed for {symbol}: {scan['error']}"
        prop = scan.get("proposal")
        if prop:
            return (
                preface
                + f"{symbol} bias is {scan.get('bias')}. Live proposal: "
                f"{prop.get('direction')} entry {prop.get('entry')}, stop {prop.get('stop_loss')}, "
                f"target {prop.get('take_profit')}, lots {prop.get('lot_size')}, "
                f"risk ${prop.get('estimated_risk_cash')}."
            )
        checks = scan.get("checks") or {}
        return (
            preface
            + f"{symbol} bias={scan.get('bias')}, skip={scan.get('skip_reason')}. "
            f"Checks: H4 bias={checks.get('h4_bias')}, H1 setup={checks.get('h1_setup')}, "
            f"retest={checks.get('retest')}, stop_cap={checks.get('stop_cap')}. "
            "A proposal is only ready when retest is true and sizing/permission pass."
        )

    if any(k in q for k in ("win", "loss", "pnl", "profit", "drawdown", "closed")):
        return (
            preface
            + f"Portfolio window: closed trades={portfolio.get('closed_trades')}, "
            f"wins={portfolio.get('wins')}, losses={portfolio.get('losses')}, "
            f"net_profit=${portfolio.get('net_profit')}, floating=${portfolio.get('floating_pnl')}, "
            f"entries today={portfolio.get('our_entries_today')}/{portfolio.get('max_trades_per_day')}."
        )

    if any(k in q for k in ("position", "open trade", "floating")):
        positions = ctx.get("positions") or []
        if not positions:
            return preface + "No open positions on the terminal right now."
        bits = [
            f"{p.get('symbol')} {'buy' if p.get('type') == 0 else 'sell'} {p.get('volume')} @ {p.get('price_open')} (P/L {p.get('profit')})"
            for p in positions[:8]
        ]
        return preface + "Open positions: " + "; ".join(bits)

    if any(k in q for k in ("signal", "approved", "pending", "submitted")):
        signals = ctx.get("signals") or []
        unsent = ctx.get("approved_not_submitted") or []
        if not signals:
            return preface + "No stored signals were returned."
        bits = [
            f"#{row.get('id')} {row.get('symbol')} {row.get('direction')} status={row.get('status')} submitted={row.get('order_submitted')}"
            for row in signals[:6]
            if isinstance(row, dict)
        ]
        extra = f" Approved but not submitted: {len(unsent)}." if unsent else ""
        return preface + "Recent signals: " + "; ".join(bits) + extra

    if any(k in q for k in ("strategy", "rule", "rr", "reward", "risk", "pip")):
        strategy = ctx.get("strategy") or {}
        limits = strategy.get("saved_limits") or {}
        return (
            preface
            + f"Rules source={strategy.get('rules_source')}, target R={strategy.get('code_target_r')}, "
            f"risk={strategy.get('code_risk_fraction')}, max stop pips={strategy.get('code_max_stop_pips')}, "
            f"saved limits={limits}."
        )

    if any(k in q for k in ("notice", "notification", "alert")):
        notices = ctx.get("notices") or []
        if not notices:
            return preface + "No recent notices were available."
        bits = [f"{n.get('title')}: {n.get('body')}" for n in notices[:5] if isinstance(n, dict)]
        return preface + "Recent notices: " + " | ".join(bits)

    if any(k in q for k in ("deal", "magic", "filled", "ticket")):
        deals = ctx.get("magic_deals") or []
        if not deals:
            return preface + f"No recent MT5 deals with magic {MAGIC}."
        bits = [
            f"#{d.get('ticket')} {d.get('symbol')} entry={d.get('entry')} profit={d.get('profit')} at {d.get('time_utc')}"
            for d in deals[:6]
        ]
        return preface + "Recent TradePilot deals: " + "; ".join(bits)

    if any(k in q for k in ("execute", "send", "order", "manual", "confirm")):
        return (
            preface
            + f"Mode is {mode}. Manual needs Send then Confirm on Signals. "
            f"Auto only sends for desk symbols {auto_syms or []}. "
            f"trade_allowed={account.get('trade_allowed')}, entries today={portfolio.get('our_entries_today')}. "
            "This chat cannot place orders."
        )

    return (
        preface
        + f"{symbol}: mode={mode}, auto reading={auto_syms or []}, "
        f"connected={account.get('connected')}, env={account.get('environment')}, "
        f"bias={scan.get('bias')}, skip={scan.get('skip_reason')}, "
        f"balance=${account.get('balance')}. Ask about setup, Auto mismatch, wins, signals, or deals."
    )

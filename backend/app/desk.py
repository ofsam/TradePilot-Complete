"""Auto scan for the markets chosen from the TradePilot watchlist."""

import json
import logging
import re
import sys
import threading
from pathlib import Path

log = logging.getLogger(__name__)
INTERVAL_SECONDS = 15
# Prefer desk_state/; fall back if an older corrupted backend/data folder blocks writes.
_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "desk_state" / "desk_mode.json"
_SYMBOL = re.compile(r"^[A-Za-z0-9 ._()#-]{2,32}$")
_lock = threading.Lock()
_attempted: set[str] = set()
_started = False
_stop = threading.Event()


def _desk_paths() -> list[Path]:
    return [
        _ROOT / "desk_state" / "desk_mode.json",
        _ROOT / "runtime" / "desk_mode.json",
        _ROOT / "data" / "desk_mode.json",
    ]


def _read() -> dict:
    for path in _desk_paths():
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        if isinstance(raw, dict):
            return raw
    return {}


def _write(payload: dict) -> None:
    text = json.dumps(payload)
    errors: list[str] = []
    for path in _desk_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            global _PATH
            _PATH = path
            return
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    raise OSError("Could not save desk mode. " + " | ".join(errors))


def _clean_symbols(values: list | tuple | None) -> list[str]:
    chosen: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        symbol = str(item).strip()
        if not symbol or _SYMBOL.fullmatch(symbol) is None:
            continue
        key = symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(symbol)
        if len(chosen) >= 12:
            break
    return chosen


def get_mode() -> str:
    mode = _read().get("mode")
    return mode if mode in {"manual", "auto"} else "manual"


def get_symbols() -> list[str]:
    return _clean_symbols(_read().get("symbols"))


def set_mode(mode: str) -> str:
    if mode not in {"manual", "auto"}:
        raise ValueError("Mode must be manual or auto.")
    with _lock:
        payload = _read()
        payload["mode"] = mode
        if "symbols" not in payload:
            payload["symbols"] = []
        else:
            payload["symbols"] = _clean_symbols(payload.get("symbols"))
        _write(payload)
    return mode


def set_symbols(symbols: list[str]) -> list[str]:
    cleaned = _clean_symbols(symbols)
    with _lock:
        payload = _read()
        payload["mode"] = payload.get("mode") if payload.get("mode") in {"manual", "auto"} else "manual"
        payload["symbols"] = cleaned
        _write(payload)
    return cleaned


def remember_symbol(symbol: str) -> list[str]:
    """Keep Auto on the market currently selected in the watchlist."""
    cleaned = _clean_symbols([symbol])
    if not cleaned:
        return get_symbols()
    with _lock:
        payload = _read()
        payload["mode"] = payload.get("mode") if payload.get("mode") in {"manual", "auto"} else "manual"
        payload["symbols"] = cleaned
        _write(payload)
    return cleaned


def state() -> dict:
    return {"mode": get_mode(), "symbols": get_symbols(), "running": _started}


def start() -> None:
    global _started
    if "pytest" in sys.modules:
        return
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="tradepilot-desk", daemon=True).start()


def stop() -> None:
    _stop.set()


def run_cycle(status, connect, scan, execute, attempted: set[str], symbols: list[str] | None = None) -> None:
    current = status()
    if not current.get("connected"):
        current = connect()
    if current.get("environment") not in {"demo", "live"}:
        return
    markets = symbols if symbols is not None else get_symbols()
    if not markets:
        return
    for symbol in markets:
        result = scan(symbol)
        proposal = result.get("proposal") or {}
        key = proposal.get("dedupe_key")
        if not key or key in attempted:
            continue
        if execute(symbol, key):
            attempted.add(key)


def _loop() -> None:
    while not _stop.is_set():
        if get_mode() == "auto":
            try:
                run_cycle(_status, _connect, _scan, _execute, _attempted)
            except Exception:
                log.warning("Desk scan failed.", exc_info=True)
        _stop.wait(INTERVAL_SECONDS)


def _status() -> dict:
    from app.mt5.adapter import MT5Unavailable, mt5_adapter

    try:
        return mt5_adapter.status()
    except MT5Unavailable as exc:
        return {"connected": False, "environment": "unknown", "message": str(exc)}


def _connect() -> dict:
    from app.mt5.adapter import mt5_adapter

    return mt5_adapter.connect()


def _scan(symbol: str) -> dict:
    from fastapi import HTTPException

    from app.routers.strategy import ScanBody, scan

    try:
        return scan(ScanBody(symbol=symbol))
    except HTTPException as exc:
        log.info("Desk scan skipped %s: %s", symbol, exc.detail)
        return {}


def _execute(symbol: str, key: str) -> bool:
    from fastapi import HTTPException

    from app.routers.strategy import ExecuteBody, execute

    try:
        execute(ExecuteBody(symbol=symbol, dedupe_key=key))
        return True
    except HTTPException as exc:
        log.info("Desk order was not sent for %s: %s", symbol, exc.detail)
        return False

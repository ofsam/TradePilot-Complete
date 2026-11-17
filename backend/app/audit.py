"""Append-only audit log for phone/cloud order confirms."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
# Prefer project runtime/ (gitignored). Avoid backend/data which can be unreadable on some Windows disks.
_LOG = Path(__file__).resolve().parents[2] / "runtime" / "execute_audit.jsonl"


def note_execute_confirm(*, email: str, symbol: str, dedupe_key: str, ok: bool, detail: str = "") -> None:
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "email": email,
        "symbol": symbol,
        "dedupe_key": dedupe_key,
        "ok": ok,
        "detail": detail[:500],
    }
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    except OSError:
        log.warning("Could not write execute audit row", exc_info=True)

"""Smoke-import restored modules. Prints only safe status lines."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.strategy.engine import TARGET_R
from app import auth, desk, notify
from app.strategy import defaults
from app.config import settings

assert TARGET_R == 5.0
assert auth.CODE_MINUTES == 10
assert desk.SYMBOLS == ("EURUSD", "USDCAD")
assert callable(notify.send_to)
assert defaults.default_parameters()["reward_multiple"] == 5.0
assert bool(settings.smtp_host and settings.smtp_user)
print("smoke_ok", "target", TARGET_R, "desk", desk.get_mode(), "mail", notify.mail_ready())

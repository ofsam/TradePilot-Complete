"""Live/demo order send switch. Off unless EXECUTION_ENABLED is truthy in the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

_TRUTHY = {"1", "true", "yes", "on"}


def is_execution_enabled() -> bool:
    return (os.getenv("EXECUTION_ENABLED") or "").strip().lower() in _TRUTHY

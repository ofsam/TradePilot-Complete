"""Login Bearer gate for remote/cloud desk access."""

from __future__ import annotations

import os
from contextvars import ContextVar

from fastapi import Header, HTTPException

from app import auth

_current_email: ContextVar[str] = ContextVar("tradepilot_email", default="")


def is_auth_required() -> bool:
    raw = (os.getenv("REQUIRE_AUTH") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def bind_host() -> str:
    return (os.getenv("BIND_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def bind_port() -> int:
    try:
        return int((os.getenv("BIND_PORT") or "8000").strip())
    except ValueError:
        return 8000


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization[7:].strip()


def current_login_email() -> str:
    return _current_email.get() or ""


def require_login(authorization: str | None = Header(default=None)) -> str:
    """Return the logged-in email, or 'local' when REQUIRE_AUTH is off."""
    if not is_auth_required():
        _current_email.set("local")
        return "local"
    token = bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Log in with the code from your email.")
    from app.strategy import store as strategy_store

    db = strategy_store.open_session()
    if db is None:
        raise HTTPException(status_code=503, detail="Supabase is not available.")
    try:
        email = auth.read_session(db, token, "login")
    finally:
        db.close()
    if email is None:
        raise HTTPException(status_code=401, detail="Log in with the code from your email.")
    _current_email.set(email)
    return email

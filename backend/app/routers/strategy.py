"""Strategy routes (recovered bytecode) with EXECUTION_ENABLED gate and login auth."""

from __future__ import annotations

from functools import wraps

from fastapi import Depends, HTTPException

from app._pyc_boot import load_into
from app.audit import note_execute_confirm
from app.deps import current_login_email, require_login
from app.execution_gate import is_execution_enabled

load_into(globals(), "app_routers___pycache___strategy.cpython-311.pyc")


def _stamp(value):
    if isinstance(value, dict):
        out = {key: _stamp(item) for key, item in value.items()}
        if "execution_enabled" in out:
            out["execution_enabled"] = is_execution_enabled()
        return out
    if isinstance(value, list):
        return [_stamp(item) for item in value]
    return value


def _wrap(endpoint, *, require_enabled: bool = False, audit_execute: bool = False):
    @wraps(endpoint)
    def wrapped(*args, **kwargs):
        if require_enabled and not is_execution_enabled():
            raise HTTPException(
                status_code=409,
                detail="Execution is disabled. Set EXECUTION_ENABLED=true in backend/.env and restart.",
            )
        email = current_login_email() or "unknown"
        body = kwargs.get("body")
        symbol = str(getattr(body, "symbol", "") or "") if body is not None else ""
        dedupe = str(getattr(body, "dedupe_key", "") or "") if body is not None else ""
        try:
            result = _stamp(endpoint(*args, **kwargs))
        except Exception as exc:
            if audit_execute:
                note_execute_confirm(email=email, symbol=symbol, dedupe_key=dedupe, ok=False, detail=str(exc))
            raise
        if audit_execute:
            detail = ""
            if isinstance(result, dict):
                detail = str(result.get("message") or result.get("ticket") or "")
            note_execute_confirm(email=email, symbol=symbol, dedupe_key=dedupe, ok=True, detail=detail)
        return result

    return wrapped


# noqa: F821 — router provided by load_into
_deps = list(getattr(router, "dependencies", None) or [])
_deps.append(Depends(require_login))
router.dependencies = _deps

for _route in router.routes:  # noqa: F821
    endpoint = getattr(_route, "endpoint", None)
    if endpoint is None:
        continue
    path = getattr(_route, "path", "") or ""
    is_execute = path == "/strategy/execute"
    wrapped = _wrap(endpoint, require_enabled=is_execute, audit_execute=is_execute)
    _route.endpoint = wrapped
    dependant = getattr(_route, "dependant", None)
    if dependant is not None:
        dependant.call = wrapped

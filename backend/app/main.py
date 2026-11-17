import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text

from app import auth, desk, models, notify  # noqa: F401
from app.config import settings
from app.db import engine, prepare_database
from app.deps import is_auth_required, require_login
from app.execution_gate import is_execution_enabled
from app.mt5.adapter import MT5Unavailable, mt5_adapter
from app.routers.strategy import router as strategy_router

log = logging.getLogger(__name__)
_SYMBOL = re.compile(r"^[A-Za-z0-9 ._()#-]{2,32}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        prepare_database()
        notify.remind_email_setup()
        _seed_strategy()
    except Exception:
        log.warning("Supabase is unavailable. Signal history will not be stored.", exc_info=True)
    desk.start()
    yield
    desk.stop()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(strategy_router, prefix=settings.api_prefix)


def _seed_strategy() -> None:
    from app.strategy import store as strategy_store

    db = strategy_store.open_session()
    if db is None:
        return
    try:
        strategy_store.ensure_default_strategy(db)
    except Exception:
        db.rollback()
        log.warning("The default strategy was not stored.", exc_info=True)
    finally:
        db.close()


def _bearer(header: str | None) -> str:
    if not header or not header.lower().startswith("bearer "):
        return ""
    return header[7:].strip()


class CodeRequest(BaseModel):
    email: str
    purpose: str = "login"


class CodeCheck(BaseModel):
    email: str
    code: str
    purpose: str = "login"


class SetupBody(BaseModel):
    parameters: dict


class DeskMode(BaseModel):
    mode: str
    symbols: list[str] | None = None


class DeskSymbols(BaseModel):
    symbols: list[str]


class ChatBody(BaseModel):
    message: str
    symbol: str | None = None
    session_id: str | None = None


def _auth_db():
    from app.strategy import store as strategy_store

    db = strategy_store.open_session()
    if db is None:
        raise HTTPException(status_code=503, detail="Supabase is not available.")
    return db


@app.post(f"{settings.api_prefix}/auth/request")
def auth_request(body: CodeRequest):
    email = auth.normalize_email(body.email)
    if not auth.valid_email(email):
        raise HTTPException(status_code=422, detail="Enter a real email address.")
    if body.purpose not in {"login", "setup"}:
        raise HTTPException(status_code=422, detail="Choose login or setup.")
    db = _auth_db()
    try:
        auth.issue_code(db, email, body.purpose, notify.send_to)
    except auth.RateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except auth.MailFailed as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        db.close()
    return {"ok": True, "email": email, "purpose": body.purpose}


@app.post(f"{settings.api_prefix}/auth/verify")
def auth_verify(body: CodeCheck):
    email = auth.normalize_email(body.email)
    db = _auth_db()
    try:
        token = auth.verify_code(db, email, body.purpose, body.code.strip())
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    finally:
        db.close()
    return {"token": token, "email": email, "purpose": body.purpose}


@app.get(f"{settings.api_prefix}/auth/me")
def auth_me(authorization: str | None = Header(default=None)):
    db = _auth_db()
    try:
        email = auth.read_session(db, _bearer(authorization), "login")
    finally:
        db.close()
    if email is None:
        raise HTTPException(status_code=401, detail="Log in with the code from your email.")
    return {"email": email}


def _setup_email(authorization: str | None) -> str:
    db = _auth_db()
    try:
        email = auth.read_session(db, _bearer(authorization), "setup")
    finally:
        db.close()
    if email is None:
        raise HTTPException(status_code=401, detail="Enter the setup code from your email.")
    return email


@app.get(f"{settings.api_prefix}/strategy/setup")
def strategy_setup(authorization: str | None = Header(default=None)):
    _setup_email(authorization)
    from app.strategy import store as strategy_store

    db = strategy_store.open_session()
    if db is None:
        raise HTTPException(status_code=503, detail="Supabase is not available.")
    try:
        return strategy_store.strategy_dict(strategy_store.ensure_default_strategy(db))
    finally:
        db.close()


@app.post(f"{settings.api_prefix}/strategy/setup")
def strategy_save(body: SetupBody, authorization: str | None = Header(default=None)):
    _setup_email(authorization)
    from app.strategy import store as strategy_store
    from app.strategy.defaults import normalize_parameters

    try:
        saved = normalize_parameters(body.parameters or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db = strategy_store.open_session()
    if db is None:
        raise HTTPException(status_code=503, detail="Supabase is not available.")
    try:
        return strategy_store.strategy_dict(strategy_store.save_strategy_parameters(db, saved))
    finally:
        db.close()


@app.post(f"{settings.api_prefix}/strategy/setup/reset")
def strategy_reset(authorization: str | None = Header(default=None)):
    _setup_email(authorization)
    from app.strategy import store as strategy_store

    db = strategy_store.open_session()
    if db is None:
        raise HTTPException(status_code=503, detail="Supabase is not available.")
    try:
        return strategy_store.strategy_dict(strategy_store.reset_default_strategy(db))
    finally:
        db.close()


def unavailable(exc):
    return HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
def health():
    enabled = is_execution_enabled()
    return {
        "status": "ok",
        "execution_enabled": enabled,
        "mt5_mode": "execute" if enabled else "read_only",
        "database": "supabase" if engine is not None else "off",
        "require_auth": is_auth_required(),
    }


@app.get(f"{settings.api_prefix}/mt5/status")
def status(_email: str = Depends(require_login)):
    try:
        current = mt5_adapter.status()
    except MT5Unavailable as exc:
        current = {
            "connected": False,
            "adapter_mode": "read_only",
            "environment": "unknown",
            "message": str(exc),
        }
    notify.watch_connection(bool(current.get("connected")), current.get("message") or "")
    return current


@app.get(f"{settings.api_prefix}/notices")
def notices(_email: str = Depends(require_login)):
    items = notify.list_notices()
    return {"items": items, "unread": sum(1 for row in items if not row.get("read"))}


@app.post(f"{settings.api_prefix}/notices/read-all")
def read_notices(_email: str = Depends(require_login)):
    notify.mark_all_read()
    return {"ok": True}


@app.post(f"{settings.api_prefix}/notices/{{notice_id}}/read")
def read_notice(notice_id: int, _email: str = Depends(require_login)):
    notify.mark_read(notice_id)
    return {"ok": True}


@app.get(f"{settings.api_prefix}/desk")
def desk_state(_email: str = Depends(require_login)):
    return desk.state()


@app.post(f"{settings.api_prefix}/desk/mode")
def desk_mode(body: DeskMode, _email: str = Depends(require_login)):
    if body.mode not in {"manual", "auto"}:
        raise HTTPException(status_code=422, detail="Mode must be manual or auto.")
    if body.mode == "auto":
        try:
            current = mt5_adapter.status()
        except MT5Unavailable:
            current = {"environment": "unknown"}
        if current.get("environment") not in {"demo", "live"}:
            raise HTTPException(status_code=409, detail="Auto stays off until a demo or live account is connected.")
    if body.symbols is not None:
        desk.set_symbols(body.symbols)
    desk.set_mode(body.mode)
    return desk.state()


@app.post(f"{settings.api_prefix}/desk/symbols")
def desk_symbols(body: DeskSymbols, _email: str = Depends(require_login)):
    desk.set_symbols(body.symbols)
    return desk.state()


@app.post(f"{settings.api_prefix}/mt5/connect")
def connect(_email: str = Depends(require_login)):
    try:
        return mt5_adapter.connect()
    except MT5Unavailable as exc:
        raise unavailable(exc)


@app.post(f"{settings.api_prefix}/mt5/disconnect")
def disconnect(_email: str = Depends(require_login)):
    return mt5_adapter.disconnect()


@app.get(f"{settings.api_prefix}/mt5/account")
def account(_email: str = Depends(require_login)):
    try:
        return mt5_adapter.status()
    except MT5Unavailable as exc:
        raise unavailable(exc)


@app.get(f"{settings.api_prefix}/mt5/symbols")
def symbols(symbols: list[str] = Query(default=["XAUUSD"]), _email: str = Depends(require_login)):
    try:
        return {"items": mt5_adapter.symbols(symbols)}
    except MT5Unavailable as exc:
        raise unavailable(exc)


@app.get(f"{settings.api_prefix}/mt5/tick")
def tick(symbol: str = "XAUUSD", _email: str = Depends(require_login)):
    chosen = symbol.strip()
    try:
        # Do not remember_symbol here: quote polls must not fight the Watchlist/Auto desk symbol.
        return mt5_adapter.tick(chosen)
    except MT5Unavailable as exc:
        raise unavailable(exc)


@app.get(f"{settings.api_prefix}/mt5/candles")
def market_candles(
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    count: int = Query(default=48, ge=10, le=300),
    _email: str = Depends(require_login),
):
    chosen = symbol.strip()
    if _SYMBOL.fullmatch(chosen) is None:
        raise HTTPException(status_code=422, detail="Enter a broker symbol such as XAUUSD.")
    if timeframe not in {"H1", "H4"}:
        raise HTTPException(status_code=422, detail="Timeframe must be H1 or H4.")
    try:
        items = mt5_adapter.rates(chosen, timeframe, count)
    except MT5Unavailable as exc:
        raise unavailable(exc)
    # Candles are read-only for charts/backtests; Auto symbol is set only via /desk/symbols.
    return {"symbol": chosen, "timeframe": timeframe, "items": items}


@app.get(f"{settings.api_prefix}/mt5/positions")
def positions(_email: str = Depends(require_login)):
    try:
        return {"items": mt5_adapter.positions()}
    except MT5Unavailable as exc:
        raise unavailable(exc)


@app.get(f"{settings.api_prefix}/database/status")
def database_status(_email: str = Depends(require_login)):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"connected": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.post(f"{settings.api_prefix}/chat")
def chat(body: ChatBody, _email: str = Depends(require_login)):
    from app import chat as desk_chat

    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="Enter a question about the desk, market, or strategy.")
    symbol = (body.symbol or "").strip() or None
    if symbol and _SYMBOL.fullmatch(symbol) is None:
        raise HTTPException(status_code=422, detail="Enter a broker symbol such as EURUSD.")
    try:
        return desk_chat.answer(message, symbol, body.session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Chat could not answer right now.") from exc


_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_file() or (_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")

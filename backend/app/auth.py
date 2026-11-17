"""Email codes for opening the desk and for opening strategy setup."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AuthSession, LoginCode

CODE_MINUTES = 10
LOGIN_DAYS = 7
SETUP_MINUTES = 15
MAX_ATTEMPTS = 5
PURPOSES = {"login", "setup"}


class RateLimited(RuntimeError):
    pass


class MailFailed(RuntimeError):
    pass


def normalize_email(value: str) -> str:
    return value.strip().lower()


def valid_email(value: str) -> bool:
    if len(value) < 6 or len(value) > 320 or value.count("@") != 1:
        return False
    local, domain = value.split("@")
    return bool(local and "." in domain and " " not in value)


def _hash(material: str) -> str:
    return hashlib.sha256(material.encode()).hexdigest()


def issue_code(db: Session, email: str, purpose: str, send) -> None:
    if purpose not in PURPOSES:
        raise ValueError("Choose login or setup.")
    now = datetime.now(timezone.utc)
    recent = (
        db.query(LoginCode)
        .filter(LoginCode.email == email, LoginCode.purpose == purpose, LoginCode.created_at >= now - timedelta(seconds=60))
        .count()
    )
    if recent:
        raise RateLimited("Wait a minute before asking for another code.")
    for older in db.query(LoginCode).filter(LoginCode.email == email, LoginCode.purpose == purpose, LoginCode.used.is_(False)).all():
        older.used = True
    code = f"{secrets.randbelow(10000):04d}"
    row = LoginCode(
        email=email,
        purpose=purpose,
        code_hash=_hash(f"{email}:{purpose}:{code}"),
        expires_at=now + timedelta(minutes=CODE_MINUTES),
        used=False,
        attempts=0,
    )
    db.add(row)
    db.commit()
    title = "Your login code" if purpose == "login" else "Your strategy setup code"
    body = f"Your TradePilot code is {code}. It expires in {CODE_MINUTES} minutes and works once."
    if not send(email, title, body):
        db.delete(row)
        db.commit()
        raise MailFailed("The code email was not sent.")


def verify_code(db: Session, email: str, purpose: str, code: str) -> str:
    if purpose not in PURPOSES or not code.isdigit() or len(code) != 4:
        raise ValueError("Enter the 4-digit code from the email.")
    now = datetime.now(timezone.utc)
    row = (
        db.query(LoginCode)
        .filter(LoginCode.email == email, LoginCode.purpose == purpose, LoginCode.used.is_(False))
        .order_by(LoginCode.id.desc())
        .first()
    )
    if row is None or row.expires_at < now:
        raise ValueError("That code is expired. Ask for a new one.")
    row.attempts += 1
    if row.attempts > MAX_ATTEMPTS:
        row.used = True
        db.commit()
        raise ValueError("Too many tries. Ask for a new code.")
    if row.code_hash != _hash(f"{email}:{purpose}:{code}"):
        db.commit()
        raise ValueError("That code does not match.")
    row.used = True
    token = secrets.token_urlsafe(32)
    minutes = SETUP_MINUTES if purpose == "setup" else LOGIN_DAYS * 24 * 60
    db.add(AuthSession(
        email=email,
        purpose=purpose,
        token_hash=_hash(token),
        expires_at=now + timedelta(minutes=minutes),
    ))
    db.commit()
    return token


def read_session(db: Session, token: str, purpose: str) -> str | None:
    if not token:
        return None
    row = db.query(AuthSession).filter_by(token_hash=_hash(token), purpose=purpose).one_or_none()
    if row is None or row.expires_at < datetime.now(timezone.utc):
        return None
    return row.email

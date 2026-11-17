"""Desk notices and Brevo mail for TradePilot."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.models import Notice

log = logging.getLogger(__name__)
ACCRA = ZoneInfo("Africa/Accra")
_connected: bool | None = None

SKIP_REASONS = {
    "daily_limit": "This symbol is already at the saved entry count for this Ghana day.",
    "position_open": "This symbol already has an open position, so a new setup waits.",
    "below_min_lot": "Sizing at the saved risk is below the broker minimum lot, so the setup was skipped.",
    "stop_100_pips": "The stop is at or beyond the saved pip limit, so this H1 setup is invalid.",
    "invalid_symbol_spec": "The terminal did not provide a usable tick value or lot step.",
}

_KIND_LABEL = {
    "signal": "NEW SETUP",
    "order": "ORDER",
    "risk": "RISK",
    "connection": "TERMINAL",
    "storage": "RECORDS",
    "setup": "TRADEPILOT",
}


def recipients() -> list[str]:
    return [part.strip() for part in settings.notify_email.split(",") if part.strip()]


def email_ready() -> bool:
    return bool(recipients() and settings.smtp_host and settings.smtp_user and settings.smtp_password)


def mail_ready() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def publish(kind: str, title: str, body: str, dedupe_key: str) -> bool:
    """Store one notice and email it the first time this key is seen."""
    if SessionLocal is None:
        return False
    db = SessionLocal()
    try:
        row = Notice(
            kind=kind[:24],
            title=title[:160],
            body=body[:600],
            dedupe_key=dedupe_key[:240],
            emailed=False,
        )
        db.add(row)
        db.commit()
    except IntegrityError:
        db.rollback()
        _retry_unsent(dedupe_key, kind, title, body)
        return False
    except Exception:
        db.rollback()
        log.warning("Notice was not stored.", exc_info=True)
        return False
    finally:
        db.close()
    if _send_email(kind, title, body):
        _mark_emailed(dedupe_key)
    return True


def list_notices(limit: int = 30) -> list[dict]:
    if SessionLocal is None:
        return []
    db = SessionLocal()
    try:
        rows = db.query(Notice).order_by(Notice.id.desc()).limit(limit).all()
        return [_dict(row) for row in rows]
    except Exception:
        log.warning("Notices could not be read.", exc_info=True)
        return []
    finally:
        db.close()


def mark_read(notice_id: int) -> None:
    _set_read(Notice.id == notice_id)


def mark_all_read() -> None:
    _set_read(True)


def note_signal(proposal) -> None:
    publish(
        "signal",
        f"New {proposal.symbol} {proposal.direction} setup",
        f"Entry {_price(proposal.entry)}, stop {_price(proposal.stop_loss)}, target {_price(proposal.take_profit)}.",
        f"signal:{proposal.dedupe_key}",
    )


def note_skip(symbol: str, reason: str) -> None:
    if reason not in SKIP_REASONS:
        return
    day = datetime.now(ACCRA).date().isoformat()
    publish("risk", f"{symbol} setup skipped", SKIP_REASONS[reason], f"skip:{symbol}:{reason}:{day}")


def note_order(
    symbol: str,
    environment: str,
    direction: str,
    volume: float,
    price: float,
    ticket: int,
    dedupe_key: str,
) -> None:
    label = "Live" if environment == "live" else "Demo"
    publish(
        "order",
        f"{label} {symbol} {direction} sent",
        f"Ticket {ticket}, {volume} lots at {_price(price)}.",
        f"order:{dedupe_key}",
    )


def note_order_failed(symbol: str, detail: str, dedupe_key: str) -> None:
    publish("order", f"{symbol} order was not sent", detail[:600], f"order-failed:{dedupe_key}")


def note_storage(title: str, body: str, dedupe_key: str) -> None:
    publish("storage", title, body, f"storage:{dedupe_key}")


def watch_connection(connected: bool, detail: str) -> None:
    global _connected
    if _connected is None:
        _connected = connected
        return
    if _connected == connected:
        return
    _connected = connected
    hour = datetime.now(ACCRA).strftime("%Y-%m-%dT%H")
    if connected:
        publish("connection", "MT5 is connected again", "The terminal is available.", f"mt5:up:{hour}")
    else:
        publish(
            "connection",
            "MT5 disconnected",
            "The terminal is not available. Auto cannot send until it returns.",
            f"mt5:down:{hour}",
        )


def remind_email_setup() -> None:
    if email_ready():
        publish(
            "setup",
            "Trade mail is on",
            "Notices go to your inbox from TradePilot. A new setup, a sent order, a blocked order, and a lost terminal each send one email.",
            "setup:mail-ready",
        )
        return
    publish(
        "setup",
        "Brevo mail is not finished",
        "The server is smtp-relay.brevo.com. In Brevo open SMTP & API, copy the SMTP login and SMTP key, verify a sender, then fill SMTP_USER, SMTP_PASSWORD, SMTP_FROM, and NOTIFY_EMAIL in backend/.env.",
        "setup:brevo-missing",
    )


def send_to(address: str, title: str, body: str) -> bool:
    """One mailbox. Login codes go only to the address that was typed."""
    if not mail_ready():
        return False
    return _deliver(address, "setup", title, body)


def _html_notice(kind: str, title: str, body: str) -> str:
    label = _KIND_LABEL.get(kind, "NOTICE")
    safe_title = escape(title)
    safe_body = escape(body).replace("\n", "<br>")
    return (
        "<!DOCTYPE html>\n<html>\n<body style=\"margin:0;padding:0;background:#0b1220;\">\n"
        f'  <div style="display:none;max-height:0;overflow:hidden;">{safe_title}</div>\n'
        '  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b1220;padding:28px 12px;">\n'
        "    <tr><td align=\"center\">\n"
        '      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:560px;max-width:560px;background:#0e1727;border:1px solid #1d2a3d;border-radius:16px;">\n'
        '        <tr><td style="padding:26px 32px 22px;">\n'
        '          <table role="presentation" cellpadding="0" cellspacing="0">\n'
        "            <tr>\n"
        '              <td width="44" height="44" align="center" valign="middle" bgcolor="#d7a94b" style="width:44px;height:44px;background:#d7a94b;border-radius:12px;">\n'
        '                <table role="presentation" cellpadding="0" cellspacing="0">\n'
        "                  <tr>\n"
        '                    <td valign="bottom" style="padding:0 2px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr><td width="4" height="12" bgcolor="#111827" style="width:4px;height:12px;background:#111827;font-size:0;line-height:0;">&nbsp;</td></tr></table></td>\n'
        '                    <td valign="bottom" style="padding:0 2px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr><td width="4" height="20" bgcolor="#111827" style="width:4px;height:20px;background:#111827;font-size:0;line-height:0;">&nbsp;</td></tr></table></td>\n'
        '                    <td valign="bottom" style="padding:0 2px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr><td width="4" height="15" bgcolor="#111827" style="width:4px;height:15px;background:#111827;font-size:0;line-height:0;">&nbsp;</td></tr></table></td>\n'
        "                  </tr>\n"
        "                </table>\n"
        "              </td>\n"
        '              <td style="padding-left:14px;">\n'
        "                <div style=\"color:#e7edf6;font:700 18px Georgia,'Times New Roman',serif;letter-spacing:0.2px;\">TradePilot</div>\n"
        '                <div style="margin-top:3px;color:#7e91aa;font:700 10px Georgia,serif;letter-spacing:1.6px;">MT5 CONTROL CENTER</div>\n'
        "              </td>\n"
        "            </tr>\n"
        "          </table>\n"
        "        </td></tr>\n"
        '        <tr><td height="3" bgcolor="#d7a94b" style="height:3px;background:#d7a94b;font-size:0;line-height:0;">&nbsp;</td></tr>\n'
        '        <tr><td style="padding:28px 32px 8px;">\n'
        f'          <div style="color:#d7a94b;font:700 11px Georgia,serif;letter-spacing:1.8px;">{escape(label)}</div>\n'
        f"          <div style=\"margin:12px 0 0;color:#e7edf6;font:700 24px Georgia,'Times New Roman',serif;line-height:1.3;\">{safe_title}</div>\n"
        "        </td></tr>\n"
        f'        <tr><td style="padding:14px 32px 30px;color:#c5d0e0;font:16px Georgia,\'Times New Roman\',serif;line-height:1.65;">{safe_body}</td></tr>\n'
        '        <tr><td style="padding:16px 32px 24px;border-top:1px solid #1d2a3d;color:#7e91aa;font:12px Georgia,serif;line-height:1.5;">\n'
        "          Sent from your TradePilot desk on this computer. Contest accounts stay blocked.\n"
        "        </td></tr>\n"
        "      </table>\n"
        "    </td></tr>\n"
        "  </table>\n"
        "</body>\n</html>"
    )


def _send_email(kind: str, title: str, body: str) -> bool:
    if not email_ready():
        return False
    return _deliver(", ".join(recipients()), kind, title, body)


def _deliver(address: str, kind: str, title: str, body: str) -> bool:
    message = EmailMessage()
    message["Subject"] = f"TradePilot: {title}"[:180]
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = address
    message.set_content(f"{title}\n\n{body}\n")
    message.add_alternative(_html_notice(kind, title, body), subtype="html")
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(message)
        return True
    except Exception:
        log.warning("Email was not sent.", exc_info=True)
        return False


def _retry_unsent(dedupe_key: str, kind: str, title: str, body: str) -> None:
    """A failed send stays unsent. The next time this key is published, try once more."""
    if not email_ready() or SessionLocal is None:
        return
    db = SessionLocal()
    try:
        row = db.query(Notice).filter_by(dedupe_key=dedupe_key[:240]).one_or_none()
        if row is None or row.emailed:
            return
    except Exception:
        return
    finally:
        db.close()
    if _send_email(kind, title, body):
        _mark_emailed(dedupe_key)
    else:
        _rewrite(dedupe_key, title, body)


def _rewrite(dedupe_key: str, title: str, body: str) -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        row = db.query(Notice).filter_by(dedupe_key=dedupe_key[:240]).one_or_none()
        if row is None:
            return
        row.title = title[:160]
        row.body = body[:600]
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _mark_emailed(dedupe_key: str) -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        row = db.query(Notice).filter_by(dedupe_key=dedupe_key[:240]).one_or_none()
        if row is None:
            return
        row.emailed = True
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _set_read(criterion) -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        query = db.query(Notice)
        if criterion is not True:
            query = query.filter(criterion)
        query.update({"read": True})
        db.commit()
    except Exception:
        db.rollback()
        log.warning("Notice was not marked read.", exc_info=True)
    finally:
        db.close()


def _dict(row: Notice) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "title": row.title,
        "body": row.body,
        "read": row.read,
        "emailed": row.emailed,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _price(value: float) -> str:
    text = f"{float(value):.5f}".rstrip("0").rstrip(".")
    return text or "0"

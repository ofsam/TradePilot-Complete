import dis
import app.notify as n

for name in [
    "publish",
    "watch_connection",
    "_retry_unsent",
    "_set_read",
    "_dict",
    "note_skip",
    "send_to",
    "_deliver",
    "list_notices",
    "note_order",
    "note_order_failed",
]:
    print("\n########", name)
    dis.dis(getattr(n, name))

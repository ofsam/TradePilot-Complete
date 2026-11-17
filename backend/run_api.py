"""Start the API using BIND_HOST / BIND_PORT from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

HOST = (os.getenv("BIND_HOST") or "127.0.0.1").strip() or "127.0.0.1"
try:
    PORT = int((os.getenv("BIND_PORT") or "8000").strip())
except ValueError:
    PORT = 8000


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)

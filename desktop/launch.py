"""Open the TradePilot window. Closing it leaves the API and Auto running."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
URL = "http://127.0.0.1:8000/"
LOG = ROOT / "runtime" / "tradepilot-launch.log"
WAIT_SECONDS = 120


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _python() -> Path:
    candidates = [
        ROOT / "runtime" / "python" / "python.exe",
        ROOT / "runtime" / "python" / "pythonw.exe",
        BACKEND / ".venv" / "Scripts" / "python.exe",
        BACKEND / ".venv" / "Scripts" / "pythonw.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise SystemExit("Python runtime missing. Run Setup-TradePilot.bat first.")


def port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            return True
    except OSError:
        return False


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(URL + "health", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def wait_until_ready() -> bool:
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        if health_ok():
            return True
        time.sleep(0.5)
    return False


def ensure_api() -> None:
    if health_ok():
        log("API already healthy")
        return
    python = _python()
    if python.name.lower() == "pythonw.exe":
        alt = python.with_name("python.exe")
        if alt.is_file():
            python = alt
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    host = (env.get("BIND_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int((env.get("BIND_PORT") or "8000").strip())
    except ValueError:
        port = 8000
    log(f"Starting API with {python} on {host}:{port}")
    subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)],
        cwd=str(BACKEND),
        env=env,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    if not wait_until_ready():
        raise SystemExit(
            "TradePilot API did not start within 2 minutes. "
            f"Check {LOG} and backend\\.env (DATABASE_URL)."
        )
    log("API healthy")


def open_window() -> None:
    try:
        import webview

        log("Opening pywebview window")
        webview.create_window("TradePilot", URL, width=1280, height=800, min_size=(960, 640))
        webview.start()
        return
    except Exception as exc:
        log(f"webview failed: {exc}")

    edge_paths = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for edge in edge_paths:
        if edge.is_file():
            log(f"Opening Edge app window: {edge}")
            subprocess.Popen([str(edge), f"--app={URL}", "--window-size=1280,800"])
            return

    log("Opening default browser")
    webbrowser.open(URL)


def main() -> None:
    try:
        log("Launch begin")
        if not (BACKEND / ".env").is_file():
            raise SystemExit("backend\\.env is missing. Run Setup-TradePilot.bat and add DATABASE_URL.")
        if not (ROOT / "frontend" / "dist" / "index.html").is_file():
            raise SystemExit("frontend\\dist is missing. Use the Full Package zip.")
        ensure_api()
        if not wait_until_ready():
            raise SystemExit("TradePilot is not answering on http://127.0.0.1:8000/")
        open_window()
        log("Launch UI started")
    except Exception:
        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()

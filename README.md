# MT5 Trading Control Center — Milestone 2

React + TypeScript dashboard, FastAPI backend, PostgreSQL records, a read-only MT5 adapter, and a provisional XAUUSD H4/H1 strategy engine with backtests.

The original strategy file was not in this project. `backend/app/strategy/engine.py` holds an explicit template: H4 bias from the last three closed candles, an H1 breakout in that direction, a 1:2 target, 2% risk floored to the broker lot step, and a maximum of two kept signals per UTC day. Replace that template with your own rules before you rely on the signals. Approving a signal stores the decision. This build cannot send, modify, or close an order.

## Safety
- No order submission, order modification, or position-closing code/endpoints exist.
- MT5 integration only reads terminal/account/tick/symbol/position information.
- Run the backend on Windows where MT5 desktop is installed. The Python MT5 package does not run as a browser integration.
- Log in to MT5 desktop manually with a demo account first. This starter does not accept or store MT5 passwords.
- This is a local development prototype, not production-secured software.

## Requirements
Windows 10/11, MT5 desktop, Python 3.11, Node.js 20+, and PostgreSQL 15+ (Docker optional).

## Start PostgreSQL
From the project root: `docker compose up -d postgres`

## Start backend (PowerShell)
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Set `DATABASE_URL` in `backend/.env`. Optional `MT5_TERMINAL_PATH` points to terminal64.exe. Leave credentials out of `.env`.

API docs: http://127.0.0.1:8000/docs

## Start frontend
```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```
Open http://127.0.0.1:5173.

## Endpoints
- `GET /health`
- `GET /api/v1/mt5/status`
- `POST /api/v1/mt5/connect` (initializes the local terminal API connection only)
- `POST /api/v1/mt5/disconnect`
- `GET /api/v1/mt5/account`
- `GET /api/v1/mt5/symbols?symbols=XAUUSD`
- `GET /api/v1/mt5/tick?symbol=XAUUSD`
- `GET /api/v1/mt5/positions`
- `GET /api/v1/strategy/rules`
- `POST /api/v1/strategy/scan`
- `POST /api/v1/strategy/backtest` with `{"source":"sample"}` or `{"source":"mt5","symbol":"XAUUSD"}`
- `GET /api/v1/signals`
- `POST /api/v1/signals/{id}/approve`
- `POST /api/v1/signals/{id}/reject`
- `GET /api/v1/strategy/backtests`

Run strategy tests from `backend` with `pytest`. The sample backtest is a price fixture, not evidence of profitability.

The backend has no order execution endpoints. Account metadata is reported as demo, live, contest, or unknown. Live account data remains read-only. Check the broker's actual gold symbol name (it may not be exactly XAUUSD). Reading history selects that symbol in Market Watch. PostgreSQL stores signals, approvals, and backtest runs when it is running. Alembic migrations and authentication should be added before any phone or network access. Keep the servers on 127.0.0.1 until then. The iPhone cannot reach this bind address from another device.

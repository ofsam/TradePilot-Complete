# TradePilot cloud VPS (Windows + MT5)

The phone app never hosts MetaTrader. Deploy this backend on a **Windows VPS** with your Exness MT5 terminal, then point the Expo app at the HTTPS API.

## 1. VPS prep

1. Windows Server / Windows 10+ VPS with enough RAM for MT5.
2. Install Exness MetaTrader 5 and log into the trading account you want the bot to use.
3. Clone this repo (or copy the Full Package) onto the VPS.
4. Run `Setup-TradePilot.bat` (or create `backend/.venv` and `pip install -r backend/requirements.txt`).

## 2. Backend `.env`

Copy `backend/.env.example` to `backend/.env` and set at least:

```env
DATABASE_URL=postgresql://...   # Supabase pooler URI
CORS_ORIGINS=https://your-app-origin,http://localhost:8081
BIND_HOST=0.0.0.0
BIND_PORT=8000
REQUIRE_AUTH=true
SMTP_HOST=...
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
EXECUTION_ENABLED=false
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

Turn `EXECUTION_ENABLED=true` only after OTP login and HTTPS work.

## 3. Start the API

From `backend/`:

```bat
python run_api.py
```

Or:

```bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check (local on the VPS): `http://127.0.0.1:8000/health`

## 4. HTTPS reverse proxy

Do **not** expose raw HTTP port 8000 to the public internet for order send.

Options:

- **Caddy / nginx** on the VPS (or a Linux reverse-proxy box) with a TLS cert terminating to `127.0.0.1:8000`
- A managed tunnel (Cloudflare Tunnel, etc.) pointing at the API

Example Caddy site block:

```
api.yourdomain.com {
  reverse_proxy 127.0.0.1:8000
}
```

Open only 443 (and RDP/SSH for admin) on the firewall.

## 5. Point the mobile app

In `mobile/.env` (or EAS secrets):

```env
EXPO_PUBLIC_API_BASE_URL=https://api.yourdomain.com
```

Then:

```bat
cd mobile
npm start
```

Sign in with the email OTP. Use **Auto** to flip the VPS desk mode. Use **Signals → Scan & confirm** to send an authenticated order when execution is enabled.

## 6. Safety checklist

- [ ] `REQUIRE_AUTH=true`
- [ ] HTTPS only from phones
- [ ] SMTP OTP working
- [ ] MT5 connected on the VPS (`Connect MT5 on VPS` in the app)
- [ ] `EXECUTION_ENABLED=false` until you are ready for real/demo sends
- [ ] Audit file `runtime/execute_audit.jsonl` reviewed after test confirms

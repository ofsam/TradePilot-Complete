from app.mt5.adapter import mt5_adapter

try:
    print("connected", mt5_adapter.connect().get("connected"))
except Exception as exc:
    print("connect", exc)

for name in ["ETHUSD", "ETHUSDm", "ETHUSD.", "#ETHUSD", "BTCUSD", "XAUUSD", "EURUSD"]:
    try:
        print(name, mt5_adapter.symbols([name])[0])
    except Exception as exc:
        print(name, "err", exc)

# Try select + tick for ETHUSD with clearer error
try:
    print("tick ETHUSD", mt5_adapter.tick("ETHUSD"))
except Exception as exc:
    print("tick ETHUSD", type(exc).__name__, exc)

from pathlib import Path

text = Path("dist/assets/index-CGswb-wH.js").read_text(encoding="utf-8")
needle = '["XAUUSD","USDJPY"'
i = text.find(needle)
print("watchlist idx", i)
print(text[i : i + 600])
print("--- desk/mode ---")
j = text.find("desk/mode")
print(text[j - 100 : j + 220])
print("--- counts ---")
for key in ["tradepilot.symbol", "desk/mode", "Confirm auto", "EURUSD and USDCAD", "n5("]:
    print(key, text.count(key))
# Find function that sets mode
k = text.find('JSON.stringify({mode:')
print("--- stringify mode ---")
print(text[k - 60 : k + 80])

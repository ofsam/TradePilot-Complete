from pathlib import Path

js_path = Path("dist/assets/index-CGswb-wH.js")
text = js_path.read_text(encoding="utf-8")
old = (
    's.trades.some(ee=>{var $;return((($=ee.shot)==null?void 0:$.candles.length)??0)>=2})&&h.jsxs("section",{className:"panel",children:[h.jsx("div",{className:"panel-head",children:h.jsxs("div",{children:[h.jsx("b",{children:"Setup shots"}),h.jsx("small",{children:"Each picture is the H1 window around that signal. The lines are the levels that rule used."})]})}),h.jsx("div",{className:"shot-grid",children:s.trades.map(ee=>h.jsx(ty,{trade:ee},`${ee.signal_time}-${ee.entry_time}`))})]})'
)
new = (
    's.trades.some(ee=>{var $;return((($=ee.shot)==null?void 0:$.candles.length)??0)>=2})&&h.jsx("section",{className:"panel shot-panel",children:h.jsxs("details",{className:"shot-accordion",children:[h.jsx("summary",{className:"panel-head shot-summary",children:h.jsxs("div",{children:[h.jsx("b",{children:"Setup shots"}),h.jsx("small",{children:"Each picture is the H1 window around that signal. The lines are the levels that rule used."})]})}),h.jsx("div",{className:"shot-grid",children:s.trades.map(ee=>h.jsx(ty,{trade:ee},`${ee.signal_time}-${ee.entry_time}`))})]})})'
)
if old not in text:
    raise SystemExit(f"old chunk not found; nearby={text.find('Setup shots')}")
js_path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("js patched")

css_path = Path("dist/assets/index-C9nq9nB1.css")
css = css_path.read_text(encoding="utf-8")
addon = (
    ".shot-panel{padding:0}"
    ".shot-accordion{margin:0}"
    ".shot-accordion>summary{list-style:none;cursor:pointer;user-select:none}"
    ".shot-accordion>summary::-webkit-details-marker{display:none}"
    ".shot-summary{display:flex;align-items:center;justify-content:space-between;gap:12px}"
    '.shot-summary::after{content:">";color:#7e91aa;font:700 16px Space Grotesk,sans-serif;transform:rotate(0deg);transition:transform .15s ease}'
    ".shot-accordion[open]>.shot-summary::after{transform:rotate(90deg)}"
)
if ".shot-accordion{" not in css:
    # insert before .shot-grid if present, else append
    marker = ".shot-grid{display:grid"
    if marker in css:
        css = css.replace(marker, addon + marker, 1)
    else:
        css += addon
    css_path.write_text(css, encoding="utf-8")
    print("css patched")
else:
    print("css already has accordion")

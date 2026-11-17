/* Keep Auto matched to the visible Watchlist dropdown only (ignore stale localStorage). */
(function () {
  const API = "http://127.0.0.1:8000/api/v1/desk/symbols";
  let last = "";

  function selected() {
    const sel = document.querySelector('select[aria-label="Watchlist"]');
    if (!sel || !sel.value) return "";
    return String(sel.value).trim().toUpperCase();
  }

  async function sync(force) {
    const symbol = selected();
    if (!symbol) return;
    if (!force && symbol === last) return;
    last = symbol;
    localStorage.setItem("tradepilot.symbol", symbol);
    try {
      await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols: [symbol] }),
      });
    } catch (_) {}
  }

  function bind() {
    const sel = document.querySelector('select[aria-label="Watchlist"]');
    if (sel && !sel.dataset.tpSyncBound) {
      sel.dataset.tpSyncBound = "1";
      sel.addEventListener("change", () => {
        void sync(true);
      });
    }
    void sync(false);
  }

  setTimeout(bind, 1500);
  setInterval(bind, 3000);
})();

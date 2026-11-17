(() => {
  const API = "http://127.0.0.1:8000/api/v1/chat";
  const SESSION_KEY = "tradepilot.chat.session";
  const ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/></svg>`;

  function sessionId() {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) || `tp-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  function selectedSymbol() {
    const select = document.querySelector('select[aria-label="Watchlist"]');
    if (select && select.value) return select.value;
    return localStorage.getItem("tradepilot.symbol") || "XAUUSD";
  }

  function ensureUi() {
    if (document.getElementById("tp-chat-drawer")) return;

    const backdrop = document.createElement("div");
    backdrop.id = "tp-chat-backdrop";
    backdrop.className = "tp-chat-backdrop";
    backdrop.addEventListener("click", close);

    const drawer = document.createElement("aside");
    drawer.id = "tp-chat-drawer";
    drawer.className = "tp-chat-drawer";
    drawer.innerHTML = `
      <div class="tp-chat-head">
        <div>
          <b>AI Chat</b>
          <small>Desk tools + memory. Read-only (no order send).</small>
        </div>
        <button type="button" id="tp-chat-close">Close</button>
      </div>
      <div class="tp-chat-log" id="tp-chat-log"></div>
      <form class="tp-chat-form" id="tp-chat-form">
        <textarea id="tp-chat-input" maxlength="1200" placeholder="Ask why Auto skipped a trade, current bias, wins/losses…"></textarea>
        <button type="submit" id="tp-chat-send">Ask</button>
      </form>`;

    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);
    document.getElementById("tp-chat-close").addEventListener("click", close);
    document.getElementById("tp-chat-form").addEventListener("submit", onSubmit);

    addBubble(
      "bot",
      "I use live desk context and (if configured) OpenAI tools. Ask about Auto vs Watchlist, setups/skips, account, wins/losses, signals, notices, or strategy. I cannot place orders.",
      "desk"
    );
  }

  function injectNav() {
    const nav = document.querySelector("aside.sidebar nav");
    if (!nav || document.getElementById("tp-chat-nav")) return;
    const btn = document.createElement("button");
    btn.id = "tp-chat-nav";
    btn.type = "button";
    btn.className = "tp-chat-nav";
    btn.innerHTML = `${ICON}<span>AI Chat</span>`;
    btn.addEventListener("click", open);
    nav.appendChild(btn);
  }

  function open() {
    ensureUi();
    injectNav();
    document.getElementById("tp-chat-drawer").classList.add("open");
    document.getElementById("tp-chat-backdrop").classList.add("open");
    const nav = document.getElementById("tp-chat-nav");
    if (nav) nav.classList.add("active");
    document.getElementById("tp-chat-input").focus();
  }

  function close() {
    const drawer = document.getElementById("tp-chat-drawer");
    const backdrop = document.getElementById("tp-chat-backdrop");
    if (drawer) drawer.classList.remove("open");
    if (backdrop) backdrop.classList.remove("open");
    const nav = document.getElementById("tp-chat-nav");
    if (nav) nav.classList.remove("active");
  }

  function addBubble(role, text, meta) {
    const log = document.getElementById("tp-chat-log");
    if (!log) return;
    const div = document.createElement("div");
    div.className = `tp-chat-bubble ${role}`;
    div.textContent = text;
    if (meta) {
      const m = document.createElement("span");
      m.className = "meta";
      m.textContent = meta;
      div.appendChild(m);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  async function onSubmit(event) {
    event.preventDefault();
    const input = document.getElementById("tp-chat-input");
    const send = document.getElementById("tp-chat-send");
    const message = (input.value || "").trim();
    if (!message) return;
    addBubble("user", message);
    input.value = "";
    send.disabled = true;
    try {
      const response = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          symbol: selectedSymbol(),
          session_id: sessionId(),
        }),
      });
      const text = await response.text();
      let body = null;
      try {
        body = text ? JSON.parse(text) : null;
      } catch {
        body = { reply: text };
      }
      if (!response.ok) {
        const detail = body && body.detail ? String(body.detail) : text || `Request failed (${response.status})`;
        addBubble("bot", detail, "error");
      } else {
        if (body.session_id) localStorage.setItem(SESSION_KEY, body.session_id);
        const meta = [
          body.source || "desk",
          body.openai_configured ? "openai-ready" : "no-openai-key",
          body.model || null,
        ]
          .filter(Boolean)
          .join(" · ");
        addBubble("bot", body.reply || "No reply.", meta);
      }
    } catch (err) {
      addBubble("bot", err instanceof Error ? err.message : "Chat is unavailable.", "error");
    } finally {
      send.disabled = false;
      input.focus();
    }
  }

  function boot() {
    injectNav();
    ensureUi();
    const obs = new MutationObserver(() => injectNav());
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

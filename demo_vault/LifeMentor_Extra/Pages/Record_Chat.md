---
lm_page: record_chat
---

# LifeMentor Chat 💬

```dataviewjs
const API_BASE = "http://127.0.0.1:8010";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);

// Message history
let messages = [];

const card = dv.container.createEl("div", { cls: "card" });
card.style.padding = "0";
card.style.overflow = "hidden";

// Top bar
const topbar = card.createEl("div");
topbar.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #e5e7eb;";
const brand = topbar.createEl("div");
brand.style.cssText = "font-weight:700;display:flex;align-items:center;gap:8px;";
brand.innerHTML = '<span style="width:10px;height:10px;border-radius:50%;background:#111827;"></span>LifeMentor Chat';
const status = topbar.createEl("div", { cls: "muted", text: "Checking connection..." });

// Message container
const msgContainer = card.createEl("div");
msgContainer.style.cssText = "height:400px;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;background:#f7f7f8;";

// Initial message
function addMessage(text, role) {
  const msg = msgContainer.createEl("div");
  msg.style.cssText = `display:flex;gap:10px;align-items:flex-start;${role === "user" ? "flex-direction:row-reverse;" : ""}`;

  const avatar = msg.createEl("div");
  avatar.style.cssText = `width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;${role === "user" ? "background:#d1d5db;color:#111827;" : "background:#111827;color:#fff;"}`;
  avatar.innerText = role === "user" ? "You" : "LM";

  const bubble = msg.createEl("div");
  bubble.style.cssText = `max-width:70%;padding:12px 14px;border-radius:16px;font-size:14px;line-height:1.5;${role === "user" ? "background:#111827;color:#fff;border-radius:16px 16px 4px 16px;" : "background:#fff;border:1px solid #e5e7eb;border-radius:16px 16px 16px 4px;"}`;
  bubble.innerText = text;

  msgContainer.scrollTop = msgContainer.scrollHeight;
}

addMessage("Where would you like to start? Share one thing that's on your mind right now.", "ai");

// Input area
const composer = card.createEl("div");
composer.style.cssText = "padding:12px 16px;border-top:1px solid #e5e7eb;background:#fff;";

const inputRow = composer.createEl("div");
inputRow.style.cssText = "display:flex;gap:8px;align-items:flex-end;border:1px solid #e5e7eb;border-radius:14px;padding:8px 10px;background:#f9fafb;";

const textarea = inputRow.createEl("textarea");
textarea.style.cssText = "flex:1;border:none;outline:none;background:transparent;resize:none;min-height:36px;max-height:100px;font-size:14px;line-height:1.5;font-family:inherit;";
textarea.placeholder = "Type a message...";
textarea.rows = 1;

const sendBtn = inputRow.createEl("button");
sendBtn.style.cssText = "width:34px;height:34px;border-radius:10px;border:none;background:#111827;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;";
sendBtn.innerText = "➤";

async function sendMessage() {
  const text = textarea.value.trim();
  if (!text) return;

  addMessage(text, "user");
  textarea.value = "";
  sendBtn.disabled = true;
  status.innerText = "Thinking...";

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, date: today }),
    });
    const data = await res.json();
    if (data.error) {
      addMessage("Error: " + data.error, "ai");
    } else {
      const reply = data.parsed?.reply || data.parsed?.action || "Done";
      addMessage(reply, "ai");
    }
    status.innerText = "Connected";
  } catch (e) {
    addMessage("Connection error: " + e.message, "ai");
    status.innerText = "Disconnected";
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", sendMessage);
textarea.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Check connection
(async () => {
  try {
    const res = await fetch(`${API_BASE}/`, { method: "GET" });
    status.innerText = res.ok || res.status === 401 ? "Connected" : "Service error";
  } catch (e) {
    status.innerText = "Server not running";
  }
})();
```

<div class="lm-nav">
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Today" href="LifeMentor_Extra/Pages/Today">☀️ Today</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
<a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 Record</a>
</div>

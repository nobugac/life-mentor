---
lm_page: today_action
did: ""
skip_reason: ""
---

# Today ☀️

<div class="subline">Action page: shows today's practice (one step only).</div>

```dataviewjs
const API_BASE = "http://127.0.0.1:8010";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const ACTION_STATE_KEY = "lm_action_state_" + today;

// Load micro-action data from localStorage
let microAction = null;
let ideas = [];
let actionState = null; // "adopted" | "skipped" | null
try {
  const stored = localStorage.getItem("lm_micro_action");
  if (stored) microAction = JSON.parse(stored);
  const storedIdeas = localStorage.getItem("lm_ideas");
  if (storedIdeas) ideas = JSON.parse(storedIdeas);
  const storedState = localStorage.getItem(ACTION_STATE_KEY);
  if (storedState) actionState = storedState;
} catch (e) {}

const card = dv.container.createEl("div", { cls: "card" });
const head = card.createEl("div", { cls: "head" });
head.createEl("div", { cls: "label", text: "🧩 Today's Practice (one step)" });
head.createEl("span", { cls: "badge amber", text: actionState ? "Done" : "1 item" });

if (!microAction) {
  card.createEl("div", { cls: "muted", text: "No practice generated yet. Go to Today → Continue to generate." });
} else {

const actionCard = card.createEl("div", { cls: "card" });
actionCard.style.background = actionState === "adopted" ? "rgba(34,197,94,.08)" : actionState === "skipped" ? "rgba(156,163,175,.08)" : "rgba(124,58,237,.05)";
actionCard.style.borderColor = actionState === "adopted" ? "rgba(34,197,94,.25)" : actionState === "skipped" ? "rgba(156,163,175,.25)" : "rgba(124,58,237,.18)";

const actionText = actionCard.createEl("div", { cls: "action-text" });
actionText.createEl("span", { cls: "action-label", text: "Action: " });
actionText.createEl("span", { cls: "action-value", text: microAction.text });

const alignedWith = actionCard.createEl("div", { cls: "muted" });
alignedWith.style.marginTop = "8px";
alignedWith.innerText = "Aligned with: " + (microAction.aligned_with || "");

// If already handled, show status
if (actionState) {
  const statusDiv = actionCard.createEl("div");
  statusDiv.style.cssText = "margin-top:12px;padding:8px 12px;border-radius:8px;font-size:14px;";
  if (actionState === "adopted") {
    statusDiv.style.background = "rgba(34,197,94,.1)";
    statusDiv.style.color = "#16a34a";
    statusDiv.innerText = "✅ Marked as done";
  } else {
    statusDiv.style.background = "rgba(156,163,175,.1)";
    statusDiv.style.color = "#6b7280";
    statusDiv.innerText = "⏭ Skipped";
  }
}

const btnrow = actionCard.createEl("div", { cls: "btnrow" });

if (!actionState) {
  const adoptBtn = btnrow.createEl("button", { cls: "btn ghost", text: "✅ I'll do this today" });
  adoptBtn.addEventListener("click", async () => {
    adoptBtn.disabled = true;
    adoptBtn.innerText = "Saving...";
    try {
      await fetch(`${API_BASE}/suggestion/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: today,
          action: "adopt",
          suggestion_id: microAction.id,
          text: microAction.text,
          type: "micro",
        }),
      });
      localStorage.setItem(ACTION_STATE_KEY, "adopted");
      adoptBtn.innerText = "Saved ✓";
      actionCard.style.background = "rgba(34,197,94,.08)";
      actionCard.style.borderColor = "rgba(34,197,94,.25)";
    } catch (e) {
      adoptBtn.innerText = "Error: " + e.message;
    }
  });

  const skipBtn = btnrow.createEl("button", { cls: "btn ghost", text: "⏭ Skip today" });
  skipBtn.addEventListener("click", async () => {
    skipBtn.disabled = true;
    skipBtn.innerText = "Saving...";
    try {
      await fetch(`${API_BASE}/suggestion/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: today,
          action: "ignore",
          suggestion_id: microAction.id,
          text: microAction.text,
          type: "micro",
        }),
      });
      localStorage.setItem(ACTION_STATE_KEY, "skipped");
      skipBtn.innerText = "Skipped";
      actionCard.style.background = "rgba(156,163,175,.08)";
      actionCard.style.borderColor = "rgba(156,163,175,.25)";
    } catch (e) {
      skipBtn.innerText = "Error: " + e.message;
    }
  });
}

const nightLink = btnrow.createEl("a", {
  cls: "btn ghost internal-link",
  text: "Evening Review →",
  href: "LifeMentor_Extra/Pages/Night",
});
nightLink.setAttribute("data-href", "LifeMentor_Extra/Pages/Night");

card.createEl("div", { cls: "hr" });
card.createEl("div", { cls: "muted", text: "Optional Inspirations" });

const chips = card.createEl("div", { cls: "chips" });
for (const idea of ideas) {
  chips.createEl("div", { cls: "chip", text: idea });
}
} // end if (microAction)
```

<div class="lm-nav">
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
<a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Today" href="LifeMentor_Extra/Pages/Today">☀️ Today</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 Record</a>
</div>

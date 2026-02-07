---
lm_page: today_input
today_one_liner: ""
---

# Today ☀️

<div class="subline">Type one sentence (optional) → click Continue → see today's practice action.</div>

```dataviewjs
const API_BASE = "http://127.0.0.1:8010";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);

const card = dv.container.createEl("div", { cls: "card" });
const head = card.createEl("div", { cls: "head" });
const label = head.createEl("div", { cls: "label", text: "📝 One sentence" });
head.createEl("span", { cls: "badge", text: "optional" });

const textarea = card.createEl("textarea", { cls: "textarea" });
textarea.placeholder = "One sentence: energy / stress / main event (the shorter the better)\nE.g. A bit tired this morning, had a late night.";

const btnrow = card.createEl("div", { cls: "btnrow" });

const submitBtn = btnrow.createEl("button", { cls: "btn ghost", text: "Continue → Generate today's practice" });
submitBtn.addEventListener("click", async () => {
  const text = textarea.value.trim();
  submitBtn.disabled = true;
  submitBtn.innerText = "Generating...";

  try {
    const res = await fetch(`${API_BASE}/morning`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: today, text: text }),
    });
    const data = await res.json();

    if (data.micro_action) {
      localStorage.setItem("lm_micro_action", JSON.stringify(data.micro_action));
    }
    if (data.ideas) {
      localStorage.setItem("lm_ideas", JSON.stringify(data.ideas));
    }

    if (app && app.workspace) {
      app.workspace.openLinkText("LifeMentor_Extra/Pages/Today_Action", "", false);
    }
  } catch (e) {
    submitBtn.innerText = "Error: " + e.message;
    submitBtn.disabled = false;
  }
});

const homeLink = btnrow.createEl("a", {
  cls: "btn ghost internal-link",
  text: "Skip, back to Home",
  href: "LifeMentor_Extra/Home",
});
homeLink.setAttribute("data-href", "LifeMentor_Extra/Home");

card.createEl("div", { cls: "muted", text: "This is only used to generate today's practice. It won't appear on the next screen." }).style.marginTop = "10px";
```

<div class="lm-nav">
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
<a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Today" href="LifeMentor_Extra/Pages/Today">☀️ Today</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 Record</a>
</div>

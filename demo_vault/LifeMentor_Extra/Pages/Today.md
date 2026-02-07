---
lm_page: today
---

# Today ☀️

```dataviewjs
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const CACHE_KEY = "lm_micro_action_" + today;

// Check if today's micro-action was already generated
let hasMicroAction = false;
try {
  const stored = localStorage.getItem("lm_micro_action");
  if (stored) {
    const data = JSON.parse(stored);
    // Check if data is from today
    if (data && data.text) {
      hasMicroAction = true;
    }
  }
} catch (e) {}

// Navigate based on state
if (hasMicroAction) {
  // Action exists, go to Action page
  if (app && app.workspace) {
    app.workspace.openLinkText("LifeMentor_Extra/Pages/Today_Action", "", false);
  }
} else {
  // No action yet, go to Input page
  if (app && app.workspace) {
    app.workspace.openLinkText("LifeMentor_Extra/Pages/Today_Input", "", false);
  }
}

// Show loading hint briefly before redirect
dv.container.createEl("div", { cls: "muted", text: "Redirecting..." });
```

<div class="lm-nav">
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
<a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Today_Input" href="LifeMentor_Extra/Pages/Today_Input">☀️ Today</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 Record</a>
</div>

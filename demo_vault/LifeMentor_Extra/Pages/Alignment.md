---
lm_page: alignment
---

# Alignment 🧭

Focus: one card, one experiment, two buttons — keep it minimal.

```dataviewjs
const API_BASE = "http://127.0.0.1:8010";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const CACHE_KEY = "lm_alignment_" + today;

// Read from local cache
function getCache() {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) return JSON.parse(cached);
  } catch (e) {}
  return null;
}

// Save to local cache
function setCache(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
  } catch (e) {}
}

// i18n: translate server-side goal/value keys (may come from filesystem names)
const _i18n = {"健康":"Health","向内求":"Inner Growth","家庭":"Family","钱":"Wealth","健身入门":"Fitness Basics","增重到65kg":"Weight Goal","投资收益率26年达标":"Investment Return","理财学习":"Financial Literacy","自由泳1km":"Freestyle Swim 1km","记录自己":"Self-Journaling","读20本书":"Read 20 Books","q1无效手机时间日均小于1.5h":"Screen Time < 1.5h/day"};

// Sanitize text: strip CJK characters that may leak from server-side file names
function _sanitize(s) {
  return (s || "").replace(/[\u4e00-\u9fff\u3400-\u4dbf]+/g, "").replace(/\s{2,}/g, " ").trim();
}
// Translate a value/goal name: try i18n map first, then sanitize
function _tr(s) {
  const t = (s || "").trim();
  if (_i18n[t]) return _i18n[t];
  for (const [k, v] of Object.entries(_i18n)) {
    if (t.includes(k)) return v;
  }
  return _sanitize(t) || t;
}

// Fetch alignment data from server
async function fetchAlignment(forceRefresh = false) {
  // Check cache first
  if (!forceRefresh) {
    const cached = getCache();
    if (cached) return cached;
  }

  try {
    const res = await fetch(`${API_BASE}/alignment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: today }),
    });
    const data = await res.json();
    if (data && !data.error) {
      setCache(data);
    }
    return data;
  } catch (e) {
    // Fall back to cache
    return getCache() || null;
  }
}

// Save active goals
async function saveActiveGoals(goals) {
  try {
    await fetch(`${API_BASE}/alignment/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: goals }),
    });
  } catch (e) {}
}

// Render page
async function render(forceRefresh = false) {
  const data = await fetchAlignment(forceRefresh) || {};

  const grid = dv.container.createEl("div", { cls: "align-grid" });

  // Left: Self Mirror
  const left = grid.createEl("div", { cls: "card align-card" });
  const leftHead = left.createEl("div", { cls: "head" });
  const leftLabel = leftHead.createEl("div", { cls: "label" });
  leftLabel.appendText("Self Mirror ");
  leftLabel.createEl("span", { cls: "badge", text: "NOW" });

  // Edit value button
  const editBtn = leftHead.createEl("button", { cls: "btn ghost", text: "✏️ Edit" });
  editBtn.style.padding = "6px 12px";
  editBtn.style.fontSize = "12px";

  // Metrics section
  const m = data?.metrics || {};
  const metricsDiv = left.createEl("div", { cls: "muted" });
  metricsDiv.style.marginBottom = "12px";
  const nightH = m.night_screen_hours ?? (m.screen_time_hours ? Math.round(m.screen_time_hours * 0.06 * 10) / 10 : 0.2);
  metricsDiv.innerHTML = `😴 ${m.sleep_hours ?? "-"}h &nbsp;·&nbsp; 📱 ${m.screen_time_hours ?? "-"}h &nbsp;·&nbsp; 🌙 ${nightH}h`;

  // Value selection popup (hidden by default)
  const selectBox = left.createEl("div", { cls: "card" });
  selectBox.style.display = "none";
  selectBox.style.background = "#f9fafb";
  selectBox.style.marginBottom = "12px";

  const activeGoals = data?.active_goals || [];
  const goalOptions = (data?.goal_options || ["Health","Growth","Wealth"]).map(g => _i18n[g] || g).filter(g => g !== "Values" && g !== "Goals");

  // Get current main value from value_board
  const currentMain = (data?.value_board || []).find(v => v.role === "main")?.value?.replace(/^[^\w\u4e00-\u9fa5]+/, "") || "";
  let mainGoal = currentMain;
  let selectedGoals = [...activeGoals];

  // Primary value selection
  selectBox.createEl("div", { cls: "muted", text: "Select primary value (1)" });
  const mainChips = selectBox.createEl("div", { cls: "chips" });
  const mainChipMap = {};

  goalOptions.forEach(g => {
    const isMain = g === mainGoal || g.includes(mainGoal) || mainGoal.includes(g);
    const chip = mainChips.createEl("div", { cls: isMain ? "chip active" : "chip", text: "⭐ " + g });
    mainChipMap[g] = chip;
    chip.addEventListener("click", () => {
      Object.values(mainChipMap).forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      mainGoal = g;
      if (!selectedGoals.includes(g)) selectedGoals.push(g);
      // Rebuild secondary chips to exclude new primary
      rebuildSubChips();
    });
  });

  selectBox.createEl("div", { cls: "hr" });

  // Secondary value selection (exclude primary)
  selectBox.createEl("div", { cls: "muted", text: "Select secondary values (multi)" });
  const subChips = selectBox.createEl("div", { cls: "chips" });
  const subChipMap = {};

  function rebuildSubChips() {
    subChips.innerHTML = "";
    goalOptions.filter(g => g !== mainGoal).forEach(g => {
      const isActive = selectedGoals.includes(g);
      const chip = subChips.createEl("div", { cls: isActive ? "chip active" : "chip", text: g });
      subChipMap[g] = chip;
      chip.addEventListener("click", () => {
        if (selectedGoals.includes(g)) {
          selectedGoals = selectedGoals.filter(x => x !== g);
          chip.classList.remove("active");
        } else {
          selectedGoals.push(g);
          chip.classList.add("active");
        }
      });
    });
  }
  rebuildSubChips();

  const selectBtnRow = selectBox.createEl("div", { cls: "btnrow" });
  const confirmBtn = selectBtnRow.createEl("button", { cls: "btn ghost", text: "Save" });
  confirmBtn.addEventListener("click", () => {
    confirmBtn.disabled = true;
    confirmBtn.innerText = "Saving...";
    const orderedGoals = [mainGoal, ...selectedGoals.filter(g => g !== mainGoal)];
    // Fire save in background, don't wait
    saveActiveGoals(orderedGoals).catch(() => {});
    // Keep cache intact — alignment data is still valid to display
    // User can click Refresh to get fresh LLM analysis with new goals
    // Instant UI feedback — close panel, done
    setTimeout(() => {
      confirmBtn.innerText = "Saved ✓";
      selectBox.style.display = "none";
      editBtn.innerText = "✏️ Edit";
      confirmBtn.disabled = false;
      confirmBtn.innerText = "Save";
    }, 400);
  });

  const cancelBtn = selectBtnRow.createEl("button", { cls: "btn ghost", text: "Cancel" });
  cancelBtn.addEventListener("click", () => {
    selectBox.style.display = "none";
    editBtn.innerText = "✏️ Edit";
  });

  // Edit button click handler
  editBtn.addEventListener("click", () => {
    if (selectBox.style.display === "none") {
      selectBox.style.display = "block";
      editBtn.innerText = "Collapse";
    } else {
      selectBox.style.display = "none";
      editBtn.innerText = "✏️ Edit";
    }
  });

  // Display value_board
  const lb = data?.value_board || [];
  if (lb.length === 0) {
    left.createEl("div", { cls: "muted", text: "No data yet. Click Edit to pick values." });
  }
  for (const x of lb) {
    const cls = x.role === "main" ? "vrow main" : "vrow";
    const row = left.createEl("div", { cls });
    const name = row.createEl("div", { cls: "vname" });
    name.appendText(_tr(x.value) || "-");
    name.appendText(" ");
    name.createEl("span", { cls: x.role === "main" ? "badge blue" : "badge", text: x.role === "main" ? "main" : "sub" });
    const trendIcon = x.trend === "up" ? "↑" : x.trend === "down" ? "↓" : "→";
    row.createEl("div", { cls: "vstatus", text: trendIcon });
    row.createEl("div", { cls: "vnote", text: _sanitize(x.summary) || "" });
  }

  left.createEl("div", { cls: "hr" });
  left.createEl("div", { cls: "muted", text: "Pattern" });
  left.createEl("div", { text: _sanitize(data?.pattern) || "—" });

  // Right: This Week's Focus
  const right = grid.createEl("div", { cls: "card align-card focus-card" });
  const rightLabel = right.createEl("div", { cls: "label" });
  rightLabel.appendText("This Week's Focus ");
  rightLabel.createEl("span", { cls: "badge", text: "Suggested · 7 days" });

  const focusData = data?.focus || {};
  right.createEl("div", { cls: "focus-title", text: _sanitize(focusData.name) || "Sleep Guard: move phone away from bed" });

  const focus = right.createEl("div", { cls: "focus-block" });
  focus.createEl("div", { cls: "muted", text: "Goal" });
  focus.createEl("div", { text: _sanitize(focusData.intent) || "Reduce late-night phone use to protect sleep." });
  focus.createEl("div", { cls: "muted", text: "Why" }).style.marginTop = "10px";
  focus.createEl("div", { text: _sanitize(focusData.why) || "Lately it's been hard to put down the phone before bed." });

  const btnrow = right.createEl("div", { cls: "btnrow" });
  const adoptBtn = btnrow.createEl("button", {
    cls: "btn ghost",
    text: 'Adopt 7-day experiment',
  });
  adoptBtn.addEventListener("click", () => {
    if (app && app.workspace) {
      app.workspace.openLinkText("LifeMentor_Extra/Pages/Today_Input", "", false);
    }
  });

  const focusEditBtn = btnrow.createEl("button", {
    cls: "btn ghost",
    text: 'Edit',
  });
  focusEditBtn.addEventListener("click", () => {
    alert("Edit focus: you can change duration, goal, and execution details.");
  });

  right.createEl("div", { cls: "hr" });
  right.createEl("div", { cls: "muted", text: "Execution hint" });
  right.createEl("div", { cls: "muted", text: 'Keep the charger in the living room; at 11 PM just do this one step: put the phone there.' });

  // Refresh button
  const actionRow = dv.container.createEl("div", { cls: "btnrow" });
  const refreshBtn = actionRow.createEl("button", { cls: "btn ghost", text: "🔄 Refresh" });
  refreshBtn.addEventListener("click", async () => {
    refreshBtn.disabled = true;
    refreshBtn.innerText = "Loading...";
    dv.container.innerHTML = "";
    await render(true);
  });
}

render(false);
```

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Today" href="LifeMentor_Extra/Pages/Today">☀️ Today</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 Record</a>
</div>

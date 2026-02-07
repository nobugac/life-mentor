---
lm_page: night
---

# Night 🌙

<div class="subline">晚间回顾与建议，内容来自今日日记。</div>

```dataviewjs
const dailyFolder = "diary/2026/day";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const path = `${dailyFolder}/${today}.md`;

const extractSection = (text, heading) => {
  const pattern = new RegExp(`^##\\s+${heading}\\s*\\n([\\s\\S]*?)(?=^#\\s|^##\\s|\\Z)`, "m");
  const match = text.match(pattern);
  return match ? match[1].trim() : "";
};

let raw;
try {
  raw = await dv.io.load(path);
} catch (e) {
  raw = "";
}

const summary = raw ? extractSection(raw, "晚间总结") : "";
const advice = raw ? extractSection(raw, "晚间建议") : "";

const grid = dv.container.createEl("div", { cls: "night-grid" });

const left = grid.createEl("div", { cls: "card" });
const leftHead = left.createEl("div", { cls: "head" });
leftHead.createEl("div", { cls: "label", text: "🌙 晚间总结" });
leftHead.createEl("span", { cls: "badge", text: "from Daily" });
left.createEl("div", { cls: "text", text: summary || "（尚未填写）" });

const right = grid.createEl("div", { cls: "card" });
const rightHead = right.createEl("div", { cls: "head" });
rightHead.createEl("div", { cls: "label", text: "🔮 晚间建议" });
rightHead.createEl("span", { cls: "badge" , text: "server" });
right.createEl("div", { cls: "text", text: advice || "（尚未生成）" });

const row = dv.container.createEl("div", { cls: "btnrow" });
const btn = row.createEl("button", { cls: "btn", text: "提交晚间总结" });
btn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-evening");
  }
});
const microBtn = row.createEl("button", { cls: "btn ghost", text: "微调执行记录" });
microBtn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-micro-action");
  }
});

if (!raw) {
  const warning = dv.container.createEl("div", { cls: "card" });
  warning.createEl("div", { cls: "label", text: "未找到今日日记" });
  warning.createEl("div", { cls: "muted", text: `路径：${path}` });
}
```

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Today_Input" href="LifeMentor_Extra/Pages/Today_Input">☀️ Today</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 记录</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Settings" href="LifeMentor_Extra/Pages/Settings">⚙️ Settings</a>
</div>

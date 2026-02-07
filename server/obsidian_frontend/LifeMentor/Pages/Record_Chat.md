---
lm_page: record
---

# 记录 📝

<div class="subline">随手记录会写入今日日记的「记录」。</div>

```dataviewjs
const dailyFolder = "diary/2026/day";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const path = `${dailyFolder}/${today}.md`;

const extractSubsection = (text, heading) => {
  const pattern = new RegExp(`^###\\s+${heading}\\s*\\n([\\s\\S]*?)(?=^##\\s|^###\\s|\\Z)`, "m");
  const match = text.match(pattern);
  return match ? match[1].trim() : "";
};

const cleanLine = (line) => line.replace(/^[-*]\\s*/, "").trim();

let raw;
try {
  raw = await dv.io.load(path);
} catch (e) {
  raw = "";
}

const block = raw ? extractSubsection(raw, "记录") : "";
const lines = block
  ? block
      .split("\n")
      .map(cleanLine)
      .filter(Boolean)
  : [];
const latest = lines.slice(-5).reverse();

const card = dv.container.createEl("div", { cls: "card" });
const head = card.createEl("div", { cls: "head" });
head.createEl("div", { cls: "label", text: "🗒️ 最近记录" });
head.createEl("span", { cls: "badge", text: latest.length ? `${latest.length} 条` : "暂无" });

if (latest.length) {
  latest.forEach((item) => {
    const row = card.createEl("div", { cls: "text" });
    row.setText(item);
  });
} else {
  card.createEl("div", { cls: "muted", text: "还没有记录，先写一条吧。" });
}

const row = dv.container.createEl("div", { cls: "btnrow" });
const btn = row.createEl("button", { cls: "btn", text: "添加记录" });
btn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-record");
  }
});

if (!raw) {
  const warning = dv.container.createEl("div", { cls: "card" });
  warning.createEl("div", { cls: "label", text: "未找到今日日记" });
  warning.createEl("div", { cls: "muted", text: `路径：${path}` });
}
```

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Home" href="LifeMentor/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Alignment" href="LifeMentor/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Today_Input" href="LifeMentor/Pages/Today_Input">☀️ Today</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Night" href="LifeMentor/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor/Pages/Record_Chat" href="LifeMentor/Pages/Record_Chat">📝 记录</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Settings" href="LifeMentor/Pages/Settings">⚙️ Settings</a>
</div>

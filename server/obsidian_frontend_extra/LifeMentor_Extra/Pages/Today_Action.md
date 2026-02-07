---
lm_page: today_action
---

# Today Action ✅

<div class="subline">只展示「今日微调」与「今日一句话」。</div>

```dataviewjs
const dailyFolder = "diary/2026/day";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const path = `${dailyFolder}/${today}.md`;

const extractSubsection = (text, heading) => {
  const pattern = new RegExp(`^###\\s+${heading}\\s*\\n([\\s\\S]*?)(?=^##\\s|^###\\s|\\Z)`, "m");
  const match = text.match(pattern);
  return match ? match[1].trim() : "";
};

const pickLastEntry = (block) => {
  if (!block) return "";
  const lines = block
    .split("\n")
    .map((line) => line.replace(/^[-*]\\s*/, "").trim())
    .filter(Boolean);
  if (!lines.length) return "";
  const last = lines[lines.length - 1];
  return last.replace(/^\[[0-9:]+\]\\s*/, "");
};

let raw;
try {
  raw = await dv.io.load(path);
} catch (e) {
  raw = "";
}

const microText = raw ? pickLastEntry(extractSubsection(raw, "今日微调")) : "";
const oneLine = raw ? pickLastEntry(extractSubsection(raw, "今日一句话")) : "";

const grid = dv.container.createEl("div", { cls: "today-grid" });

const left = grid.createEl("div", { cls: "card" });
const head = left.createEl("div", { cls: "head" });
head.createEl("div", { cls: "label", text: "🧩 今日实验动作（只做一步）" });
head.createEl("span", { cls: "badge amber", text: "1 条" });

const actionCard = left.createEl("div", { cls: "card action-card" });
const actionText = actionCard.createEl("div", { cls: "action-text" });
actionText.createEl("span", { cls: "action-label", text: "动作：" });
actionText.createEl("span", { cls: "action-value", text: microText || "（尚未生成）" });

const actionRow = actionCard.createEl("div", { cls: "btnrow" });
const recordBtn = actionRow.createEl("button", { cls: "btn", text: "记录执行结果" });
recordBtn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-micro-action");
  }
});
const refreshBtn = actionRow.createEl("button", { cls: "btn ghost", text: "重新生成" });
refreshBtn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-morning");
  }
});
const nightLink = actionRow.createEl("a", {
  cls: "btn ghost internal-link",
  text: "去晚间回顾 →",
  href: "LifeMentor_Extra/Pages/Night",
});
nightLink.setAttribute("data-href", "LifeMentor_Extra/Pages/Night");

left.createEl("div", { cls: "hr" });
left.createEl("div", { cls: "muted", text: "可选灵感" });
const chipRow = left.createEl("div", { cls: "chips" });
["🌱 10 分钟散步", "🧘 3 分钟呼吸", "📓 写一句感受"].forEach((text) => {
  chipRow.createEl("div", { cls: "chip", text });
});

const right = grid.createEl("div", { cls: "card" });
const rightHead = right.createEl("div", { cls: "head" });
rightHead.createEl("div", { cls: "label", text: "今天一句话（仅记录）" });
rightHead.createEl("span", { cls: "badge", text: "from Today" });
right.createEl("div", {
  cls: "text",
  text: oneLine || "（未填写）",
});
right.createEl("div", { cls: "hr" });
right.createEl("div", { cls: "muted", text: "提示" });
right.createEl("div", { cls: "text", text: "内容来自今日日记的「今日一句话」。" });

if (!raw) {
  const warning = dv.container.createEl("div", { cls: "card" });
  warning.createEl("div", { cls: "label", text: "未找到今日日记" });
  warning.createEl("div", { cls: "muted", text: `路径：${path}` });
}
```

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Today_Action" href="LifeMentor_Extra/Pages/Today_Action">✅ Action</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 记录</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Settings" href="LifeMentor_Extra/Pages/Settings">⚙️ Settings</a>
</div>

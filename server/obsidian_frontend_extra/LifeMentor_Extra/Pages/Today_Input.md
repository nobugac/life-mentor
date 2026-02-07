---
lm_page: today_input
---

# Today ☀️

<div class="subline">在 Obsidian 内完成今日输入 → 调用服务端生成「今日微调」。</div>

<div class="card">
  <div class="head">
    <div class="label">📝 今日一句话</div>
    <span class="badge">可选</span>
  </div>
  <div class="text">点击下方按钮后，会弹出输入框。内容会写入今日日记的「今日一句话」。</div>

```dataviewjs
const row = dv.container.createEl("div", { cls: "btnrow" });
const btn = row.createEl("button", { cls: "btn", text: "继续 → 生成今日微调" });
btn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-morning");
  }
});
const ghost = row.createEl("button", { cls: "btn ghost", text: "刷新对齐" });
ghost.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-alignment");
  }
});
```

  <div class="muted" style="margin-top:10px;">微调生成完成后，去「Today Action」查看结果。</div>
</div>

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Today_Input" href="LifeMentor_Extra/Pages/Today_Input">☀️ Today</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 记录</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Settings" href="LifeMentor_Extra/Pages/Settings">⚙️ Settings</a>
</div>

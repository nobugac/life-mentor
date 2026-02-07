---
lm_page: settings
---

# Settings ⚙️

<div class="card">
  <div class="label">插件与样式</div>
  <div class="text">
    需要启用以下内容，才能让页面与服务端交互：
  </div>
  <div class="text" style="margin-top:8px;">
    1. 安装并启用插件：<strong>Life Mentor Bridge</strong><br />
    2. 在插件设置里填入 <strong>Server URL</strong> 与 <strong>UI Token</strong><br />
    3. 启用 CSS Snippet：<code>lifementor-native.css</code>
  </div>
</div>

<div class="card">
  <div class="label">快捷操作</div>

```dataviewjs
const row = dv.container.createEl("div", { cls: "btnrow" });
const mockBtn = row.createEl("button", { cls: "btn", text: "Mock 屏幕时间" });
mockBtn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-mock-screen-time");
  }
});
const alignBtn = row.createEl("button", { cls: "btn ghost", text: "刷新对齐" });
alignBtn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-alignment");
  }
});
```

  <div class="muted" style="margin-top:10px;">这些按钮会调用 Obsidian 插件，与服务端交互。</div>
</div>

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Today_Input" href="LifeMentor_Extra/Pages/Today_Input">☀️ Today</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 记录</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Settings" href="LifeMentor_Extra/Pages/Settings">⚙️ Settings</a>
</div>

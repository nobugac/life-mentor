---
lm_page: alignment
---

# Alignment 🧭

<div class="subline">对齐页会读取「今日日记」里的 <code>## 对齐</code> 小节内容。</div>

```dataviewjs
const dailyFolder = "diary/2026/day";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const path = `${dailyFolder}/${today}.md`;

const extractSection = (text, heading) => {
  const pattern = new RegExp(`^##\\s+${heading}\\s*\\n([\\s\\S]*?)(?=^#\\s|^##\\s|\\Z)`, "m");
  const match = text.match(pattern);
  return match ? match[1].trim() : "";
};

const splitBlocks = (text) => {
  const blocks = {};
  const pattern = /^###\\s+(.+)\\n([\\s\\S]*?)(?=^###\\s+|\\Z)/gm;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    blocks[match[1].trim()] = (match[2] || "").trim();
  }
  return blocks;
};

const parseMetrics = (block) => {
  const lines = block.split("\n").map((line) => line.replace(/^[-*]\\s*/, "").trim());
  const pick = (label) => {
    const line = lines.find((l) => l.startsWith(`${label}：`));
    return line ? line.replace(`${label}：`, "").trim() : "-";
  };
  return {
    sleep: pick("睡眠"),
    screen: pick("屏幕"),
    night: pick("夜间屏幕"),
  };
};

const parseBoard = (block) => {
  const rows = [];
  const lines = block.split("\n").filter((line) => line.trim().startsWith("|"));
  const dataLines = lines.slice(2);
  dataLines.forEach((line) => {
    const parts = line
      .split("|")
      .map((part) => part.trim())
      .filter((part) => part.length > 0);
    if (parts.length >= 4) {
      rows.push({
        value: parts[0],
        role: parts[1],
        trend: parts[2],
        summary: parts[3],
      });
    }
  });
  return rows;
};

const parseFocus = (block) => {
  const lines = block.split("\n").map((line) => line.replace(/^[-*]\\s*/, "").trim());
  const pick = (label) => {
    const line = lines.find((l) => l.startsWith(`${label}：`));
    return line ? line.replace(`${label}：`, "").trim() : "";
  };
  return {
    name: pick("主题"),
    intent: pick("意图"),
    why: pick("原因"),
  };
};

let raw;
try {
  raw = await dv.io.load(path);
} catch (e) {
  raw = "";
}

if (!raw) {
  const card = dv.container.createEl("div", { cls: "card" });
  card.createEl("div", { cls: "label", text: "未找到今日日记" });
  card.createEl("div", { cls: "muted", text: `路径：${path}` });
} else {
  const section = extractSection(raw, "对齐");
  if (!section) {
    const card = dv.container.createEl("div", { cls: "card" });
    card.createEl("div", { cls: "label", text: "未找到对齐内容" });
    card.createEl("div", { cls: "muted", text: "请点击下方按钮「刷新对齐」" });
  } else {
    const blocks = splitBlocks(section);
    const metrics = parseMetrics(blocks["指标"] || "");
    const board = parseBoard(blocks["Value Board"] || "");
    const focus = parseFocus(blocks["Focus"] || "");
    const pattern = (blocks["Pattern"] || "").trim() || "—";
    const snapshot = (blocks["Snapshot"] || "").trim();

    const grid = dv.container.createEl("div", { cls: "align-grid" });

    const left = grid.createEl("div", { cls: "card align-card" });
    const leftLabel = left.createEl("div", { cls: "label" });
    leftLabel.appendText("自我镜像 ");
    leftLabel.createEl("span", { cls: "badge", text: "NOW" });

    const metricsWrap = left.createEl("div");
    metricsWrap.createEl("div", { cls: "muted", text: "指标" });
    metricsWrap.createEl("div", {
      cls: "text",
      text: `睡眠：${metrics.sleep} / 屏幕：${metrics.screen} / 夜间屏幕：${metrics.night}`,
    });

    if (snapshot) {
      left.createEl("div", { cls: "hr" });
      left.createEl("div", { cls: "muted", text: "Snapshot" });
      left.createEl("div", { text: snapshot });
    }

    if (board.length) {
      left.createEl("div", { cls: "hr" });
      board.forEach((item) => {
        const row = left.createEl("div", { cls: item.role === "main" ? "vrow main" : "vrow" });
        row.createEl("div", { cls: "vname", text: item.value || "-" });
        row.createEl("div", { cls: "vstatus", text: item.trend || "-" });
        row.createEl("div", { cls: "vnote", text: item.summary || "-" });
      });
    }

    left.createEl("div", { cls: "hr" });
    left.createEl("div", { cls: "muted", text: "Pattern" });
    left.createEl("div", { text: pattern });

    const right = grid.createEl("div", { cls: "card align-card focus-card" });
    const rightLabel = right.createEl("div", { cls: "label" });
    rightLabel.appendText("本周 Focus ");
    rightLabel.createEl("span", { cls: "badge", text: "推荐实验" });

    if (focus.name) {
      right.createEl("div", { cls: "focus-title", text: focus.name });
    }
    const focusBlock = right.createEl("div", { cls: "focus-block" });
    if (focus.intent) {
      focusBlock.createEl("div", { cls: "muted", text: "目标" });
      focusBlock.createEl("div", { text: focus.intent });
    }
    if (focus.why) {
      focusBlock.createEl("div", { cls: "muted", text: "为什么" }).style.marginTop = "10px";
      focusBlock.createEl("div", { text: focus.why });
    }
    if (!focus.name && !focus.intent && !focus.why) {
      focusBlock.createEl("div", { cls: "muted", text: "暂无 Focus，先刷新对齐。" });
    }
  }
}

const btnRow = dv.container.createEl("div", { cls: "btnrow" });
const actionBtn = btnRow.createEl("button", { cls: "btn", text: "刷新对齐" });
actionBtn.addEventListener("click", () => {
  if (app && app.commands) {
    app.commands.executeCommandById("life-mentor-alignment");
  }
});
const openToday = btnRow.createEl("a", {
  cls: "btn ghost internal-link",
  text: "查看今日日记",
  href: path,
});
openToday.setAttribute("data-href", path);
```

<div class="lm-nav">
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Home" href="LifeMentor/Home">🏠 Home</a>
  <a class="internal-link lm-nav-link active" data-href="LifeMentor/Pages/Alignment" href="LifeMentor/Pages/Alignment">🧭 Alignment</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Today_Input" href="LifeMentor/Pages/Today_Input">☀️ Today</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Night" href="LifeMentor/Pages/Night">🌙 Night</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Record_Chat" href="LifeMentor/Pages/Record_Chat">📝 记录</a>
  <a class="internal-link lm-nav-link" data-href="LifeMentor/Pages/Settings" href="LifeMentor/Pages/Settings">⚙️ Settings</a>
</div>

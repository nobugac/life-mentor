const {
  Plugin,
  Notice,
  Setting,
  PluginSettingTab,
  FuzzySuggestModal,
  Modal,
  requestUrl,
} = require("obsidian");

const DEFAULT_SETTINGS = {
  serverUrl: "http://127.0.0.1:8010",
  uiToken: "",
  dailyNoteFolder: "diary/2026/day",
  alignmentHeading: "对齐",
  lastMicroAction: null,
};

function formatDateISO(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

class TextPromptModal extends Modal {
  constructor(app, { title, placeholder, value, multiline }) {
    super(app);
    this.title = title;
    this.placeholder = placeholder;
    this.value = value || "";
    this.multiline = Boolean(multiline);
    this._resolve = null;
    this._submitted = false;
  }

  openAndGetValue() {
    return new Promise((resolve) => {
      this._resolve = resolve;
      this.open();
    });
  }

  onOpen() {
    this.modalEl.addClass("life-mentor-modal");
    const { contentEl } = this;
    contentEl.empty();
    if (this.title) {
      contentEl.createEl("h3", { text: this.title });
    }

    let inputEl;
    if (this.multiline) {
      inputEl = contentEl.createEl("textarea");
    } else {
      inputEl = contentEl.createEl("input", { type: "text" });
    }
    inputEl.placeholder = this.placeholder || "";
    inputEl.value = this.value;
    inputEl.focus();

    const buttonRow = contentEl.createDiv({ cls: "life-mentor-modal__actions" });
    const submitBtn = buttonRow.createEl("button", { text: "确认" });
    const cancelBtn = buttonRow.createEl("button", { text: "取消" });

    submitBtn.addEventListener("click", () => {
      this._submitted = true;
      const result = inputEl.value.trim();
      if (this._resolve) {
        this._resolve(result);
      }
      this.close();
    });

    cancelBtn.addEventListener("click", () => {
      this.close();
    });
  }

  onClose() {
    if (!this._submitted && this._resolve) {
      this._resolve(null);
    }
    this._resolve = null;
  }
}

class ActionSuggestModal extends FuzzySuggestModal {
  constructor(app, onChoose) {
    super(app);
    this.onChoose = onChoose;
    this.actions = [
      { id: "adopt", label: "采纳" },
      { id: "ignore", label: "忽略" },
      { id: "modify", label: "修改" },
    ];
  }

  getItems() {
    return this.actions;
  }

  getItemText(item) {
    return item.label;
  }

  onChooseItem(item) {
    if (this.onChoose) {
      this.onChoose(item);
    }
  }
}

module.exports = class LifeMentorBridgePlugin extends Plugin {
  async onload() {
    await this.loadSettings();

    this.addCommand({
      id: "life-mentor-alignment",
      name: "Life Mentor: 刷新对齐",
      callback: () => this.runAlignment(),
    });

    this.addCommand({
      id: "life-mentor-morning",
      name: "Life Mentor: 今日输入 -> 生成微调",
      callback: () => this.runMorning(),
    });

    this.addCommand({
      id: "life-mentor-evening",
      name: "Life Mentor: 晚间总结 -> 生成建议",
      callback: () => this.runEvening(),
    });

    this.addCommand({
      id: "life-mentor-record",
      name: "Life Mentor: 添加记录",
      callback: () => this.runRecord(),
    });

    this.addCommand({
      id: "life-mentor-micro-action",
      name: "Life Mentor: 微调执行记录",
      callback: () => this.runSuggestionAction(),
    });

    this.addCommand({
      id: "life-mentor-mock-screen-time",
      name: "Life Mentor: Mock 屏幕时间",
      callback: () => this.runMockScreenTime(),
    });

    this.addSettingTab(new LifeMentorSettingTab(this.app, this));
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async ensureFolderPath(folderPath) {
    if (!folderPath) return;
    const parts = folderPath.split("/").filter(Boolean);
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      const existing = this.app.vault.getAbstractFileByPath(current);
      if (!existing) {
        await this.app.vault.createFolder(current);
      }
    }
  }

  async ensureDailyFile(date) {
    const folder = (this.settings.dailyNoteFolder || "").trim();
    const relPath = folder ? `${folder}/${date}.md` : `${date}.md`;
    let file = this.app.vault.getAbstractFileByPath(relPath);
    if (!file) {
      if (folder) {
        await this.ensureFolderPath(folder);
      }
      await this.app.vault.create(relPath, `# ${date}\n`);
      file = this.app.vault.getAbstractFileByPath(relPath);
    }
    return file;
  }

  async getDailyContext() {
    const active = this.app.workspace.getActiveFile();
    if (active && this.isDailyNoteFile(active)) {
      return { file: active, date: this.getDateFromFile(active), usedActive: true };
    }
    const date = formatDateISO(new Date());
    const file = await this.ensureDailyFile(date);
    if (!file) {
      new Notice("未找到今日日记");
      return null;
    }
    if (active) {
      new Notice(`未在日记页，已使用今日日记 ${date}`);
    }
    return { file, date, usedActive: false };
  }

  isDailyNoteFile(file) {
    const folder = (this.settings.dailyNoteFolder || "").trim();
    if (folder) {
      return file.path.startsWith(`${folder}/`);
    }
    return /\d{4}-\d{2}-\d{2}/.test(file.basename);
  }

  getDateFromFile(file) {
    const match = file.basename.match(/\d{4}-\d{2}-\d{2}/);
    if (match) {
      return match[0];
    }
    return formatDateISO(new Date());
  }

  extractSection(text, heading, level = 2) {
    const hashes = "#".repeat(level);
    const pattern = new RegExp(
      `(^${hashes}\\s+${escapeRegExp(heading)}\\s*\\n)([\\s\\S]*?)(?=^#{1,${level}}\\s|\\Z)`,
      "m"
    );
    const match = text.match(pattern);
    if (!match) {
      return "";
    }
    return match[2].trim();
  }

  replaceOrAppendSection(text, heading, newBody, level = 2) {
    const hashes = "#".repeat(level);
    const pattern = new RegExp(
      `(^${hashes}\\s+${escapeRegExp(heading)}\\s*\\n)([\\s\\S]*?)(?=^#{1,${level}}\\s|\\Z)`,
      "m"
    );
    const body = (newBody || "").trim();
    if (pattern.test(text)) {
      return text.replace(pattern, (match, header) => `${header}${body}\\n\\n`);
    }
    return `${text.trimEnd()}\\n\\n${hashes} ${heading}\\n${body}\\n\\n`;
  }

  async getSectionOrPrompt(file, heading, promptTitle) {
    const content = await this.app.vault.read(file);
    const section = this.extractSection(content, heading);
    if (section) {
      return section;
    }
    const modal = new TextPromptModal(this.app, {
      title: promptTitle || heading,
      placeholder: `请输入${heading}`,
      multiline: true,
    });
    const value = await modal.openAndGetValue();
    return value ? value.trim() : "";
  }

  async apiPost(path, payload) {
    const base = (this.settings.serverUrl || "").trim();
    if (!base) {
      new Notice("请先在设置中填写 Server URL");
      return null;
    }
    const url = new URL(path, base).toString();
    const headers = {
      "Content-Type": "application/json",
    };
    const token = (this.settings.uiToken || "").trim();
    if (token) {
      headers["X-UI-Token"] = token;
    }

    try {
      const response = await requestUrl({
        url,
        method: "POST",
        headers,
        body: JSON.stringify(payload || {}),
      });
      if (response.status >= 400) {
        new Notice(`请求失败 (${response.status})`);
        return null;
      }
      return response.json;
    } catch (error) {
      new Notice("请求失败，请检查服务端是否启动");
      return null;
    }
  }

  formatAlignmentMarkdown(data) {
    const lines = [];
    const metrics = (data && data.metrics) || {};
    const sleepHours = Number.isFinite(metrics.sleep_hours)
      ? `${metrics.sleep_hours}h`
      : "-";
    const sleepScore = Number.isFinite(metrics.sleep_score) ? metrics.sleep_score : null;
    const screenHours = Number.isFinite(metrics.screen_time_hours)
      ? `${metrics.screen_time_hours}h`
      : "-";
    const nightHours = Number.isFinite(metrics.night_screen_hours)
      ? `${metrics.night_screen_hours}h`
      : "-";

    lines.push(`### 日期\\n- ${data && data.date ? data.date : formatDateISO(new Date())}`);
    lines.push("### 指标");
    lines.push(`- 睡眠：${sleepHours}${sleepScore !== null ? `（评分 ${sleepScore}）` : ""}`);
    lines.push(`- 屏幕：${screenHours}`);
    lines.push(`- 夜间屏幕：${nightHours}`);

    if (data && data.snapshot) {
      lines.push("### Snapshot");
      lines.push(String(data.snapshot));
    }

    if (data && data.pattern) {
      lines.push("### Pattern");
      lines.push(String(data.pattern));
    }

    const board = Array.isArray(data && data.value_board) ? data.value_board : [];
    if (board.length > 0) {
      lines.push("### Value Board");
      lines.push("| 价值 | 角色 | 趋势 | 小结 |");
      lines.push("| --- | --- | --- | --- |");
      board.forEach((item) => {
        const value = item.value || "-";
        const role = item.role || "-";
        const trend = item.trend || "-";
        const summary = item.summary || "-";
        lines.push(`| ${value} | ${role} | ${trend} | ${summary} |`);
      });
    }

    if (data && data.focus) {
      lines.push("### Focus");
      const focus = data.focus || {};
      if (focus.name) lines.push(`- 主题：${focus.name}`);
      if (focus.intent) lines.push(`- 意图：${focus.intent}`);
      if (focus.why) lines.push(`- 原因：${focus.why}`);
    }

    const goals = Array.isArray(data && data.active_goals) ? data.active_goals : [];
    if (goals.length > 0) {
      lines.push("### Active Goals");
      goals.forEach((goal) => {
        lines.push(`- ${goal}`);
      });
    }

    return lines.join("\\n") + "\\n";
  }

  async runAlignment() {
    const ctx = await this.getDailyContext();
    if (!ctx) return;
    const { file, date } = ctx;
    const data = await this.apiPost("/alignment", { date });
    if (!data) return;

    const content = await this.app.vault.read(file);
    const body = this.formatAlignmentMarkdown(data);
    const updated = this.replaceOrAppendSection(
      content,
      this.settings.alignmentHeading || "对齐",
      body,
      2
    );
    await this.app.vault.modify(file, updated);
    new Notice("对齐已更新");
  }

  async runMorning() {
    const ctx = await this.getDailyContext();
    if (!ctx) return;
    const { file, date } = ctx;
    const text = await this.getSectionOrPrompt(file, "今日一句话", "今日一句话");

    const data = await this.apiPost("/morning", {
      date,
      text: text || undefined,
    });

    if (data && data.micro_action) {
      this.settings.lastMicroAction = {
        date,
        text: data.micro_action.text || "",
        id: data.micro_action.id || null,
      };
      await this.saveSettings();
    }

    new Notice("今日微调已生成（如未刷新请重开文件）");
  }

  async runEvening() {
    const ctx = await this.getDailyContext();
    if (!ctx) return;
    const { file, date } = ctx;
    const journal = await this.getSectionOrPrompt(file, "晚间总结", "晚间总结");
    if (!journal) {
      new Notice("晚间总结为空");
      return;
    }

    await this.apiPost("/evening", {
      date,
      journal,
    });

    new Notice("晚间总结已提交（如未刷新请重开文件）");
  }

  async runRecord() {
    const ctx = await this.getDailyContext();
    if (!ctx) return;
    const { date } = ctx;
    const modal = new TextPromptModal(this.app, {
      title: "记录",
      placeholder: "输入记录内容",
      multiline: true,
    });
    const text = await modal.openAndGetValue();
    if (!text) return;

    await this.apiPost("/record", {
      date,
      text,
    });

    new Notice("记录已提交（如未刷新请重开文件）");
  }

  async runSuggestionAction() {
    const ctx = await this.getDailyContext();
    if (!ctx) return;
    const { file, date } = ctx;
    let suggestionText = "";

    if (this.settings.lastMicroAction && this.settings.lastMicroAction.date === date) {
      suggestionText = this.settings.lastMicroAction.text || "";
    }

    if (!suggestionText) {
      const content = await this.app.vault.read(file);
      const microSection = this.extractSection(content, "今日微调");
      if (microSection) {
        const lines = microSection
          .split("\\n")
          .map((line) => line.replace(/^[-*]\\s*/, "").trim())
          .filter(Boolean);
        suggestionText = lines[lines.length - 1] || "";
      }
    }

    const action = await new Promise((resolve) => {
      const modal = new ActionSuggestModal(this.app, (item) => resolve(item));
      modal.open();
    });

    if (!action) return;

    let modifiedText = null;
    if (action.id === "modify") {
      const modal = new TextPromptModal(this.app, {
        title: "修改后的微调",
        placeholder: "输入修改后的内容",
        value: suggestionText,
        multiline: true,
      });
      modifiedText = await modal.openAndGetValue();
      if (!modifiedText) return;
    }

    await this.apiPost("/suggestion/action", {
      date,
      action: action.id,
      suggestion_text: suggestionText || undefined,
      modified_text: modifiedText || undefined,
      type: "micro",
    });

    new Notice("微调执行已记录（如未刷新请重开文件）");
  }

  async runMockScreenTime() {
    const ctx = await this.getDailyContext();
    if (!ctx) return;
    const { date } = ctx;
    const baseTime = `${date}T00:00:00+08:00`;
    const endTime = `${date}T23:59:59+08:00`;

    const modal = new TextPromptModal(this.app, {
      title: "Mock 屏幕时间 (分钟)",
      placeholder: "例如 240",
      value: "240",
      multiline: false,
    });
    const minutesText = await modal.openAndGetValue();
    if (!minutesText) return;
    const minutes = Number(minutesText);
    if (!Number.isFinite(minutes) || minutes <= 0) {
      new Notice("请输入有效的分钟数");
      return;
    }

    const payload = {
      deviceId: "mock-device",
      rangeStart: baseTime,
      rangeEnd: endTime,
      generatedAt: endTime,
      localDate: date,
      usageTotalMs: Math.round(minutes * 60000),
      usageByApp: [
        { packageName: "mock.app", totalTimeMs: Math.round(minutes * 60000) },
      ],
      health: {},
    };

    const data = await this.apiPost("/ingest?update_note=true", payload);
    if (!data) return;

    new Notice("Mock 屏幕时间已写入（如未刷新请重开文件）");
  }
};

class LifeMentorSettingTab extends PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("Server URL")
      .setDesc("例如 http://127.0.0.1:8010")
      .addText((text) =>
        text
          .setPlaceholder("http://127.0.0.1:8010")
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("UI Token")
      .setDesc("与服务端配置的 UI Token 保持一致")
      .addText((text) =>
        text
          .setPlaceholder("token")
          .setValue(this.plugin.settings.uiToken)
          .onChange(async (value) => {
            this.plugin.settings.uiToken = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("日记目录")
      .setDesc("仅在此目录内写入日记，例如 diary/2026/day")
      .addText((text) =>
        text
          .setPlaceholder("diary/2026/day")
          .setValue(this.plugin.settings.dailyNoteFolder)
          .onChange(async (value) => {
            this.plugin.settings.dailyNoteFolder = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("对齐小节标题")
      .setDesc("默认写入 ## 对齐")
      .addText((text) =>
        text
          .setPlaceholder("对齐")
          .setValue(this.plugin.settings.alignmentHeading)
          .onChange(async (value) => {
            this.plugin.settings.alignmentHeading = value.trim() || "对齐";
            await this.plugin.saveSettings();
          })
      );
  }
}

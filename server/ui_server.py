#!/usr/bin/env python3
"""Minimal web UI for the daily helper (LLM intent parsing + vision).

启动后访问 http://localhost:8000（同一 WiFi 下可用局域网地址访问）
- 「日常」区域：输入一句话（如“早上帮我安排今天，我昨晚睡得一般”），选择 provider/model，点击发送
- 服务器用所选 LLM 解析早/晚流程、文字输入、日记等字段，调用 manage_day 更新 Obsidian 日记
- 「图片」区域：输入图片 URL 与提示，调用视觉模型（示例用 Ark）

准备：
1) pip install openai
2) export OPENAI_API_KEY 或 ARK_API_KEY
3) 可选：--goal-file 提供目标文本，模型会参考
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import chat_bot
import manage_day
from core import record_store
from core import state_recorder
from integrations.config import get_config

CONFIG = get_config()
RESULT_DIR = Path(str(CONFIG.get("vision_results_dir", Path(__file__).resolve().parent / "vision_results"))).expanduser()
IMAGE_DIR = Path(str(CONFIG.get("vision_images_dir", Path(__file__).resolve().parent / "vision_images"))).expanduser()
VAULT_ROOT = Path(str(CONFIG.get("vault_root", "/Users/sean/workspace/life/note"))).expanduser()
STATUS_TEMPLATE = VAULT_ROOT / "template" / "month_status_2026.md"
ALLOW_STATUS_WRITE = bool(CONFIG.get("allow_status_write", False))
VISION_PROMPT_PATH = Path(str(CONFIG.get("vision_prompt_path", ""))).expanduser()
GARMIN_DATA_ROOT = Path(
    str(CONFIG.get("garmin_data_root", Path(__file__).resolve().parent / "data" / "garmin"))
).expanduser()


def _load_prompt(path: Path) -> Optional[str]:
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return None


VISION_PROMPT_OVERRIDE = _load_prompt(VISION_PROMPT_PATH)


def _parse_date(value: Optional[str]) -> Optional[dt.date]:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except Exception:
        return None


def _fetch_garmin_payload(target_date: dt.date, is_cn: Optional[bool] = None) -> dict:
    try:
        from garminconnect import (  # type: ignore
            Garmin,
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        )
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Missing dependency: garminconnect. Install with: pip install garminconnect"
        ) from exc

    def login(client: Garmin) -> None:
        try:
            client.login()
        except GarminConnectAuthenticationError:
            mfa_code = os.environ.get("GARMIN_MFA_CODE")
            if not mfa_code:
                raise
            try:
                client.login(mfa_code)
            except TypeError as exc:
                raise GarminConnectAuthenticationError(
                    "MFA provided but garminconnect login() signature is incompatible"
                ) from exc

    def fetch_metric(
        client: Garmin,
        methods: list[str],
        date_str: str,
        date_obj: dt.date,
    ) -> tuple[object | None, str | None]:
        last_type_error: str | None = None
        for method_name in methods:
            method = getattr(client, method_name, None)
            if not callable(method):
                continue
            for args in ((date_str,), (date_obj,)):
                try:
                    return method(*args), None
                except TypeError as exc:
                    last_type_error = f"{method_name} TypeError: {exc}"
                    continue
                except Exception as exc:  # noqa: BLE001
                    return None, f"{method_name}: {exc.__class__.__name__}: {exc}"
        return None, last_type_error or "no compatible method found"

    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set GARMIN_EMAIL and GARMIN_PASSWORD in the environment.")

    tokenstore = os.environ.get("GARMIN_TOKENSTORE")
    is_cn_flag = is_cn if is_cn is not None else os.environ.get("GARMIN_IS_CN") == "1"

    try:
        if tokenstore:
            client = Garmin(email, password, is_cn=is_cn_flag, tokenstore=tokenstore)
        else:
            client = Garmin(email, password, is_cn=is_cn_flag)
    except TypeError:
        client = Garmin(email, password, is_cn=is_cn_flag)

    try:
        login(client)
    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    ) as exc:
        raise RuntimeError(f"Login failed: {exc}") from exc

    date_str = target_date.isoformat()
    metrics = {
        "sleep": ["get_sleep_data", "get_sleep_data_by_date"],
        "hrv": ["get_hrv_data", "get_hrv_data_by_date"],
        "heart_rate": ["get_heart_rates", "get_heart_rates_v2", "get_heart_rate"],
        "resting_heart_rate": ["get_rhr_day", "get_resting_heart_rate"],
        "steps": ["get_steps_data", "get_steps_data_by_date", "get_steps"],
        "daily_summary": ["get_daily_summary", "get_user_summary"],
    }

    utc_now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, object] = {
        "source": "garmin_connect",
        "date": date_str,
        "generated_at": utc_now.isoformat().replace("+00:00", "Z"),
        "data": {},
        "errors": {},
    }

    for name, methods in metrics.items():
        value, error = fetch_metric(client, methods, date_str, target_date)
        if value is not None:
            payload["data"][name] = value
        if error:
            payload["errors"][name] = error

    return payload

INDEX_HTML = """
<!doctype html>
<html lang="zh">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Life Mentor</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Fraunces:wght@600;700&display=swap');

    :root {
      --bg: #f6f1ea;
      --bg-2: #f0efe9;
      --ink: #1a1a19;
      --muted: #6b6258;
      --card: #fff8ef;
      --stroke: #e5d9cc;
      --accent: #ff7a45;
      --accent-2: #1ea7a8;
      --accent-3: #f6b73c;
      --accent-4: #3a6ea5;
      --shadow: 0 22px 60px rgba(27, 23, 18, 0.2);
      --radius: 26px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: "Space Grotesk", system-ui, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(246, 183, 60, 0.25), transparent 45%),
        radial-gradient(circle at 18% 70%, rgba(255, 122, 69, 0.18), transparent 55%),
        linear-gradient(160deg, var(--bg), var(--bg-2));
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px 16px 48px;
    }

    .stage {
      max-width: 1180px;
      width: 100%;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 28px;
      align-items: start;
    }

    .hero {
      padding: 8px 4px;
      display: grid;
      gap: 16px;
    }

    .hero h1 {
      font-family: "Fraunces", serif;
      font-size: clamp(30px, 4vw, 46px);
      margin: 0;
      letter-spacing: -0.02em;
    }

    .hero p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }

    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .pill {
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid var(--stroke);
      background: #fffdf7;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }

    .phone {
      background: #0f0f0f;
      border-radius: 36px;
      padding: 14px;
      box-shadow: var(--shadow);
      position: relative;
    }

    .screen {
      background: #fef9f2;
      border-radius: 28px;
      overflow: hidden;
      min-height: 720px;
      display: flex;
      flex-direction: column;
    }

    .status {
      height: 26px;
      padding: 0 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: #5d5d5d;
    }

    .header {
      padding: 18px 20px 10px;
      display: grid;
      gap: 10px;
    }

    .header h2 {
      margin: 0 0 4px;
      font-size: 20px;
      letter-spacing: -0.01em;
    }

    .header span {
      color: var(--muted);
      font-size: 12px;
    }

    .token-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .token-row input {
      padding: 8px 10px;
      border-radius: 12px;
      border: 1px solid var(--stroke);
      background: #fffdf7;
      font-size: 12px;
    }

    .token-row small { color: var(--muted); }

    .sync-bar {
      margin: 0 18px 12px;
      background: var(--card);
      border: 1px solid var(--stroke);
      border-radius: 18px;
      padding: 12px 14px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      animation: rise 0.5s ease-out;
    }

    .sync-chip {
      background: #fffdf8;
      border: 1px dashed var(--stroke);
      border-radius: 14px;
      padding: 10px;
    }

    .sync-chip h4 {
      margin: 0 0 4px;
      font-size: 12px;
      color: var(--muted);
    }

    .sync-chip strong { font-size: 16px; }

    .feed {
      padding: 0 18px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      flex: 1;
      overflow-y: auto;
    }

    .bubble {
      max-width: 92%;
      padding: 10px 12px;
      border-radius: 18px;
      border: 1px solid var(--stroke);
      background: #fff;
      display: grid;
      gap: 6px;
      animation: rise 0.4s ease-out;
    }

    .bubble.user {
      align-self: flex-end;
      background: #1a1a19;
      color: #fff;
      border-color: #1a1a19;
    }

    .bubble.system {
      align-self: center;
      background: transparent;
      border: none;
      color: var(--muted);
      font-size: 12px;
    }

    .bubble-meta {
      font-size: 11px;
      color: var(--muted);
    }

    .bubble.user .bubble-meta {
      color: #d2c7be;
    }

    .bubble-text {
      white-space: pre-line;
      font-size: 13px;
      line-height: 1.45;
    }

    label {
      font-size: 12px;
      color: var(--muted);
      display: grid;
      gap: 6px;
    }

    input[type="date"],
    input[type="text"],
    input[type="password"],
    textarea,
    select {
      width: 100%;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--stroke);
      font-family: inherit;
      background: #fffefb;
      font-size: 13px;
    }

    textarea { resize: vertical; min-height: 70px; }

    .composer {
      border-top: 1px solid var(--stroke);
      background: #fff4e6;
      padding: 12px 16px 16px;
      display: grid;
      gap: 12px;
    }

    .mode-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .mode-chip {
      border-radius: 999px;
      border: 1px solid var(--stroke);
      background: #fff8ef;
      color: var(--ink);
      font-weight: 600;
      font-size: 11px;
      padding: 6px 12px;
      cursor: pointer;
    }

    .mode-chip.active {
      background: var(--ink);
      color: #fff;
      border-color: var(--ink);
    }

    .mode-panel {
      display: none;
      gap: 10px;
      background: #fffdf6;
      border: 1px solid var(--stroke);
      border-radius: 18px;
      padding: 12px;
    }

    .mode-panel.active { display: grid; }

    .grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
    }

    .input-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: center;
    }

    button {
      border: none;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      padding: 10px 16px;
      border-radius: 14px;
      cursor: pointer;
      font-size: 13px;
    }

    button.ghost {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--stroke);
    }

    pre {
      background: #161311;
      color: #f9f6f0;
      border-radius: 14px;
      padding: 10px 12px;
      font-size: 12px;
      line-height: 1.45;
      max-height: 220px;
      overflow: auto;
      margin: 0;
    }

    .bubble.user pre { background: #2a201b; }

    .vision-preview {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .paste-box {
      width: 100%;
      min-height: 70px;
      max-height: 120px;
      border: 1px dashed var(--stroke);
      border-radius: 14px;
      padding: 10px 12px;
      background: #fffef8;
      overflow-y: auto;
      font-size: 12px;
      color: var(--muted);
    }

    .nav {
      display: flex;
      justify-content: space-around;
      padding: 10px 0 14px;
      background: #fff4e6;
      border-top: 1px solid var(--stroke);
      font-size: 11px;
      color: var(--muted);
    }

    .nav strong { color: var(--ink); }

    @keyframes rise {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 900px) {
      .hero { order: -1; }
      .phone { border-radius: 28px; }
      .screen { min-height: 640px; }
    }
  </style>
</head>
<body>
  <main class="stage">
    <section class="hero">
      <h1>Life Mentor</h1>
      <p>把所有日常更新串成对话。选择模式后直接发送，Garmin / Vision 也能一键触发。</p>
      <div class="pill-row">
        <span class="pill">对话入口</span>
        <span class="pill">手机使用时间自动上传</span>
        <span class="pill">Garmin 一键同步</span>
        <span class="pill">本地优先写入</span>
      </div>
    </section>

    <section class="phone">
      <div class="screen">
        <div class="status">
          <span>Local</span>
          <span>Daily • Sync</span>
        </div>
        <div class="header">
          <div>
            <h2>Life Mentor</h2>
            <span>所有输入都会写入你的 Obsidian</span>
          </div>
          <div class="token-row">
            <label>
              访问口令（可选）
              <input type="password" id="ui-token" placeholder="如设置了口令请输入">
            </label>
            <small id="token-status"></small>
          </div>
        </div>

        <div class="sync-bar">
          <div class="sync-chip">
            <h4>手机使用时间</h4>
            <strong>等待上传</strong>
            <div style="color: var(--muted); font-size: 11px;">上次同步 --</div>
          </div>
          <div class="sync-chip">
            <h4>Garmin</h4>
            <strong>待同步</strong>
            <div style="color: var(--muted); font-size: 11px;">HRV / RHR / 睡眠</div>
          </div>
        </div>

        <div class="feed" id="chat-feed">
          <div class="bubble system">准备就绪：选择模式开始输入。</div>
        </div>

        <div class="composer">
          <div class="mode-chips">
            <button class="mode-chip active" data-mode="morning">Morning</button>
            <button class="mode-chip" data-mode="vision">Vision</button>
            <button class="mode-chip" data-mode="garmin">Garmin</button>
            <button class="mode-chip" data-mode="evening">Evening</button>
            <button class="mode-chip" data-mode="record">Quick note</button>
          </div>

          <div class="mode-panel active" data-mode="morning">
            <label>日期（默认今天）
              <input type="date" id="morning-date">
            </label>
            <div style="font-size: 12px; color: var(--muted);">提示：如果有截图，会自动触发 Vision。</div>
          </div>

          <div class="mode-panel" data-mode="vision">
            <div class="grid-2">
              <label>图片日期（默认昨日）
                <input type="date" id="vision-date">
              </label>
              <label>Provider
                <select id="vision-provider">
                  <option value="ark">ark</option>
                  <option value="openai">openai</option>
                </select>
              </label>
              <label>Model
                <input type="text" id="vision-model" placeholder="默认 doubao-seed-1-6-vision-250815">
              </label>
            </div>
            <label>图片 URL（多张可换行/逗号分隔）
              <textarea id="vision-url" placeholder="https://..."></textarea>
            </label>
            <label>上传图片
              <input type="file" id="vision-file" accept="image/*" multiple>
            </label>
            <div id="vision-preview" class="vision-preview"></div>
            <div id="vision-paste" class="paste-box" contenteditable="true">
              点击这里后粘贴图片（Ctrl/Cmd+V）
            </div>
            <label>识别 Prompt（可选）
              <textarea id="vision-prompt" placeholder="可选：不填则使用默认识别 prompt"></textarea>
            </label>
          </div>

          <div class="mode-panel" data-mode="garmin">
            <label>日期（默认昨日）
              <input type="date" id="garmin-date">
            </label>
            <div style="font-size: 12px; color: var(--muted);">
              通过 Garmin Connect API 拉取（需设置 GARMIN_EMAIL / GARMIN_PASSWORD）
            </div>
            <label style="display:flex; align-items:center; gap:8px; font-size:12px;">
              <input type="checkbox" id="garmin-update-note"> 写入日记设备数据
            </label>
          </div>

          <div class="mode-panel" data-mode="evening">
            <label>日期
              <input type="date" id="evening-date">
            </label>
            <div style="font-size: 12px; color: var(--muted);">在输入框中写今天的总结。</div>
          </div>

          <div class="mode-panel" data-mode="record">
            <label>日期（默认今天）
              <input type="date" id="record-date">
            </label>
            <div style="font-size: 12px; color: var(--muted);">快速记录，不更新日记。</div>
          </div>

          <div class="input-row">
            <textarea id="chat-input" placeholder="输入内容..."></textarea>
            <button id="chat-send">Send</button>
          </div>
        </div>

        <div class="nav">
          <span><strong>Chat</strong></span>
          <span>Sync</span>
          <span>Timeline</span>
          <span>Settings</span>
        </div>
      </div>
    </section>
  </main>

  <script>
    console.log("UI script loaded");
    const chatFeed = document.getElementById('chat-feed');
    const morningDateInput = document.getElementById('morning-date');
    const eveningDateInput = document.getElementById('evening-date');
    const visionDateInput = document.getElementById('vision-date');
    const garminDateInput = document.getElementById('garmin-date');
    const recordDateInput = document.getElementById('record-date');
    const tokenInput = document.getElementById('ui-token');
    const tokenStatus = document.getElementById('token-status');
    const now = new Date();
    const today = now.toISOString().slice(0,10);
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const yesterdayStr = yesterday.toISOString().slice(0,10);
    morningDateInput.value = today;
    eveningDateInput.value = today;
    visionDateInput.value = yesterdayStr;
    garminDateInput.value = yesterdayStr;
    recordDateInput.value = today;

    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('chat-send');
    const modeButtons = Array.from(document.querySelectorAll('.mode-chip'));
    const modePanels = Array.from(document.querySelectorAll('.mode-panel'));
    let activeMode = 'morning';

    function appendBubble(role, label, content, asPre = false) {
      const bubble = document.createElement('div');
      bubble.className = `bubble ${role}`;
      if (label) {
        const meta = document.createElement('div');
        meta.className = 'bubble-meta';
        meta.textContent = label;
        bubble.appendChild(meta);
      }
      if (role === 'system') {
        bubble.textContent = content;
      } else if (asPre) {
        const pre = document.createElement('pre');
        pre.textContent = content;
        bubble.appendChild(pre);
      } else {
        const text = document.createElement('div');
        text.className = 'bubble-text';
        text.textContent = content;
        bubble.appendChild(text);
      }
      chatFeed.appendChild(bubble);
      chatFeed.scrollTop = chatFeed.scrollHeight;
    }

    function showError(label, err) {
      console.error(err);
      const msg = err && err.message ? err.message : String(err);
      appendBubble('assistant', label || '错误', msg, false);
    }

    function setMode(mode) {
      activeMode = mode;
      modeButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
      });
      modePanels.forEach(panel => {
        panel.classList.toggle('active', panel.dataset.mode === mode);
      });
      switch (mode) {
        case 'morning':
          chatInput.placeholder = '早间状态 / 今日重点';
          break;
        case 'vision':
          chatInput.placeholder = '可选：补充识别提示';
          break;
        case 'garmin':
          chatInput.placeholder = 'Garmin 同步无需文字';
          break;
        case 'evening':
          chatInput.placeholder = '晚间总结 / 日记内容';
          break;
        case 'record':
          chatInput.placeholder = '快速记录';
          break;
        default:
          chatInput.placeholder = '输入内容...';
      }
    }

    modeButtons.forEach(btn => {
      btn.addEventListener('click', () => setMode(btn.dataset.mode));
    });

    const savedToken = localStorage.getItem('uiToken') || '';
    tokenInput.value = savedToken;
    if (savedToken) {
      tokenStatus.textContent = '已保存';
    }
    const tokenFromQuery = new URLSearchParams(window.location.search).get('token');
    if (tokenFromQuery) {
      localStorage.setItem('uiToken', tokenFromQuery);
      tokenInput.value = tokenFromQuery;
      tokenStatus.textContent = '已保存';
      const cleanUrl = window.location.origin + window.location.pathname;
      window.history.replaceState({}, '', cleanUrl);
    }
    tokenInput.addEventListener('input', () => {
      const token = tokenInput.value.trim();
      if (token) {
        localStorage.setItem('uiToken', token);
        tokenStatus.textContent = '已保存';
      } else {
        localStorage.removeItem('uiToken');
        tokenStatus.textContent = '';
      }
    });

    function getToken() {
      return tokenInput.value.trim() || localStorage.getItem('uiToken') || '';
    }

    function authHeaders() {
      const token = getToken();
      return token ? { 'X-UI-Token': token } : {};
    }

    async function apiPost(path, body) {
      return fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body)
      });
    }

    async function readResponse(resp) {
      const text = await resp.text();
      let data = null;
      try {
        data = JSON.parse(text);
      } catch (err) {
        data = text;
      }
      return { ok: resp.ok, data, raw: text };
    }

    function getVisionInputs() {
      const urlText = document.getElementById('vision-url').value.trim();
      const visionDate = document.getElementById('vision-date').value;
      const fileInput = document.getElementById('vision-file');
      const files = fileInput.files ? Array.from(fileInput.files) : [];
      const pasteBox = document.getElementById('vision-paste');
      const prompt = document.getElementById('vision-prompt').value.trim();
      const provider = document.getElementById('vision-provider').value;
      const model = document.getElementById('vision-model').value.trim();
      let pastedList = [];
      try {
        pastedList = pasteBox.dataset.imageB64List ? JSON.parse(pasteBox.dataset.imageB64List) : [];
      } catch (err) {
        pastedList = [];
        console.error('解析粘贴缓存失败', err);
      }
      const urls = urlText ? urlText.split(/[,\n]+/).map(s => s.trim()).filter(Boolean) : [];
      return { urls, files, pastedList, prompt, provider, model, visionDate };
    }

    function hasVisionInputs(inputs) {
      return inputs.urls.length > 0 || inputs.files.length > 0 || inputs.pastedList.length > 0;
    }

    function describeVisionInputs(inputs, promptOverride) {
      const parts = [];
      if (inputs.urls.length) parts.push(`URL ${inputs.urls.length}`);
      if (inputs.files.length) parts.push(`文件 ${inputs.files.length}`);
      if (inputs.pastedList.length) parts.push(`粘贴 ${inputs.pastedList.length}`);
      const prompt = promptOverride || inputs.prompt;
      if (prompt) parts.push(`Prompt: ${prompt.slice(0, 80)}`);
      return parts.length ? parts.join(' · ') : '无图片';
    }

    async function sendMorning(textInput) {
      const date = morningDateInput.value;
      const content = textInput ? textInput : '（无文字）';
      appendBubble('user', `Morning · ${date}`, content, false);
      try {
        const resp = await apiPost('/morning', { date, text: textInput, token: getToken() || null });
        const result = await readResponse(resp);
        appendBubble(
          'assistant',
          'Morning result',
          result.ok ? JSON.stringify(result.data, null, 2) : String(result.data),
          true
        );
        return result.ok ? result.data : null;
      } catch (e) {
        showError('Morning error', e);
        return null;
      }
    }

    async function sendEvening(textInput) {
      const date = eveningDateInput.value;
      appendBubble('user', `Evening · ${date}`, textInput, false);
      try {
        const resp = await apiPost('/evening', { date, journal: textInput, token: getToken() || null });
        const result = await readResponse(resp);
        appendBubble(
          'assistant',
          'Evening result',
          result.ok ? JSON.stringify(result.data, null, 2) : String(result.data),
          true
        );
        return result.ok ? result.data : null;
      } catch (e) {
        showError('Evening error', e);
        return null;
      }
    }

    async function sendRecord(textInput) {
      const date = recordDateInput.value;
      appendBubble('user', `Quick note · ${date}`, textInput, false);
      try {
        const resp = await apiPost('/record', { date, text: textInput, token: getToken() || null });
        const result = await readResponse(resp);
        appendBubble(
          'assistant',
          'Record result',
          result.ok ? JSON.stringify(result.data, null, 2) : String(result.data),
          true
        );
        return result.ok ? result.data : null;
      } catch (e) {
        showError('Record error', e);
        return null;
      }
    }

    async function sendGarmin() {
      const date = garminDateInput.value;
      const updateNote = document.getElementById('garmin-update-note').checked;
      appendBubble('user', `Garmin · ${date}`, updateNote ? '同步并写入日记' : '同步', false);
      try {
        const resp = await apiPost('/garmin', {
          date,
          update_note: updateNote,
          token: getToken() || null
        });
        const result = await readResponse(resp);
        appendBubble(
          'assistant',
          'Garmin result',
          result.ok ? JSON.stringify(result.data, null, 2) : String(result.data),
          true
        );
        return result.ok ? result.data : null;
      } catch (e) {
        showError('Garmin error', e);
        return null;
      }
    }

    async function sendVision(requireImages = true, options = {}) {
      try {
        const inputs = getVisionInputs();
        if (!hasVisionInputs(inputs)) {
          if (requireImages) {
            alert('请输入图片 URL 或选择/粘贴图片');
          }
          return null;
        }
        const promptOverride = options.promptOverride || null;
        if (!options.skipUserBubble) {
          appendBubble('user', 'Vision', describeVisionInputs(inputs, promptOverride), false);
        }
        console.log('vision request', { urls: inputs.urls, files: inputs.files.length, pasted: inputs.pastedList.length, provider: inputs.provider, model: inputs.model });
        const image_b64_list = [];
        for (const file of inputs.files) {
          const buffer = await file.arrayBuffer();
          let binary = '';
          const bytes = new Uint8Array(buffer);
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          image_b64_list.push(btoa(binary));
        }
        for (const b64 of inputs.pastedList) {
          image_b64_list.push(b64);
        }
        const resp = await apiPost('/vision', {
          image_urls: inputs.urls.length ? inputs.urls : null,
          image_b64_list: image_b64_list.length ? image_b64_list : null,
          prompt: inputs.prompt || promptOverride || null,
          date: inputs.visionDate || null,
          provider: inputs.provider,
          model: inputs.model,
          token: getToken() || null
        });
        const result = await readResponse(resp);
        appendBubble(
          'assistant',
          'Vision result',
          result.ok ? JSON.stringify(result.data, null, 2) : String(result.data),
          true
        );
        return result.ok ? result.data : null;
      } catch (e) {
        showError('Vision error', e);
        return null;
      }
    }

    const pasteBox = document.getElementById('vision-paste');
    const preview = document.getElementById('vision-preview');

    function addPreviewFromB64(b64) {
      const img = document.createElement('img');
      img.src = 'data:image/jpeg;base64,' + b64;
      img.style.width = '64px';
      img.style.height = '64px';
      img.style.objectFit = 'contain';
      img.style.border = '1px solid #ddd';
      img.style.padding = '2px';
      preview.appendChild(img);
    }

    function pushB64(b64) {
      const list = pasteBox.dataset.imageB64List ? JSON.parse(pasteBox.dataset.imageB64List) : [];
      list.push(b64);
      pasteBox.dataset.imageB64List = JSON.stringify(list);
      pasteBox.innerText = `已粘贴 ${list.length} 张图片，可继续粘贴`;
      addPreviewFromB64(b64);
    }

    pasteBox.addEventListener('paste', async (e) => {
      e.preventDefault();
      const items = e.clipboardData && e.clipboardData.items;
      if (!items) {
        pasteBox.innerText = '粘贴失败：无剪贴板数据';
        return;
      }
      let added = 0;
      for (const item of items) {
        if (item.type && item.type.startsWith('image/')) {
          const blob = item.getAsFile();
          if (!blob) continue;
          const buffer = await blob.arrayBuffer();
          let binary = '';
          const bytes = new Uint8Array(buffer);
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const b64 = btoa(binary);
          pushB64(b64);
          added += 1;
        }
      }
      if (added === 0) {
        pasteBox.innerText = '未检测到图片，请重新粘贴或选择文件';
      }
    });

    document.getElementById('vision-file').addEventListener('change', async (e) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      for (const file of files) {
        const buffer = await file.arrayBuffer();
        let binary = '';
        const bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        addPreviewFromB64(btoa(binary));
      }
    });

    async function handleSend() {
      const text = chatInput.value.trim();
      if (activeMode === 'morning') {
        const visionInputs = getVisionInputs();
        const hasImages = hasVisionInputs(visionInputs);
        if (!text && !hasImages) {
          alert('请输入文字或图片');
          return;
        }
        await sendMorning(text || null);
        if (hasImages) {
          await sendVision(false, { skipUserBubble: true });
        }
      } else if (activeMode === 'vision') {
        await sendVision(true, { promptOverride: text || null });
      } else if (activeMode === 'garmin') {
        await sendGarmin();
      } else if (activeMode === 'evening') {
        if (!text) {
          alert('请输入晚间总结内容');
          return;
        }
        await sendEvening(text);
      } else if (activeMode === 'record') {
        if (!text) {
          alert('请输入记录内容');
          return;
        }
        await sendRecord(text);
      }
      chatInput.value = '';
    }

    sendButton.addEventListener('click', handleSend);
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSend();
      }
    });

    window.addEventListener('error', (e) => {
      showError('页面错误', e.error || e.message);
    });

    setMode('morning');
  </script>
</body>
</html>
"""


class ChatHandler(BaseHTTPRequestHandler):
    goal_text: Optional[str] = None
    default_provider: str = "openai"
    default_model: Optional[str] = None  # resolved in main
    ui_token: Optional[str] = None
    default_vision_prompt: str = (
        VISION_PROMPT_OVERRIDE
        if VISION_PROMPT_OVERRIDE
        else (
        "你将看到的是我上传的一组截图，可能来自以下来源之一或多个：\n"
        "- 手机的「屏幕使用时间 / 应用使用情况」\n"
        "- 智能手表 App 的「首页 / 睡眠 / 睡眠阶段 / 身体状况」\n\n"
        "截图组合是不确定的：\n"
        "- 可能只有手机截图\n"
        "- 可能只有手表截图\n"
        "- 也可能两者同时存在\n\n"
        "你的任务只有一件事：\n"
        "**从截图中准确识别“真实可见的信息”，并进行结构化输出，不要进行任何分析、解释或评价。**\n\n"
        "====================\n"
        "一、识别规则（非常重要）\n"
        "====================\n"
        "- 只提取截图中明确显示的数据\n"
        "- 不推断、不补全、不做合理猜测\n"
        "- 无法识别或未出现的字段必须填 null\n"
        "- 允许部分结构为空，但 JSON 结构必须完整\n\n"
        "====================\n"
        "二、手机使用信息（若截图中存在）\n"
        "====================\n"
        "请识别以下字段：\n\n"
        "- 统计口径（如：今日 / 昨日）\n"
        "- 屏幕使用总时长\n"
        "- 与前一日的对比变化（若存在）\n"
        "- 应用使用列表（App 名称 + 使用时长）\n"
        "- 解锁次数\n"
        "- 首次解锁时间\n"
        "- 系统显示的使用变化提示（若存在）\n\n"
        "====================\n"
        "三、手表睡眠 & 身体信息（若截图中存在）\n"
        "====================\n"
        "请识别以下字段：\n\n"
        "1. 睡眠\n"
        "- 总睡眠时间\n"
        "- 睡眠评分（若存在）\n"
        "- 睡眠持续时间显示（若存在）\n"
        "- 深睡 / 浅睡 / REM / 清醒 时长\n\n"
        "2. HRV（重点）\n"
        "- HRV 状态\n"
        "- HRV 数值（毫秒）\n"
        "- HRV 7 天平均值（毫秒，若存在）\n\n"
        "3. 心率\n"
        "- 静息心率（bpm）\n"
        "- 心率显示值（首页仪表盘值，若存在）\n\n"
        "4. 呼吸 / 血氧\n"
        "- 脉搏血氧 SpO₂（百分比，若存在）\n"
        "- 呼吸变化指数（若存在）\n\n"
        "5. 身体状态\n"
        "- 不安稳状态次数\n"
        "- 身体电量变化（Body Battery）\n"
        "- 压力值\n\n"
        "====================\n"
        "四、统一结构化输出（必须）\n"
        "====================\n"
        "请将所有识别结果整理为 **一个 JSON 对象**，结构固定如下：\n\n"
        '{\n'
        '  "record_type": "daily_raw_capture",\n'
        '\n'
        '  "phone_usage": {\n'
        '    "day_scope": null,\n'
        '    "screen_time": {\n'
        '      "total": null,\n'
        '      "total_minutes": null,\n'
        '      "delta_vs_previous": null\n'
        "    },\n"
        '    "app_usage": [\n'
        '      { "app": null, "duration": null, "minutes": null }\n'
        "    ],\n"
        '    "unlock": {\n'
        '      "count": null,\n'
        '      "first_unlock_time": null,\n'
        '      "delta_vs_previous": null\n'
        "    },\n"
        '    "system_notes": []\n'
        "  },\n"
        '\n'
        '  "watch_health": {\n'
        '    "day_scope": null,\n'
        '    "pages_detected": [],\n'
        '\n'
        '    "sleep": {\n'
        '      "total": null,\n'
        '      "total_minutes": null,\n'
        '      "score": null,\n'
        '      "duration_display": null,\n'
        '      "stages": {\n'
        '        "deep": { "duration": null, "minutes": null },\n'
        '        "light": { "duration": null, "minutes": null },\n'
        '        "rem": { "duration": null, "minutes": null },\n'
        '        "awake": { "duration": null, "minutes": null }\n'
        "      }\n"
        "    },\n"
        '\n'
        '    "hrv": {\n'
        '      "status": null,\n'
        '      "value_ms": null,\n'
        '      "seven_day_avg_ms": null\n'
        "    },\n"
        '\n'
        '    "heart_rate": {\n'
        '      "resting_bpm": null,\n'
        '      "display_bpm": null\n'
        "    },\n"
        '\n'
        '    "respiration": {\n'
        '      "variation_index": null\n'
        "    },\n"
        '\n'
        '    "spo2": {\n'
        '      "value_percent": null\n'
        "    },\n"
        '\n'
        '    "recovery": {\n'
        '      "restlessness_events": null,\n'
        '      "body_battery_change": null,\n'
        '      "stress_level": null\n'
        "    }\n"
        "  }\n"
        "}\n\n"
        "====================\n"
        "五、严格输出约束\n"
        "====================\n"
        "- 只输出 JSON，不要输出任何其他文字\n"
        "- JSON 字段名、层级、结构必须完全一致\n"
        "- 不允许添加未定义字段\n"
        "- 时间字段需同时提供「hh:mm」与「分钟」\n"
        )
    )

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        # Server-side log for debugging
        sys.stderr.write(f"[{self.log_date_time_string()}] {status} {payload}\n")

    def _extract_token(self, payload: Optional[dict] = None) -> Optional[str]:
        header_token = self.headers.get("X-UI-Token")
        if header_token:
            return header_token.strip()
        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            return auth_header.split(" ", 1)[1].strip()
        if payload and isinstance(payload, dict):
            value = payload.get("token")
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            query = urlparse(self.path).query
            params = parse_qs(query)
            token_param = params.get("token", [])
            if token_param:
                return token_param[0].strip()
        except Exception:
            pass
        return None

    def _authorized(self, payload: Optional[dict] = None) -> bool:
        if not self.ui_token:
            return True
        token = self._extract_token(payload)
        return bool(token) and token == self.ui_token

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self.send_error(404, "Not Found")
            return
        if not self._authorized():
            body = (
                "<html><body><h3>Unauthorized</h3>"
                "<p>请在 URL 里添加 token，例如：</p>"
                "<pre>http://IP:8000/?token=你的口令</pre>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(401)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception:
            self._json_response(400, {"error": "invalid json"})
            return
        if not self._authorized(payload):
            self._json_response(401, {"error": "unauthorized"})
            return

        if parsed.path == "/chat":
            self._handle_chat(payload)
        elif parsed.path == "/morning":
            self._handle_morning(payload)
        elif parsed.path == "/evening":
            self._handle_evening(payload)
        elif parsed.path == "/record":
            self._handle_record(payload)
        elif parsed.path == "/vision":
            self._handle_vision(payload)
        elif parsed.path == "/garmin":
            self._handle_garmin(payload)
        else:
            self.send_error(404, "Not Found")

    def _handle_chat(self, payload: dict) -> None:
        message = payload.get("message")
        date_str = payload.get("date")
        provider = payload.get("provider") or self.default_provider
        model = payload.get("model") or (chat_bot.DEFAULT_ARK_MODEL if provider == "ark" else chat_bot.DEFAULT_MODEL)
        if not message:
            self._json_response(400, {"error": "缺少 message"})
            return
        try:
            date = dt.date.fromisoformat(date_str) if date_str else dt.date.today()
        except Exception:
            self._json_response(400, {"error": "日期格式应为 YYYY-MM-DD"})
            return

        try:
            client = chat_bot.make_client(provider)
            parsed = chat_bot.classify_message(client, model, message, self.goal_text)
            action = parsed.get("action", "none")
            text_input = parsed.get("text")
            journal = parsed.get("journal")
            images = parsed.get("images", []) or []
            file_path = chat_bot.apply_action(
                action, date, self.goal_text, text_input, journal, images
            )
            self._json_response(
                200,
                {
                    "action": action,
                    "file": str(file_path),
                    "parsed": parsed,
                },
            )
        except Exception as exc:  # pragma: no cover - network errors
            sys.stderr.write(f"[chat_error] provider={provider} model={model} error={exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})

    def _handle_morning(self, payload: dict) -> None:
        date_str = payload.get("date")
        text_input = payload.get("text") or payload.get("note")
        try:
            date = dt.date.fromisoformat(date_str) if date_str else dt.date.today()
        except Exception:
            self._json_response(400, {"error": "日期格式应为 YYYY-MM-DD"})
            return
        try:
            path = manage_day.ensure_daily_file(date)
            manage_day.run_morning(path, self.goal_text, [], text_input=text_input)
            self._json_response(200, {"file": str(path), "action": "morning"})
        except Exception as exc:
            sys.stderr.write(f"[morning_error] {exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})

    def _handle_evening(self, payload: dict) -> None:
        date_str = payload.get("date")
        journal = payload.get("journal")
        if not journal:
            self._json_response(400, {"error": "缺少 journal"})
            return
        try:
            date = dt.date.fromisoformat(date_str) if date_str else dt.date.today()
        except Exception:
            self._json_response(400, {"error": "日期格式应为 YYYY-MM-DD"})
            return
        try:
            path = manage_day.ensure_daily_file(date)
            manage_day.run_evening(path, journal)
            self._json_response(200, {"file": str(path), "action": "evening"})
        except Exception as exc:
            sys.stderr.write(f"[evening_error] {exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})

    def _handle_record(self, payload: dict) -> None:
        text = payload.get("text")
        date_str = payload.get("date")
        if not text:
            self._json_response(400, {"error": "缺少 text"})
            return
        try:
            date = dt.date.fromisoformat(date_str) if date_str else dt.date.today()
        except Exception:
            self._json_response(400, {"error": "日期格式应为 YYYY-MM-DD"})
            return
        try:
            path = record_store.add_record(date, text, source="ui")
            self._json_response(200, {"saved": str(path), "action": "record"})
        except Exception as exc:
            sys.stderr.write(f"[record_error] {exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})

    def _handle_garmin(self, payload: dict) -> None:
        date_str = payload.get("date")
        update_note = bool(payload.get("update_note"))
        if date_str and _parse_date(date_str) is None:
            self._json_response(400, {"error": "日期格式应为 YYYY-MM-DD"})
            return
        try:
            target_date = _parse_date(date_str) or (dt.date.today() - dt.timedelta(days=1))
            raw = _fetch_garmin_payload(target_date)
        except Exception as exc:
            sys.stderr.write(f"[garmin_fetch_error] {exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})
            return

        try:
            out_dir = GARMIN_DATA_ROOT / target_date.strftime("%Y%m%d")
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = dt.datetime.now().strftime("%H%M%S")
            file_name = f"garmin_{target_date.isoformat()}_{ts}.json"
            saved_path = out_dir / file_name
            saved_path.write_text(json.dumps(raw, ensure_ascii=True, indent=2), encoding="utf-8")

            state = state_recorder.build_daily_state_from_garmin(target_date, raw)
            existing = state_recorder.load_daily_state(target_date)
            merged = state_recorder.merge_daily_state(existing, state)
            state_path = state_recorder.save_daily_state(merged)

            daily_path = None
            if update_note:
                daily_path = manage_day.ensure_daily_file(target_date)
                manage_day.update_device_data(daily_path, merged.get("normalized") or {})

            self._json_response(
                200,
                {
                    "action": "garmin",
                    "date": target_date.isoformat(),
                    "saved": str(saved_path),
                    "state_saved": str(state_path),
                    "daily_updated": str(daily_path) if daily_path else None,
                },
            )
        except Exception as exc:
            sys.stderr.write(f"[garmin_error] {exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})

    def _handle_vision(self, payload: dict) -> None:
        image_urls = payload.get("image_urls") or []
        image_b64_list = payload.get("image_b64_list") or []
        if not image_urls and not image_b64_list:
            self._json_response(400, {"error": "缺少 image_urls 或 image_b64_list"})
            return
        prompt_override = payload.get("prompt")
        prompt = prompt_override or self.default_vision_prompt
        if prompt_override:
            prompt_source = "payload"
            prompt_path = None
            prompt_version = "payload"
        elif VISION_PROMPT_OVERRIDE:
            prompt_source = "file"
            prompt_path = str(VISION_PROMPT_PATH)
            prompt_version = VISION_PROMPT_PATH.stem
        else:
            prompt_source = "builtin"
            prompt_path = None
            prompt_version = "builtin"
        provider = payload.get("provider") or "ark"
        model = payload.get("model") or chat_bot.DEFAULT_VISION_MODEL
        date_str = payload.get("date")
        try:
            if date_str:
                capture_date = dt.date.fromisoformat(date_str)
            else:
                capture_date = dt.date.today() - dt.timedelta(days=1)
        except Exception:
            self._json_response(400, {"error": "日期格式应为 YYYY-MM-DD"})
            return
        try:
            client = chat_bot.make_client(provider)
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            data_urls = []
            if image_b64_list:
                for image_b64 in image_b64_list:
                    try:
                        base64.b64decode(image_b64, validate=True)
                    except Exception:
                        self._json_response(400, {"error": "image_b64_list 含无效 base64"})
                        return
                    data_urls.append(f"data:image/jpeg;base64,{image_b64}")
            all_urls = data_urls + image_urls
            sys.stderr.write(f"[vision_request] provider={provider} model={model} urls={len(all_urls)} b64={len(image_b64_list)}\n")
            text = chat_bot.vision_describe_multi(client, model, all_urls, prompt)
            saved_imgs = save_images_from_base64(image_b64_list, ts)
            saved_path = save_vision_result(
                provider=provider,
                model=model,
                capture_date=capture_date,
                prompt=prompt,
                urls=all_urls,
                result_text=text,
                prompt_source=prompt_source,
                prompt_path=prompt_path,
                prompt_version=prompt_version,
            )
            status_path = None
            state_path = None
            daily_path = None
            try:
                result_data = json.loads(text)
                state = state_recorder.build_daily_state(capture_date, vision_result=result_data)
                existing = state_recorder.load_daily_state(capture_date)
                merged = state_recorder.merge_daily_state(existing, state)
                state_path = state_recorder.save_daily_state(merged)
                daily_path = manage_day.ensure_daily_file(capture_date)
                manage_day.update_device_data(daily_path, merged.get("normalized") or {})
                if ALLOW_STATUS_WRITE:
                    status_path = update_month_status(capture_date, result_data)
            except Exception as exc:
                sys.stderr.write(f"[status_update_error] {exc}\n")
            sys.stderr.write(
                "[vision_saved] raw=%s state=%s daily=%s status=%s\n"
                % (
                    saved_path,
                    state_path if state_path else "-",
                    daily_path if daily_path else "-",
                    status_path if status_path else "-",
                )
            )
            self._json_response(
                200,
                {
                    "vision": text,
                    "provider": provider,
                    "model": model,
                    "capture_date": capture_date.isoformat(),
                    "saved": str(saved_path),
                    "status_updated": str(status_path) if status_path else None,
                    "state_saved": str(state_path) if state_path else None,
                    "daily_updated": str(daily_path) if daily_path else None,
                    "images_saved": [str(p) for p in saved_imgs],
                    "image_urls": image_urls,
                },
            )
        except Exception as exc:  # pragma: no cover
            sys.stderr.write(f"[vision_error] provider={provider} model={model} error={exc}\n")
            sys.stderr.write(traceback.format_exc() + "\n")
            self._json_response(500, {"error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:  # quieter logging
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Web UI for GPT-5 daily helper.")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址，局域网访问建议 0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", help="可选：访问口令")
    parser.add_argument("--goal-file", type=Path, help="可选：目标文本，提供给 GPT 参考")
    return parser.parse_args(argv)


def save_vision_result(
    provider: str,
    model: str,
    capture_date: Optional[dt.date],
    prompt: str,
    urls: list[str],
    result_text: str,
    prompt_source: Optional[str] = None,
    prompt_path: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> Path:
    """Save vision result to disk with a structured filename."""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_")
    filename = f"vision_{ts}_{provider}_{safe_model}.json"
    path = RESULT_DIR / filename
    payload = {
        "provider": provider,
        "model": model,
        "timestamp": ts,
        "capture_date": capture_date.isoformat() if capture_date else None,
        "prompt": prompt,
        "prompt_source": prompt_source,
        "prompt_path": prompt_path,
        "prompt_version": prompt_version,
        "images": urls,
        "result": None,
        "raw": result_text,
    }
    try:
        payload["result"] = json.loads(result_text)
    except Exception:
        payload["result"] = None
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _safe_get(obj: dict, *keys, default=None):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def _join_notes(*parts: Optional[str]) -> str:
    items = [p for p in parts if p]
    return "；".join(items) if items else "-"


def _format_minutes(minutes: Optional[int]) -> Optional[str]:
    if minutes is None:
        return None
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


def _format_app_usage(app_usage: Optional[list]) -> str:
    if not isinstance(app_usage, list) or not app_usage:
        return "-"
    parts = []
    for entry in app_usage:
        if not isinstance(entry, dict):
            continue
        app = entry.get("app")
        duration = entry.get("duration")
        minutes = entry.get("minutes")
        if not duration and minutes is not None:
            duration = _format_minutes(minutes)
        if app and duration:
            parts.append(f"{app} {duration}")
        elif app:
            parts.append(app)
        elif duration:
            parts.append(duration)
    return " / ".join(parts) if parts else "-"


def _build_sleep_text(sleep: dict) -> str:
    total = sleep.get("total")
    total_minutes = sleep.get("total_minutes")
    score = sleep.get("score")
    stages = sleep.get("stages") or {}
    deep = _safe_get(stages, "deep", "duration")
    light = _safe_get(stages, "light", "duration")
    rem = _safe_get(stages, "rem", "duration")
    awake = _safe_get(stages, "awake", "duration")

    if not total and total_minutes is not None:
        total = _format_minutes(total_minutes)
    if not total:
        total = "-"
    stage_bits = []
    if deep:
        stage_bits.append(f"深{deep}")
    if light:
        stage_bits.append(f"浅{light}")
    if rem:
        stage_bits.append(f"REM{rem}")
    if awake:
        stage_bits.append(f"醒{awake}")
    stage_str = "/".join(stage_bits) if stage_bits else "-"
    score_str = f"S{score}" if score is not None else "-"
    return f"{total} ({stage_str}) {score_str}"


def _build_row_from_result(date_str: str, result: dict) -> str:
    phone = result.get("phone_usage") or {}
    watch = result.get("watch_health") or {}
    sleep = watch.get("sleep") or {}

    screen_total = _safe_get(phone, "screen_time", "total")
    top_apps = _format_app_usage(phone.get("app_usage"))
    unlock_count = _safe_get(phone, "unlock", "count")
    screen_delta = _safe_get(phone, "screen_time", "delta_vs_previous")
    unlock_delta = _safe_get(phone, "unlock", "delta_vs_previous")
    body_battery = _safe_get(watch, "recovery", "body_battery_change")

    hrv_value = _safe_get(watch, "hrv", "value_ms")
    hrv_status = _safe_get(watch, "hrv", "status")
    hrv_text = f"{hrv_value} ({hrv_status})" if hrv_value is not None or hrv_status else "-"

    row = [
        date_str,
        _build_sleep_text(sleep),
        hrv_text,
        str(_safe_get(watch, "heart_rate", "resting_bpm", default="-")),
        str(_safe_get(watch, "spo2", "value_percent", default="-")),
        str(_safe_get(watch, "recovery", "stress_level", default="-")),
        screen_total or "-",
        top_apps,
        str(unlock_count if unlock_count is not None else "-"),
        _join_notes(screen_delta, unlock_delta, f"电量{body_battery}" if body_battery else None),
    ]
    return "| " + " | ".join(row) + " |"


def _create_status_file(path: Path, month_str: str) -> None:
    if STATUS_TEMPLATE.exists():
        text = STATUS_TEMPLATE.read_text(encoding="utf-8")
        text = text.replace('<% tp.date.now("YYYY-MM") %>', month_str)
    else:
        text = f"---\njournal: month_status\nmonth: {month_str}\n---\n\n# 本月状态汇总\n"
    path.write_text(text, encoding="utf-8")


def _update_week_table(text: str, week_idx: int, date_str: str, row_line: str) -> str:
    header = f"## Week {week_idx}"
    if header not in text:
        return text
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        return text
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## Week "):
            end = j
            break
    section = lines[start:end]
    table_start = None
    for i, line in enumerate(section):
        if line.strip().startswith("| 日期 |"):
            table_start = i
            break
    if table_start is None:
        return text
    table_lines = section[table_start:]
    # Find rows in the table block
    for idx, row in enumerate(table_lines):
        if row.strip().startswith("|") and date_str in row:
            table_lines[idx] = row_line
            section[table_start:] = table_lines
            lines[start:end] = section
            return "\n".join(lines)
    for idx, row in enumerate(table_lines):
        if row.strip().startswith("|") and row.count("|") > 2:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if cells and cells[0] == "":
                table_lines[idx] = row_line
                section[table_start:] = table_lines
                lines[start:end] = section
                return "\n".join(lines)
    # Append row before next blank or end of table
    insert_at = table_start + len(table_lines)
    for idx, row in enumerate(table_lines):
        if row.strip() == "" or not row.strip().startswith("|"):
            insert_at = table_start + idx
            break
    section.insert(insert_at, row_line)
    lines[start:end] = section
    return "\n".join(lines)


def update_month_status(date: dt.date, result: dict) -> Optional[Path]:
    status_dir = VAULT_ROOT / "diary" / str(date.year) / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    month_str = date.strftime("%Y-%m")
    status_path = status_dir / f"{month_str}-status.md"
    if not status_path.exists():
        _create_status_file(status_path, month_str)
    text = status_path.read_text(encoding="utf-8")
    row_line = _build_row_from_result(date.strftime("%Y-%m-%d"), result)
    week_idx = (date.day - 1) // 7 + 1
    try:
        import calendar

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(date.year, date.month)
        for idx, week in enumerate(weeks, start=1):
            if date.day in week:
                week_idx = idx
                break
    except Exception:
        pass
    updated = _update_week_table(text, week_idx, date.strftime("%Y-%m-%d"), row_line)
    status_path.write_text(updated, encoding="utf-8")
    return status_path


def save_images_from_base64(b64_list: list[str], ts: str) -> list[Path]:
    """Decode base64 images, save as JPG, resize longest edge to 448 using sips (macOS)."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for idx, b64 in enumerate(b64_list):
        try:
            data = base64.b64decode(b64)
        except Exception:
            continue
        fname = f"img_{ts}_{idx}.jpg"
        out_path = IMAGE_DIR / fname
        try:
            out_path.write_bytes(data)
            # resize longest edge to 448; sips returns non-zero on failure
            subprocess.run(
                ["sips", "-Z", "448", str(out_path), "-o", str(out_path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            saved.append(out_path)
        except Exception:
            continue
    return saved


def _local_ipv4_addresses() -> list[str]:
    addresses = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            addr = info[4][0]
            if not addr.startswith("127."):
                addresses.add(addr)
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for addr in socket.gethostbyname_ex(hostname)[2]:
            if not addr.startswith("127."):
                addresses.add(addr)
    except Exception:
        pass
    return sorted(addresses)


def main(argv=None) -> int:
    args = parse_args(argv or [])
    handler_cls = ChatHandler
    handler_cls.goal_text = chat_bot.read_goal_text(args.goal_file)
    token = args.token
    if not token:
        token = os.environ.get("UI_TOKEN")
    if not token:
        cfg_token = CONFIG.get("ui_token")
        if isinstance(cfg_token, str) and cfg_token.strip():
            token = cfg_token.strip()
    handler_cls.ui_token = token
    server = HTTPServer((args.host, args.port), handler_cls)
    print(f"本机访问: http://localhost:{args.port}")
    if args.host in {"127.0.0.1", "localhost"}:
        print("提示：当前仅本机可访问，局域网请使用 --host 0.0.0.0")
    else:
        ips = _local_ipv4_addresses()
        if ips:
            for ip in ips:
                print(f"局域网访问: http://{ip}:{args.port}")
        else:
            print(f"局域网访问：请使用本机 IP，例如 http://<本机IP>:{args.port}")
    if token:
        print("访问口令已启用（UI Token）")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

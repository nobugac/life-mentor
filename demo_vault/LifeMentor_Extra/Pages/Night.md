---
lm_page: night
did: ""
reason: ""
mood: ""
drain: ""
win: ""
deep: ""
---

# Night 🌙

<div class="subline">Evening review (did you? + why?) + Reflection (follow-up).</div>

```dataviewjs
const API_BASE = "http://127.0.0.1:8010";
const today = window.moment ? window.moment().format("YYYY-MM-DD") : new Date().toISOString().slice(0, 10);
const REVIEW_KEY = "lm_night_review_" + today;
const REFLECTION_KEY = "lm_night_reflection_" + today;

function _sanitize(s) { return (s || "").replace(/[\u4e00-\u9fff\u3400-\u4dbf]+/g, "").replace(/\s{2,}/g, " ").trim(); }

// Load state from localStorage
let savedReview = null;
let savedReflection = null;
try {
  const r = localStorage.getItem(REVIEW_KEY);
  if (r) savedReview = JSON.parse(r);
  const f = localStorage.getItem(REFLECTION_KEY);
  if (f) savedReflection = JSON.parse(f);
} catch (e) {}

// Status
let didIt = savedReview?.didIt ?? null;
let skipReason = savedReview?.reason ?? null;
let mood = savedReflection?.mood ?? "good";

const grid = dv.container.createEl("div", { cls: "grid2" });
grid.style.display = "grid";
grid.style.gridTemplateColumns = "repeat(2, minmax(0, 1fr))";
grid.style.gap = "18px";
grid.style.alignItems = "start";
grid.style.width = "100%";

// Left card: Evening Review
const leftCard = grid.createEl("div", { cls: "card" });
const leftHead = leftCard.createEl("div", { cls: "head" });
leftHead.createEl("div", { cls: "label", text: "🌙 Evening Review (1 min)" });
leftHead.createEl("span", { cls: "badge amber", text: "quick" });

leftCard.createEl("div", { cls: "muted", text: "🧩 Did you do today's practice?" });
const didChips = leftCard.createEl("div", { cls: "chips" });
const yesChip = didChips.createEl("div", { cls: "chip active", text: "✅ Yes" });
const noChip = didChips.createEl("div", { cls: "chip", text: "❌ No" });

yesChip.addEventListener("click", () => {
  didIt = true;
  yesChip.classList.add("active");
  noChip.classList.remove("active");
});
noChip.addEventListener("click", () => {
  didIt = false;
  noChip.classList.add("active");
  yesChip.classList.remove("active");
});

leftCard.createEl("div", { cls: "hr" });
leftCard.createEl("div", { cls: "muted", text: "If no — why? (optional)" });
const reasonChips = leftCard.createEl("div", { cls: "chips" });
const reasons = ["Forgot", "Too hard", "Not important", "Bad timing"];
reasons.forEach(r => {
  const chip = reasonChips.createEl("div", { cls: "chip", text: r });
  chip.addEventListener("click", () => {
    reasonChips.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    skipReason = r;
  });
});

// If review already saved, show status
if (savedReview) {
  const statusDiv = leftCard.createEl("div");
  statusDiv.style.cssText = "margin-top:12px;padding:8px 12px;border-radius:8px;font-size:14px;background:rgba(34,197,94,.1);color:#16a34a;";
  statusDiv.innerText = savedReview.didIt ? "✅ Recorded: Done" : "📝 Recorded: " + (savedReview.reason || "Not done");
}

const leftBtnrow = leftCard.createEl("div", { cls: "btnrow" });

if (!savedReview) {
  const saveBtn = leftBtnrow.createEl("button", { cls: "btn ghost", text: "Save review" });
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    saveBtn.innerText = "Saving...";
    try {
      await fetch(`${API_BASE}/suggestion/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: today,
          action: didIt ? "adopt" : "ignore",
          text: skipReason || (didIt ? "Done" : "Not done"),
          type: "micro_review",
        }),
      });
      localStorage.setItem(REVIEW_KEY, JSON.stringify({ didIt, reason: skipReason }));
      saveBtn.innerText = "Saved ✓";
    } catch (e) {
      saveBtn.innerText = "Save failed";
    }
  });
}

const homeLink = leftBtnrow.createEl("a", {
  cls: "btn ghost internal-link",
  text: "Back to Home",
  href: "LifeMentor_Extra/Home",
});
homeLink.setAttribute("data-href", "LifeMentor_Extra/Home");

// Right card: Night Reflection
const rightCard = grid.createEl("div", { cls: "card" });
const rightHead = rightCard.createEl("div", { cls: "head" });
rightHead.createEl("div", { cls: "label", text: "📝 Night Reflection (30s)" });
rightHead.createEl("span", { cls: "badge", text: "deep" });

if (!savedReflection) {
  rightCard.createEl("div", { cls: "muted", text: "Today's mood" });
  const moodChips = rightCard.createEl("div", { cls: "chips" });
  const moods = [
    { text: "🙂 Good", value: "good" },
    { text: "😐 OK", value: "ok" },
    { text: "🙁 Not great", value: "not_great" },
  ];
  moods.forEach((m, i) => {
    const chip = moodChips.createEl("div", { cls: i === 0 ? "chip active" : "chip", text: m.text });
    chip.addEventListener("click", () => {
      moodChips.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      mood = m.value;
    });
  });

  rightCard.createEl("div", { cls: "hr" });
  rightCard.createEl("div", { cls: "muted", text: "Follow-up question" });
  const questionDiv = rightCard.createEl("div", { cls: "text", text: "What's the one thing most likely to throw off your rhythm tonight?" });
  questionDiv.style.marginTop = "6px";

  var textarea = rightCard.createEl("textarea", { cls: "textarea" });
  textarea.style.minHeight = "140px";
  textarea.style.marginTop = "10px";
  textarea.placeholder = "Go a bit deeper: why? / what do you want to do tomorrow…";
}

rightCard.createEl("div", { cls: "hr" });
rightCard.createEl("div", { cls: "muted", text: "Mirror" });
const mirrorDiv = rightCard.createEl("div", { cls: "text", text: savedReflection?.mirror || "One step at a time — don't let reflection become a chore." });
mirrorDiv.style.marginTop = "6px";

// If reflection already submitted, show status
if (savedReflection) {
  // Show selected mood
  const moodMap = { "good": "🙂 Good", "ok": "😐 OK", "not_great": "🙁 Not great" };
  const moodLabel = rightCard.createEl("div");
  moodLabel.style.cssText = "margin-bottom:12px;padding:8px 14px;border-radius:20px;background:#f3f4f6;display:inline-block;font-size:14px;";
  moodLabel.innerText = "Today's mood: " + (moodMap[savedReflection.mood] || savedReflection.mood);

  const resultDiv = rightCard.createEl("div");
  resultDiv.style.cssText = "margin-top:12px;padding:12px;border-radius:10px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);";

  const successTitle = resultDiv.createEl("div");
  successTitle.style.cssText = "font-weight:600;color:#16a34a;margin-bottom:8px;";
  successTitle.innerText = "✅ Reflection submitted";

  if (savedReflection.journal) {
    const journalDiv = resultDiv.createEl("div");
    journalDiv.style.cssText = "font-size:14px;color:#374151;margin-bottom:6px;";
    journalDiv.innerText = "📝 " + savedReflection.journal.slice(0, 80) + (savedReflection.journal.length > 80 ? "..." : "");
  }

  if (savedReflection.summary) {
    const summaryDiv = resultDiv.createEl("div");
    summaryDiv.style.cssText = "font-size:14px;color:#374151;margin-bottom:6px;";
    summaryDiv.innerText = "💭 " + savedReflection.summary;
  }

  if (savedReflection.tomorrowAdvice) {
    const adviceDiv = resultDiv.createEl("div");
    adviceDiv.style.cssText = "font-size:14px;color:#6b7280;";
    adviceDiv.innerText = "💡 Tomorrow's suggestion: " + _sanitize(savedReflection.tomorrowAdvice);
  }
}

// Submit reflection button
const rightBtnrow = rightCard.createEl("div", { cls: "btnrow" });

if (!savedReflection) {
  const submitBtn = rightBtnrow.createEl("button", { cls: "btn ghost", text: "Submit reflection" });
  submitBtn.addEventListener("click", async () => {
    const journal = textarea.value.trim();
    if (!journal) {
      submitBtn.innerText = "Please write your reflection first";
      setTimeout(() => { submitBtn.innerText = "Submit reflection"; }, 1500);
      return;
    }
    submitBtn.disabled = true;
    submitBtn.innerText = "Submitting...";
    try {
      const res = await fetch(`${API_BASE}/evening`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: today,
          journal: journal,
          mood: mood,
          did: didIt,
          reason: skipReason,
        }),
      });
      const data = await res.json();
      const mirror = data.analysis?.reflection || "Keep going — tomorrow will be better";
      const summary = data.analysis?.summary || "";
      const tomorrowAdvice = data.tomorrow_advice || "";
      localStorage.setItem(REFLECTION_KEY, JSON.stringify({ mood, journal, mirror, summary, tomorrowAdvice }));

      // Update UI with result
      submitBtn.innerText = "Submitted ✓";
      mirrorDiv.innerText = mirror;

      // Show success status
      const moodMap = { "good": "🙂 Good", "ok": "😐 OK", "not_great": "🙁 Not great" };
      const moodLabel = rightCard.createEl("div");
      moodLabel.style.cssText = "margin-top:12px;margin-bottom:12px;padding:8px 14px;border-radius:20px;background:#f3f4f6;display:inline-block;font-size:14px;";
      moodLabel.innerText = "Today's mood: " + (moodMap[mood] || mood);

      const resultDiv = rightCard.createEl("div");
      resultDiv.style.cssText = "margin-top:16px;padding:12px;border-radius:10px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);";

      const successTitle = resultDiv.createEl("div");
      successTitle.style.cssText = "font-weight:600;color:#16a34a;margin-bottom:8px;";
      successTitle.innerText = "✅ Reflection saved";

      if (summary) {
        const summaryDiv = resultDiv.createEl("div");
        summaryDiv.style.cssText = "font-size:14px;color:#374151;margin-bottom:6px;";
        summaryDiv.innerText = "📝 " + summary;
      }

      if (tomorrowAdvice) {
        const adviceDiv = resultDiv.createEl("div");
        adviceDiv.style.cssText = "font-size:14px;color:#6b7280;";
        adviceDiv.innerText = "💡 Tomorrow's suggestion: " + _sanitize(tomorrowAdvice);
      }

      // Hide input area
      textarea.style.display = "none";
    } catch (e) {
      submitBtn.innerText = "Submit failed: " + e.message;
    }
  });
}
```

<div class="lm-nav">
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Home" href="LifeMentor_Extra/Home">🏠 Home</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Alignment" href="LifeMentor_Extra/Pages/Alignment">🧭 Alignment</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Today" href="LifeMentor_Extra/Pages/Today">☀️ Today</a>
<a class="internal-link lm-nav-link active" data-href="LifeMentor_Extra/Pages/Night" href="LifeMentor_Extra/Pages/Night">🌙 Night</a>
<a class="internal-link lm-nav-link" data-href="LifeMentor_Extra/Pages/Record_Chat" href="LifeMentor_Extra/Pages/Record_Chat">📝 Record</a>
</div>

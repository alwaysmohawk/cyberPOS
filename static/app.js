// cyberPOS console: tiny progressive enhancement layer. Pages work as server-rendered HTML;
// buttons with data-post call the JSON API and then reload / toast / celebrate.

const WINS = [
  "DONE. THAT COUNTS.", "LOGGED. GOOD WORK, OPERATOR.", "ONE DOWN.", "SMALL WIN. REAL WIN.",
  "THERMAL://SYNC OK", "DONE BEATS PERFECT.", "NICE. KEEP THE CHAIN GOING.",
];

function toast(msg, isErr = false, ms = 2200) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.toggle("err", isErr);
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  let data = {};
  try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ===== data-post buttons =====
document.addEventListener("click", async (ev) => {
  const el = ev.target.closest("[data-post]");
  if (!el) return;
  ev.preventDefault();
  ev.stopPropagation(); // buttons inside <summary> shouldn't toggle the row
  if (el.classList.contains("busy")) return;
  const body = el.dataset.body ? JSON.parse(el.dataset.body) : {};
  const then = el.dataset.then || "";
  el.classList.add("busy");
  if (el.dataset.busy) toast(el.dataset.busy, false, 20000);
  try {
    const data = await post(el.dataset.post, body);
    if (then === "reload") {
      if (data.steps) toast(`Split into ${data.steps.length} steps. Start with the first.`);
      setTimeout(() => location.reload(), data.steps ? 900 : 0);
    } else if (then === "celebrate") {
      toast(WINS[Math.floor(Math.random() * WINS.length)] + (data.streak ? `  ·  ${data.streak}D STREAK` : ""));
      if (navigator.vibrate) navigator.vibrate(60);
      setTimeout(() => location.reload(), 1100);
    } else if (then === "toggle") {
      el.classList.toggle("on", data.on);
      const box = el.querySelector(".box");
      if (box) box.textContent = data.on ? "✓" : "";
      el.classList.remove("busy");
    } else if (then.startsWith("go:")) {
      location.href = then.slice(3);
    } else {
      toast(el.dataset.ok || "Done.");
      el.classList.remove("busy");
    }
  } catch (err) {
    toast(err.message, true, 5000);
    el.classList.remove("busy");
  }
});

// ===== due date pickers on the task board =====
document.addEventListener("change", async (ev) => {
  const el = ev.target;
  if (el.dataset.dueFor) {
    try { await post(el.dataset.dueFor + "/due", { due: el.value }); location.reload(); }
    catch (err) { toast(err.message, true, 5000); }
  }
  if (el.dataset.setting) {
    try {
      await post("/api/settings", { [el.dataset.setting]: el.checked ? "1" : "0" });
      toast("Saved.");
      if (el.dataset.setting === "nag_enabled") document.querySelector(".sub")?.classList.toggle("disabled", !el.checked);
    } catch (err) { toast(err.message, true); }
  }
  if (el.dataset.settingValue) {
    try { await post("/api/settings", { [el.dataset.settingValue]: el.value }); toast("Saved."); }
    catch (err) { toast(err.message, true); }
  }
  if (el.dataset.listToggle !== undefined) {
    const hidden = [...document.querySelectorAll("[data-list-toggle]")]
      .filter((cb) => !cb.checked).map((cb) => cb.dataset.listToggle);
    try { await post("/api/settings", { hidden_lists: hidden }); toast("Saved."); }
    catch (err) { toast(err.message, true); }
  }
});

// ===== forms =====
document.addEventListener("submit", async (ev) => {
  const form = ev.target;
  const fd = Object.fromEntries(new FormData(form).entries());
  let url = null;
  if (form.id === "chore-add") url = "/api/chore/add";
  else if (form.dataset.choreEdit) url = `/api/chore/${form.dataset.choreEdit}/edit`;
  else if (form.dataset.habitAdd) { url = "/api/habit/add"; fd.routine = form.dataset.habitAdd; }
  if (!url) return;
  ev.preventDefault();
  try { await post(url, fd); location.reload(); }
  catch (err) { toast(err.message, true, 5000); }
});

// ===== quick capture =====
(() => {
  const dlg = document.getElementById("capture");
  const open = document.getElementById("capture-open");
  const text = document.getElementById("capture-text");
  if (!dlg || !open) return;
  open.addEventListener("click", () => { dlg.showModal(); text.focus(); });
  document.getElementById("capture-cancel").addEventListener("click", () => dlg.close());
  document.getElementById("capture-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const value = text.value.trim();
    if (!value) return;
    const btn = document.getElementById("capture-save");
    btn.classList.add("busy");
    toast("Capturing…", false, 20000);
    try {
      const { task } = await post("/api/capture", { text: value });
      text.value = "";
      dlg.close();
      const bits = [task.due ? `due ${task.due}` : null, task.priority === 1 ? "HIGH" : null, task.list].filter(Boolean);
      toast(`Captured: ${task.title}${bits.length ? "  ·  " + bits.join(" · ") : ""}`, false, 3500);
      if (["/", "/tasks"].includes(location.pathname)) setTimeout(() => location.reload(), 1500);
    } catch (err) {
      toast(err.message, true, 5000);
    } finally {
      btn.classList.remove("busy");
    }
  });
})();

// ===== note printing =====
document.getElementById("note-print")?.addEventListener("click", async () => {
  const ta = document.getElementById("note-text");
  if (!ta.value.trim()) return toast("Write something first.", true);
  toast("Printing…", false, 20000);
  try { await post("/api/print/note", { text: ta.value }); ta.value = ""; toast("Note printed."); }
  catch (err) { toast(err.message, true, 5000); }
});

// ===== clock + focus timer =====
function tick() {
  const c = document.getElementById("clock");
  if (c) c.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  const card = document.querySelector(".timer[data-ends]");
  const cd = document.getElementById("countdown");
  if (card && cd) {
    const left = Math.round((new Date(card.dataset.ends) - Date.now()) / 1000);
    const a = Math.abs(left);
    const mm = String(Math.floor(a / 60)).padStart(2, "0");
    const ss = String(a % 60).padStart(2, "0");
    cd.textContent = (left < 0 ? "+" : "") + `${mm}:${ss}`;
    cd.classList.toggle("over", left < 0);
  }
}
tick();
setInterval(tick, 1000);

// ===== service worker + push =====
if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

function b64ToBytes(b64) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

document.getElementById("push-enable")?.addEventListener("click", async (ev) => {
  if (!window.isSecureContext || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return toast("Open the https address (cyberpos.fastaf.ca) to enable notifications.", true, 6000);
  }
  try {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return toast("Notifications blocked. Allow them in the browser's site settings.", true, 6000);
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: b64ToBytes(ev.target.dataset.key),
    });
    await post("/api/push/subscribe", sub.toJSON());
    document.getElementById("push-state").textContent = "This phone is subscribed.";
    toast("Notifications on. Try 'Send test'.");
  } catch (err) {
    toast(`Couldn't enable: ${err.message}`, true, 6000);
  }
});

// ===== Google reconnect =====
document.getElementById("reauth-start")?.addEventListener("click", async () => {
  try {
    const { url } = await post("/api/google/reauth/start");
    window.open(url, "_blank");
  } catch (err) { toast(err.message, true, 6000); }
});
document.getElementById("reauth-finish")?.addEventListener("click", async () => {
  const url = document.getElementById("reauth-url").value.trim();
  if (!url) return toast("Paste the localhost address first.", true);
  try {
    const { message } = await post("/api/google/reauth/finish", { url });
    toast(message);
    setTimeout(() => location.reload(), 1200);
  } catch (err) { toast(err.message, true, 8000); }
});

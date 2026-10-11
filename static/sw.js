// cyberPOS service worker: shows pushed nags and handles their action buttons.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (ev) => ev.waitUntil(self.clients.claim()));

self.addEventListener("push", (ev) => {
  let msg = {};
  try { msg = ev.data.json(); } catch (e) { msg = { title: "cyberPOS", body: ev.data ? ev.data.text() : "" }; }
  ev.waitUntil(self.registration.showNotification(msg.title || "cyberPOS", {
    body: msg.body || "",
    tag: msg.tag || undefined,
    renotify: !!msg.tag,
    icon: "/static/icon-192.png",
    badge: "/static/badge-96.png",
    actions: msg.actions || [],
    data: Object.assign({ url: msg.url || "/" }, msg.data || {}),
  }));
});

async function api(path, body) {
  return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
}

self.addEventListener("notificationclick", (ev) => {
  const n = ev.notification;
  const d = n.data || {};
  n.close();
  ev.waitUntil((async () => {
    if (ev.action === "done" && d.task_path) {
      const r = await api(d.task_path + "/done");
      return self.registration.showNotification(r.ok ? "✓ Logged. Nice." : "Couldn't mark it done", {
        body: r.ok ? "Open cyberPOS for the next one." : "Open cyberPOS to retry.", tag: "ack", icon: "/static/icon-192.png",
      });
    }
    if (ev.action === "start" && d.task_path) {
      await api(d.task_path + "/timer", { minutes: 10 });
      return self.registration.showNotification("▶ 10-minute timer started", {
        body: "Just begin. You can stop after.", tag: "ack", icon: "/static/icon-192.png",
      });
    }
    if (ev.action === "more") {
      await api("/api/timer/extend", { minutes: 10 });
      return;
    }
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const w of wins) {
      if ("focus" in w) { await w.navigate(d.url); return w.focus(); }
    }
    return self.clients.openWindow(d.url);
  })());
});

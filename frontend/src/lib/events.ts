// Client usage events: batched and sent only if the visitor accepted the privacy notice.
import { storage } from "./storage";

export type Consent = "all" | "essential" | null;
type ClientEvent = { type: string; page?: string; object_key?: string; payload?: Record<string, unknown> };

const queue: ClientEvent[] = [];
const MAX_QUEUE = 200;
let timer: number | undefined;

export function getConsent(): Consent {
  const v = storage.get("consent");
  return v === "all" || v === "essential" ? v : null;
}

export function setConsent(c: Exclude<Consent, null>) {
  storage.set("consent", c);
  if (c === "all") track("privacy_consent", { payload: { choice: c } });
  else queue.length = 0;
}

export function track(type: string, extra: Omit<ClientEvent, "type"> = {}) {
  if (getConsent() !== "all") return;
  if (queue.length >= MAX_QUEUE) queue.shift();
  queue.push({ type, page: window.location.pathname, ...extra });
  if (timer === undefined) timer = window.setTimeout(flush, 5000);
}

export function flush(useBeacon = false) {
  window.clearTimeout(timer);
  timer = undefined;
  if (!queue.length) return;
  const batch = queue.splice(0, 50);
  const body = JSON.stringify({ events: batch });
  if (useBeacon && navigator.sendBeacon) {
    navigator.sendBeacon("/api/v1/events", new Blob([body], { type: "application/json" }));
  } else {
    void fetch("/api/v1/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      credentials: "same-origin",
      keepalive: true,
    }).catch(() => {
      /* analytics must never break the page */
    });
  }
  if (queue.length) timer = window.setTimeout(flush, 1000);
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") flush(true);
});

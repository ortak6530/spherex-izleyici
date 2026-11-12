// Single WebSocket to /ws with automatic reconnect (exponential backoff 1 s -> 30 s).
// Every feature also works over HTTP; the socket only adds live progress and streaming.

export type WsStatus = "connecting" | "open" | "closed";
type Message = { type: string; [k: string]: unknown };
type Handler = (msg: Message) => void;

class RealtimeClient {
  private ws: WebSocket | null = null;
  private status: WsStatus = "closed";
  private retry = 0;
  private reconnectTimer: number | undefined;
  private pingTimer: number | undefined;
  private statusListeners = new Set<(s: WsStatus) => void>();
  private handlers = new Set<Handler>();
  private topics = new Set<string>();
  private started = false;

  start() {
    if (this.started) return;
    this.started = true;
    this.connect();
    // Reconnect promptly when the tab becomes visible or the network comes back
    window.addEventListener("online", () => this.connectNow());
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && this.status === "closed") this.connectNow();
    });
  }

  private url() {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws`;
  }

  private setStatus(s: WsStatus) {
    this.status = s;
    this.statusListeners.forEach((l) => l(s));
  }

  private connectNow() {
    window.clearTimeout(this.reconnectTimer);
    this.retry = 0;
    this.connect();
  }

  private connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING))
      return;
    this.setStatus("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url());
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.setStatus("open");
      this.topics.forEach((topic) => this.send({ type: "subscribe", topic }));
      window.clearInterval(this.pingTimer);
      // Keeps proxies from closing idle sockets
      this.pingTimer = window.setInterval(() => this.send({ type: "ping" }), 25_000);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as Message;
        this.handlers.forEach((h) => h(msg));
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      window.clearInterval(this.pingTimer);
      this.setStatus("closed");
      this.scheduleReconnect();
    };
    ws.onerror = () => ws.close();
  }

  private scheduleReconnect() {
    window.clearTimeout(this.reconnectTimer);
    const delay = Math.min(30_000, 1000 * 2 ** this.retry) * (0.75 + Math.random() * 0.5);
    this.retry = Math.min(this.retry + 1, 6);
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay);
  }

  send(msg: Message): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  subscribe(topic: string) {
    this.topics.add(topic);
    this.send({ type: "subscribe", topic });
  }

  unsubscribe(topic: string) {
    this.topics.delete(topic);
    this.send({ type: "unsubscribe", topic });
  }

  onMessage(h: Handler): () => void {
    this.handlers.add(h);
    return () => {
      this.handlers.delete(h);
    };
  }

  onStatus(l: (s: WsStatus) => void): () => void {
    this.statusListeners.add(l);
    l(this.status);
    return () => {
      this.statusListeners.delete(l);
    };
  }
}

export const realtime = new RealtimeClient();

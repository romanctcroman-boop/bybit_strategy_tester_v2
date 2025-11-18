type MessageHandler = (msg: any) => void;
type Status = 'idle' | 'connecting' | 'open' | 'closed' | 'error';
type StatusHandler = (status: Status, info?: any) => void;

class WSClient {
  private ws?: WebSocket;
  private handlers: MessageHandler[] = [];
  private statusHandlers: StatusHandler[] = [];
  private url: string;
  private manualClose = false;
  private reconnectTimer?: number;
  private backoffMs = 1000; // start at 1s
  private readonly maxBackoffMs = 15000;

  constructor(url: string) {
    this.url = url;
  }

  private notifyStatus(s: Status, info?: any) {
    this.statusHandlers.forEach((h) => h(s, info));
  }

  private scheduleReconnect() {
    if (this.manualClose) return;
    const delay = this.backoffMs + Math.floor(Math.random() * 300);
     
    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay);
    this.backoffMs = Math.min(this.backoffMs * 1.8, this.maxBackoffMs);
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    this.manualClose = false;
    this.notifyStatus('connecting');
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.backoffMs = 1000; // reset backoff on success
      this.notifyStatus('open');
    };
    this.ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        this.handlers.forEach((h) => h(data));
      } catch (e) {
        this.notifyStatus('error', e);
      }
    };
    this.ws.onerror = (e) => {
      this.notifyStatus('error', e);
    };
    this.ws.onclose = () => {
      this.notifyStatus('closed');
      this.scheduleReconnect();
    };
  }

  onMessage(h: MessageHandler) {
    this.handlers.push(h);
    return () => {
      this.handlers = this.handlers.filter((x) => x !== h);
    };
  }

  onStatus(h: StatusHandler) {
    this.statusHandlers.push(h);
    return () => {
      this.statusHandlers = this.statusHandlers.filter((x) => x !== h);
    };
  }

  close() {
    this.manualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    try {
      this.ws?.close();
    } catch {}
  }
}

export default WSClient;

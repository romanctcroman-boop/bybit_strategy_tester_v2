type MessageHandler = (msg: any) => void;

class WSClient {
  private ws?: WebSocket;
  private handlers: MessageHandler[] = [];
  private url: string;

  constructor(url: string) {
    this.url = url;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    this.ws = new WebSocket(this.url);
    this.ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      this.handlers.forEach((h) => h(data));
    };
  }

  onMessage(h: MessageHandler) {
    this.handlers.push(h);
    return () => {
      this.handlers = this.handlers.filter((x) => x !== h);
    };
  }

  close() {
    this.ws?.close();
  }
}

export default WSClient;

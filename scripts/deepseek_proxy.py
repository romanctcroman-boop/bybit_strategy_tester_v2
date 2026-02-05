    #!/usr/bin/env python3
"""
Прокси для DeepSeek API: добавляет поле model в запросы, если Cursor его не передаёт.

Запуск (из корня проекта):
  set DEEPSEEK_API_KEY=your_key
  python scripts/deepseek_proxy.py

Или: scripts/run_deepseek_proxy.ps1  (подхватит ключ из .env при наличии)

В Cursor → Settings → Models:
  Base URL: http://localhost:5000
  API Key: любое (прокси подставит ключ из DEEPSEEK_API_KEY)
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Подгрузка DEEPSEEK_API_KEY из .env в корне проекта (без внешних зависимостей)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "DEEPSEEK_API_KEY" and value and key not in os.environ:
                os.environ[key] = value
                break

from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("DEEPSEEK_PROXY_PORT", "5000"))
DEEPSEEK_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_DEFAULT_MODEL", "deepseek-coder")


def get_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set DEEPSEEK_API_KEY in environment.")
    return key


def _parse_path(path):
    """Return (is_chat_completions, deployment_from_url)."""
    path = path.split("?")[0].rstrip("/")
    # /v1/chat/completions
    if path == "/v1/chat/completions":
        return True, None
    # /chat/completions
    if path == "/chat/completions":
        return True, None
    # Azure: /openai/deployments/DEPLOYMENT_NAME/chat/completions
    if path.startswith("/openai/deployments/") and path.endswith("/chat/completions"):
        name = path[len("/openai/deployments/") : -len("/chat/completions")].strip("/")
        if name:
            return True, name
    # Любой путь .../chat/completions (на случай нестандартного формата Cursor)
    if path.endswith("/chat/completions"):
        return True, None
    return False, None


class DeepSeekProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[proxy] {args[0]}")

    def do_POST(self):
        is_chat, deployment_from_url = _parse_path(self.path)
        if not is_chat:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"error": {"message": "Invalid JSON", "type": "invalid_request"}}
                ).encode()
            )
            return
        # DeepSeek всегда требует поле "model". Принудительно подставляем из URL, body или по умолчанию.
        model_before = data.get("model") or data.get("deployment")
        chosen = (
            (deployment_from_url and str(deployment_from_url).strip())
            or (data.get("deployment") and str(data.get("deployment", "")).strip())
            or (data.get("model") and str(data.get("model", "")).strip())
            or DEFAULT_MODEL
        )
        data["model"] = chosen
        print(f"[proxy] POST path={self.path.split('?')[0]!r} -> model={chosen!r} (was: {model_before!r})")
        api_key = get_api_key()
        url = f"{DEEPSEEK_BASE}/v1/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "error": {
                            "message": str(e),
                            "type": "proxy_error",
                        }
                    }
                ).encode()
            )

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "data": [
                            {"id": "deepseek-coder", "object": "model"},
                            {"id": "deepseek-chat", "object": "model"},
                        ]
                    }
                ).encode()
            )
            return
        if path == "/" or path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            msg = (
                "DeepSeek proxy OK. Base URL for Cursor: http://localhost:5000\n"
                "GET /v1/models — список моделей.\n"
                "POST /v1/chat/completions — чат (прокси подставит model)."
            )
            try:
                self.wfile.write(msg.encode("utf-8"))
            except (BrokenPipeError, ConnectionAbortedError, OSError):
                pass  # клиент закрыл соединение
            return
        self.send_error(404)


def main():
    try:
        get_api_key()
    except SystemExit as e:
        print("Ошибка:", e, file=sys.stderr)
        print("Задайте DEEPSEEK_API_KEY в .env (скопируйте из .env.example и вставьте ключ с https://platform.deepseek.com)", file=sys.stderr)
        sys.exit(1)
    print("[proxy] DEEPSEEK_API_KEY задан, прокси готов.")
    try:
        server = HTTPServer(("127.0.0.1", PORT), DeepSeekProxyHandler)
    except OSError as e:
        if "10048" in str(e) or "Address already in use" in str(e) or "WinError 10048" in str(e):
            print(f"Порт {PORT} занят. Задайте другой: set DEEPSEEK_PROXY_PORT=5001", file=sys.stderr)
        else:
            print("Ошибка запуска сервера:", e, file=sys.stderr)
        sys.exit(1)
    print(f"DeepSeek proxy: http://127.0.0.1:{PORT}")
    print(f"Cursor: Base URL = http://localhost:{PORT}, API Key = любой")
    print("Модель по умолчанию:", DEFAULT_MODEL)
    print("Остановка: Ctrl+C")
    print("--- Если при отправке сообщения в чате здесь НЕ появляется строка [proxy] POST path=...")
    print("    значит запросы идут не сюда. В Cursor проверьте: агент deepseek-coder должен быть")
    print("    привязан к провайдеру Azure OpenAI с Base URL http://localhost:5000 (не api.deepseek.com).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nПрокси остановлен.")
        server.shutdown()


if __name__ == "__main__":
    main()

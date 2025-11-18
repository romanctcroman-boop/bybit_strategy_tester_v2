"""
Запуск Agent-to-Agent Backend сервера
Простой способ без отдельного окна
"""

import subprocess
import time
import sys

print("=" * 80)
print(" Agent-to-Agent Backend Server")
print("=" * 80)
print()
print("Starting uvicorn on http://127.0.0.1:8000...")
print("WebSocket: ws://localhost:8000/api/v1/agent/ws")
print("API Docs: http://localhost:8000/docs")
print()
print("Press Ctrl+C to stop the server")
print("=" * 80)
print()

try:
    # Запуск uvicorn
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "backend.app:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ])
except KeyboardInterrupt:
    print("\n\nServer stopped by user")
    sys.exit(0)

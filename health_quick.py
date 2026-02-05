"""Quick health check."""

import requests

try:
    r = requests.get("http://localhost:8000/api/v1/health", timeout=5)
    print(f"Server status: {r.status_code}")
except Exception as e:
    print(f"Server DOWN: {e}")

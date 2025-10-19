Deployment artifacts for bybit_strategy_tester_v2

Docker (development / staging)

1. Build and start services (PowerShell):
   docker-compose -f deploy/docker-compose.yml up --build

2. Services:
   - backend: FastAPI app (uvicorn) on port 8000
   - ws_publisher: publisher that writes to Redis Streams
   - redis: Redis server

Systemd (production example)

1. Copy `ws_publisher.service` to `/etc/systemd/system/ws_publisher.service` and adjust WorkingDirectory and ExecStart to your environment.
2. Enable and start:
   sudo systemctl daemon-reload; sudo systemctl enable ws_publisher; sudo systemctl start ws_publisher

Prometheus

- The backend exposes `/metrics` on the FastAPI port (8000) if prometheus_client is installed and enabled in settings.
- The ws_publisher starts an internal metrics HTTP server on port 8001 when prometheus_client is available.

Notes

- These are minimal artifacts for quick deployment and testing. For production use, add proper healthchecks, user permissions, logging to files, secrets management, and TLS.

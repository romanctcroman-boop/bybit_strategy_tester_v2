# Run a reproducible 60s integration test (PowerShell)
param(
    [int]$Duration = 60
)

Write-Host "Stopping existing python processes..."
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "Starting backend (uvicorn)..."
Start-Process -FilePath python -ArgumentList '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000', '--log-level', 'info' -NoNewWindow -RedirectStandardOutput run_backend_out.log -RedirectStandardError run_backend_err.log
Start-Sleep -Seconds 2

Write-Host "Starting fake publisher..."
Start-Process -FilePath python -ArgumentList '-m', 'backend.workers.ws_publisher', '--fake', '--fake-rate', '1.0' -NoNewWindow -RedirectStandardOutput run_pub_out.log -RedirectStandardError run_pub_err.log
Start-Sleep -Seconds 2

Write-Host "Running ws client for $Duration seconds..."
Start-Process -FilePath python -ArgumentList '.\\scripts\\run_ws_60s.py' -NoNewWindow -Wait -RedirectStandardOutput run_client_out.log -RedirectStandardError run_client_err.log

Write-Host "Collecting artifacts: XLEN, metrics..."
python -c "import redis; r=redis.Redis(); print('BTC XLEN', r.xlen('stream:candles:BTCUSDT:1')); print('ETH XLEN', r.xlen('stream:candles:ETHUSDT:1'))" > xlen.txt

Invoke-WebRequest -Uri http://127.0.0.1:8001/ -UseBasicParsing | Select-Object -ExpandProperty Content > pub_metrics.txt
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/live/metrics -UseBasicParsing | Select-Object -ExpandProperty Content > backend_metrics.txt

Write-Host "Done. Artifacts: run_backend_err.log run_pub_err.log run_client_out.log xlen.txt pub_metrics.txt backend_metrics.txt"

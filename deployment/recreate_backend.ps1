# Script to recreate backend container with updated healthcheck
Set-Location "d:\bybit_strategy_tester_v2\deployment"
docker-compose -f docker-compose-prod.yml up -d --build backend
Write-Host "Backend container recreated with new healthcheck endpoint"

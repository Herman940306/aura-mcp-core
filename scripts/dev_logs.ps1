Write-Host "Tailing Docker compose logs (Ctrl+C to stop)..." -ForegroundColor Cyan
Invoke-Expression "docker compose logs -f"

# Start Aura IA ML Backend with GPU support (PowerShell)
# This script ensures proper GPU passthrough on Docker Desktop

Write-Host "🚀 Starting Aura IA ML Backend with GPU..." -ForegroundColor Cyan

# Ensure network exists
docker network create latest_mcp_mcp-network 2>$null

# Stop existing container
docker rm -f aura_ia_ml 2>$null

# Start with GPU support
docker run -d `
    --name aura_ia_ml `
    --gpus all `
    -p 9201:8001 `
    -v "${PWD}/model_artifacts:/app/model_artifacts:ro" `
    -v "${PWD}/logs:/app/logs" `
    -v "${PWD}/data:/app/data" `
    -e GITHUB_TOKEN="$env:GITHUB_TOKEN" `
    -e LLAMA_N_GPU_LAYERS=auto `
    -e EMBEDDING_DEVICE=auto `
    --network latest_mcp_mcp-network `
    --health-cmd="curl -f http://localhost:8001/health || exit 1" `
    --health-interval=20s `
    --health-timeout=5s `
    --health-retries=5 `
    --health-start-period=30s `
    --restart unless-stopped `
    latest_mcp-aura-ia-ml:latest

Write-Host "✅ Container started. Waiting for startup..." -ForegroundColor Green
Start-Sleep -Seconds 10

Write-Host "🔍 Checking GPU support..." -ForegroundColor Yellow
docker exec aura_ia_ml python3.11 -c "from llama_cpp import llama_cpp; print('GPU offload:', llama_cpp.llama_supports_gpu_offload())"

Write-Host ""
Write-Host "📊 Testing inference speed..." -ForegroundColor Yellow
$body = @{message = "What is 2+2?" } | ConvertTo-Json
$start = Get-Date
$response = Invoke-RestMethod -Uri "http://localhost:9201/chat/send" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 60
$elapsed = (Get-Date) - $start
Write-Host "Response: $($response.response)" -ForegroundColor White
Write-Host "⚡ Time: $($elapsed.TotalSeconds) seconds" -ForegroundColor Green

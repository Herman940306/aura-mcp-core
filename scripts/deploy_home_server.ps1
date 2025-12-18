# Home Server Quick Deploy Script (PowerShell)
# Run this on Windows home server to get started in 5 minutes

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Aura IA MCP Home Server Deployment" -ForegroundColor Cyan
Write-Host "  Canonical Architecture (PRD v3.0)" -ForegroundColor Cyan
Write-Host "  Zero Cloud Cost • 100% Local" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow

try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker installed: $dockerVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker not found. Install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Red
    exit 1
}

try {
    $composeVersion = docker compose version
    Write-Host "✅ Docker Compose installed: $composeVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker Compose not found. Update Docker Desktop to latest version" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Check disk space
$drive = (Get-Location).Drive.Name
$disk = Get-PSDrive $drive
$freeGB = [math]::Round($disk.Free / 1GB, 2)
if ($freeGB -lt 50) {
    Write-Host "⚠️  Warning: Only ${freeGB}GB free. Recommended: 50GB+" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}
Write-Host "✅ Disk space: ${freeGB}GB available" -ForegroundColor Green
Write-Host ""

# Check RAM
$totalRAMGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
if ($totalRAMGB -lt 8) {
    Write-Host "⚠️  Warning: Only ${totalRAMGB}GB RAM. Recommended: 8GB+" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}
Write-Host "✅ RAM: ${totalRAMGB}GB total" -ForegroundColor Green
Write-Host ""

# Setup .env file
if (-not (Test-Path ".env")) {
    Write-Host "📝 Setting up environment configuration..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"

    Write-Host ""
    Write-Host "⚠️  IMPORTANT: You need to set your GitHub token!" -ForegroundColor Yellow
    Write-Host "   1. Go to: https://github.com/settings/tokens"
    Write-Host "   2. Create token with 'repo' scope"
    Write-Host "   3. Edit .env and set GITHUB_TOKEN=your_token"
    Write-Host ""
    $openEnv = Read-Host "Open .env now? (Y/n)"
    if ($openEnv -ne "n" -and $openEnv -ne "N") {
        notepad .env
    }

    # Check if token was set
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "GITHUB_TOKEN=your_github_token_here") {
        Write-Host "❌ GitHub token not set. Please edit .env before continuing." -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Environment configured" -ForegroundColor Green
}
else {
    Write-Host "✅ Using existing .env file" -ForegroundColor Green
}
Write-Host ""

# Detect GPU (optional)
try {
    $nvidiaSmi = nvidia-smi --query-gpu=name, memory.total --format=csv, noheader 2>$null
    Write-Host "🎮 NVIDIA GPU detected!" -ForegroundColor Green
    Write-Host $nvidiaSmi
    Write-Host ""
    $enableGPU = Read-Host "Enable GPU acceleration? (Y/n)"
    if ($enableGPU -ne "n" -and $enableGPU -ne "N") {
        (Get-Content ".env") -replace "EMBEDDING_DEVICE=cpu", "EMBEDDING_DEVICE=cuda" | Set-Content ".env"
        (Get-Content ".env") -replace "RERANK_DEVICE=cpu", "RERANK_DEVICE=cuda" | Set-Content ".env"
        # TTS GPU acceleration
        (Get-Content ".env") -replace "TTS_USE_GPU=.*", "TTS_USE_GPU=true" | Set-Content ".env"
        if (-not ((Get-Content ".env") -match "TTS_USE_GPU")) {
            Add-Content ".env" "`nTTS_USE_GPU=true"
        }
        Write-Host "✅ GPU acceleration enabled (Embeddings + Reranking + TTS)" -ForegroundColor Green
    }
}
catch {
    Write-Host "ℹ️  No GPU detected (CPU inference will be used)" -ForegroundColor Gray
    Write-Host "   TTS will use VITS model (10x faster than Tacotron2 on CPU)" -ForegroundColor Gray
}
Write-Host ""

# Choose deployment profile
Write-Host "📊 Choose deployment profile:" -ForegroundColor Yellow
Write-Host "  1) Development  (Fast, minimal resources, Week 1)"
Write-Host "  2) Staging      (Balanced, Week 2-3)"
Write-Host "  3) Production   (Best quality, Week 5+)"
Write-Host ""
$profile = Read-Host "Select profile [1-3] (default: 1)"
if ([string]::IsNullOrWhiteSpace($profile)) { $profile = "1" }

switch ($profile) {
    "1" {
        Write-Host "✅ Using Development profile" -ForegroundColor Green
        (Get-Content ".env") -replace "RERANK_ENABLED=1", "RERANK_ENABLED=0" | Set-Content ".env"
        (Get-Content ".env") -replace "QUERY_EXPANSION_ENABLED=1", "QUERY_EXPANSION_ENABLED=0" | Set-Content ".env"
        (Get-Content ".env") -replace "QDRANT_POOL_SIZE=.*", "QDRANT_POOL_SIZE=1" | Set-Content ".env"
    }
    "2" {
        Write-Host "✅ Using Staging profile" -ForegroundColor Green
        (Get-Content ".env") -replace "RERANK_ENABLED=0", "RERANK_ENABLED=1" | Set-Content ".env"
        (Get-Content ".env") -replace "QUERY_EXPANSION_ENABLED=0", "QUERY_EXPANSION_ENABLED=1" | Set-Content ".env"
        (Get-Content ".env") -replace "EXPANSION_STRATEGY=.*", "EXPANSION_STRATEGY=synonyms" | Set-Content ".env"
        (Get-Content ".env") -replace "QDRANT_POOL_SIZE=.*", "QDRANT_POOL_SIZE=3" | Set-Content ".env"
    }
    "3" {
        Write-Host "✅ Using Production profile" -ForegroundColor Green
        (Get-Content ".env") -replace "EMBEDDING_MODEL=.*all-MiniLM.*", "EMBEDDING_MODEL=all-mpnet-base-v2" | Set-Content ".env"
        (Get-Content ".env") -replace "RERANK_ENABLED=0", "RERANK_ENABLED=1" | Set-Content ".env"
        (Get-Content ".env") -replace "RERANK_MODEL=.*", "RERANK_MODEL=ms-marco-electra-base" | Set-Content ".env"
        (Get-Content ".env") -replace "QUERY_EXPANSION_ENABLED=0", "QUERY_EXPANSION_ENABLED=1" | Set-Content ".env"
        (Get-Content ".env") -replace "EXPANSION_STRATEGY=.*", "EXPANSION_STRATEGY=multi_query" | Set-Content ".env"
        (Get-Content ".env") -replace "QDRANT_POOL_SIZE=.*", "QDRANT_POOL_SIZE=10" | Set-Content ".env"
    }
}
Write-Host ""

# Build and start services
Write-Host "🐳 Building and starting Docker containers..." -ForegroundColor Yellow
Write-Host "   This may take 5-10 minutes on first run (model downloads)"
Write-Host ""

docker compose down 2>$null
docker compose up -d --build

Write-Host ""
Write-Host "⏳ Waiting for services to become healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service health
$maxRetries = 30
$retry = 0
while ($retry -lt $maxRetries) {
    $unhealthy = docker compose ps | Select-String "unhealthy"
    if ($unhealthy) {
        Write-Host "   Services starting... ($($retry+1)/$maxRetries)"
        Start-Sleep -Seconds 5
        $retry++
    }
    else {
        break
    }
}

if ($retry -eq $maxRetries) {
    Write-Host "❌ Services failed to start. Check logs:" -ForegroundColor Red
    Write-Host "   docker compose logs"
    exit 1
}

Write-Host ""
Write-Host "✅ All services healthy!" -ForegroundColor Green
Write-Host ""

# Get server IP
$serverIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*" | Select-Object -First 1).IPAddress
if (-not $serverIP) {
    $serverIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi*" | Select-Object -First 1).IPAddress
}

# Display access information
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  🎉 Deployment Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Local Access (Canonical Ports):" -ForegroundColor Yellow
Write-Host "   Aura IA Gateway:  http://localhost:9200"
Write-Host "   Aura IA ML:       http://localhost:9201/health"
Write-Host "   Aura IA Dashboard: http://localhost:9205"
Write-Host "   Aura IA RAG:      http://localhost:9202"
Write-Host ""
Write-Host "🌐 Network Access (from other devices):" -ForegroundColor Yellow
Write-Host "   Aura IA Gateway:  http://${serverIP}:9200"
Write-Host "   Dashboard:        http://${serverIP}:9205"
Write-Host "   Qdrant:           http://${serverIP}:9202"
Write-Host ""
Write-Host "📊 Useful Commands:" -ForegroundColor Yellow
Write-Host "   View logs:    docker compose logs -f"
Write-Host "   Stop all:     docker compose down"
Write-Host "   Restart:      docker compose restart"
Write-Host "   Status:       docker compose ps"
Write-Host ""
Write-Host "📚 Documentation:" -ForegroundColor Yellow
Write-Host "   Home Server Guide: docs\HOME_SERVER_DEPLOYMENT.md"
Write-Host "   Wave 6 Config:     docs\WAVE6_DEPLOYMENT.md"
Write-Host "   Troubleshooting:   docs\WAVE6_DEPLOYMENT.md#troubleshooting"
Write-Host ""
Write-Host "💰 Total Monthly Cost: `$0 (just electricity!)" -ForegroundColor Green
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Welcome to self-hosted AI! 🏠🤖" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

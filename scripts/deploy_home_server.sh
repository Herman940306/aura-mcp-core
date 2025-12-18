#!/bin/bash
# Home Server Quick Deploy Script
# Run this on your home server to get started in 5 minutes

set -e  # Exit on error

echo "============================================"
echo "  Aura IA MCP Home Server Deployment"
echo "  Canonical Architecture (PRD v3.0)"
echo "  Zero Cloud Cost • 100% Local"
echo "============================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install from: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose not found. Install Docker Compose v2+"
    exit 1
fi

echo "✅ Docker installed: $(docker --version)"
echo "✅ Docker Compose installed: $(docker compose version)"
echo ""

# Check disk space
AVAILABLE_GB=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_GB" -lt 50 ]; then
    echo "⚠️  Warning: Only ${AVAILABLE_GB}GB free. Recommended: 50GB+"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo "✅ Disk space: ${AVAILABLE_GB}GB available"
echo ""

# Check RAM
TOTAL_RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_RAM_GB" -lt 8 ]; then
    echo "⚠️  Warning: Only ${TOTAL_RAM_GB}GB RAM. Recommended: 8GB+"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo "✅ RAM: ${TOTAL_RAM_GB}GB total"
echo ""

# Setup .env file
if [ ! -f .env ]; then
    echo "📝 Setting up environment configuration..."
    cp .env.example .env

    echo ""
    echo "⚠️  IMPORTANT: You need to set your GitHub token!"
    echo "   1. Go to: https://github.com/settings/tokens"
    echo "   2. Create token with 'repo' scope"
    echo "   3. Edit .env and set GITHUB_TOKEN=your_token"
    echo ""
    read -p "Open .env now? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        ${EDITOR:-nano} .env
    fi

    # Check if token was set
    if grep -q "GITHUB_TOKEN=your_github_token_here" .env; then
        echo "❌ GitHub token not set. Please edit .env before continuing."
        exit 1
    fi
    echo "✅ Environment configured"
else
    echo "✅ Using existing .env file"
fi
echo ""

# Detect GPU (optional)
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 NVIDIA GPU detected!"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo ""
    read -p "Enable GPU acceleration? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sed -i 's/EMBEDDING_DEVICE=cpu/EMBEDDING_DEVICE=cuda/' .env
        sed -i 's/RERANK_DEVICE=cpu/RERANK_DEVICE=cuda/' .env
        echo "✅ GPU acceleration enabled in .env"
    fi
else
    echo "ℹ️  No GPU detected (CPU inference will be used)"
fi
echo ""

# Choose deployment profile
echo "📊 Choose deployment profile:"
echo "  1) Development  (Fast, minimal resources, Week 1)"
echo "  2) Staging      (Balanced, Week 2-3)"
echo "  3) Production   (Best quality, Week 5+)"
echo ""
read -p "Select profile [1-3] (default: 1): " PROFILE
PROFILE=${PROFILE:-1}

case $PROFILE in
    1)
        echo "✅ Using Development profile"
        sed -i 's/RERANK_ENABLED=1/RERANK_ENABLED=0/' .env
        sed -i 's/QUERY_EXPANSION_ENABLED=1/QUERY_EXPANSION_ENABLED=0/' .env
        sed -i 's/QDRANT_POOL_SIZE=.*/QDRANT_POOL_SIZE=1/' .env
        ;;
    2)
        echo "✅ Using Staging profile"
        sed -i 's/RERANK_ENABLED=0/RERANK_ENABLED=1/' .env
        sed -i 's/QUERY_EXPANSION_ENABLED=0/QUERY_EXPANSION_ENABLED=1/' .env
        sed -i 's/EXPANSION_STRATEGY=.*/EXPANSION_STRATEGY=synonyms/' .env
        sed -i 's/QDRANT_POOL_SIZE=.*/QDRANT_POOL_SIZE=3/' .env
        ;;
    3)
        echo "✅ Using Production profile"
        sed -i 's/EMBEDDING_MODEL=.*/EMBEDDING_MODEL=all-mpnet-base-v2/' .env
        sed -i 's/RERANK_ENABLED=0/RERANK_ENABLED=1/' .env
        sed -i 's/RERANK_MODEL=.*/RERANK_MODEL=ms-marco-electra-base/' .env
        sed -i 's/QUERY_EXPANSION_ENABLED=0/QUERY_EXPANSION_ENABLED=1/' .env
        sed -i 's/EXPANSION_STRATEGY=.*/EXPANSION_STRATEGY=multi_query/' .env
        sed -i 's/QDRANT_POOL_SIZE=.*/QDRANT_POOL_SIZE=10/' .env
        ;;
esac
echo ""

# Build and start services
echo "🐳 Building and starting Docker containers..."
echo "   This may take 5-10 minutes on first run (model downloads)"
echo ""

docker compose down 2>/dev/null || true
docker compose up -d --build

echo ""
echo "⏳ Waiting for services to become healthy..."
sleep 10

# Check service health
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if docker compose ps | grep -q "unhealthy"; then
        echo "   Services starting... ($((RETRY+1))/$MAX_RETRIES)"
        sleep 5
        RETRY=$((RETRY+1))
    else
        break
    fi
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "❌ Services failed to start. Check logs:"
    echo "   docker compose logs"
    exit 1
fi

echo ""
echo "✅ All services healthy!"
echo ""

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

# Display access information
echo "============================================"
echo "  🎉 Deployment Complete!"
echo "============================================"
echo ""
echo "📍 Local Access (Canonical Ports):"
echo "   Aura IA Gateway:  http://localhost:9200"
echo "   Aura IA ML:       http://localhost:9201/health"
echo "   Aura IA Dashboard: http://localhost:9205"
echo "   Aura IA RAG:      http://localhost:9202"
echo ""
echo "🌐 Network Access (from other devices):"
echo "   Aura IA Gateway:  http://${SERVER_IP}:9200"
echo "   Dashboard:        http://${SERVER_IP}:9205"
echo "   Qdrant:           http://${SERVER_IP}:9202"
echo ""
echo "📊 Useful Commands:"
echo "   View logs:    docker compose logs -f"
echo "   Stop all:     docker compose down"
echo "   Restart:      docker compose restart"
echo "   Status:       docker compose ps"
echo ""
echo "📚 Documentation:"
echo "   Home Server Guide: docs/HOME_SERVER_DEPLOYMENT.md"
echo "   Wave 6 Config:     docs/WAVE6_DEPLOYMENT.md"
echo "   Troubleshooting:   docs/WAVE6_DEPLOYMENT.md#troubleshooting"
echo ""
echo "💰 Total Monthly Cost: \$0 (just electricity!)"
echo ""
echo "============================================"
echo "  Welcome to self-hosted AI! 🏠🤖"
echo "============================================"

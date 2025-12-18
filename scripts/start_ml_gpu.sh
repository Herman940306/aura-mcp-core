#!/bin/bash
# Start Aura IA ML Backend with GPU support
# This script ensures proper GPU passthrough on Docker Desktop

echo "🚀 Starting Aura IA ML Backend with GPU..."

# Stop existing container
docker rm -f aura_ia_ml 2>/dev/null

# Start with GPU support
docker run -d \
    --name aura_ia_ml \
    --gpus all \
    -p 9201:8001 \
    -v "$(pwd)/model_artifacts:/app/model_artifacts:ro" \
    -v "$(pwd)/logs:/app/logs" \
    -v "$(pwd)/data:/app/data" \
    -e GITHUB_TOKEN="${GITHUB_TOKEN:-}" \
    -e LLAMA_N_GPU_LAYERS=auto \
    -e EMBEDDING_DEVICE=auto \
    --network latest_mcp_mcp-network \
    --health-cmd="curl -f http://localhost:8001/health || exit 1" \
    --health-interval=20s \
    --health-timeout=5s \
    --health-retries=5 \
    --health-start-period=30s \
    --restart unless-stopped \
    latest_mcp-aura-ia-ml:latest

echo "✅ Container started. Checking GPU..."
sleep 5
docker exec aura_ia_ml python3.11 -c "from llama_cpp import llama_cpp; print('GPU offload:', llama_cpp.llama_supports_gpu_offload())"

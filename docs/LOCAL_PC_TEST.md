# Local PC Test Deployment Guide

# Test the full stack on your Windows PC (different drive) before deploying to home server

## 🎯 Goal

Run a complete test deployment on your local Windows PC using Docker Desktop to verify everything works before deploying to your home server.

---

## 📋 Prerequisites Check

### 1. Docker Desktop Running

```powershell
# Check Docker is running
docker --version
docker compose version

# Start Docker Desktop if not running
# Look for Docker Desktop icon in system tray
```

### 2. Choose Test Location (Different Drive)

```powershell
# Example: Use D:, E:, or any drive except C:
$TestDrive = "D:"  # Change this to your preferred drive
$TestPath = "$TestDrive\MCP_Test_Deploy"

# Create test directory
New-Item -ItemType Directory -Path $TestPath -Force
Set-Location $TestPath
```

---

## 🚀 Step-by-Step Test Deployment

### Step 1: Clone to Test Location

```powershell
# Clone repository to test drive
cd D:\  # or your chosen drive
git clone https://github.com/yourusername/LATEST_MCP.git MCP_Test_Deploy
cd MCP_Test_Deploy

# Or copy from your current location
# Copy-Item -Path "F:\Kiro_Projects\LATEST_MCP" -Destination "D:\MCP_Test_Deploy" -Recurse
```

### Step 2: Configure for Local Testing

```powershell
# Copy environment template
Copy-Item .env.example .env

# Edit .env with minimal configuration for testing
notepad .env
```

**Minimal .env for testing:**

```env
# Required: Your GitHub token
GITHUB_TOKEN=ghp_your_token_here

# Test Configuration (Development Profile - Fast)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RERANK_ENABLED=0
QUERY_EXPANSION_ENABLED=0
QDRANT_POOL_SIZE=1

# Optional flags
IDE_AGENTS_ULTRA_ENABLED=true
```

### Step 3: Verify Docker Desktop Settings

```powershell
# Check Docker Desktop resources
# Open Docker Desktop → Settings → Resources:
# - CPU: At least 4 cores
# - Memory: At least 4GB (8GB recommended)
# - Disk: At least 50GB free on test drive

# Check WSL 2 backend (if on Windows)
wsl --list --verbose
# Should show "Running" for docker-desktop
```

### Step 4: Pre-Download Models (Optional but Recommended)

This saves time and lets you see progress:

```powershell
# Start Python environment
& .\venv\Scripts\Activate.ps1

# Pre-download embedding model (~80MB)
python -c "from sentence_transformers import SentenceTransformer; print('Downloading...'); m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('Done!')"

# Download NLTK data for query expansion (~10MB)
python -c "import nltk; nltk.download('wordnet'); print('WordNet downloaded!')"

# Deactivate environment
deactivate
```

### Step 5: Start Test Deployment

```powershell
# Clean start (remove any previous test containers)
docker compose down -v

# Build and start all services
docker compose up -d --build

# This will take 5-10 minutes first time:
# - Building images
# - Downloading base images (Python, Qdrant, Nginx)
# - Installing dependencies
# - Starting services
```

### Step 6: Monitor Startup

```powershell
# Watch logs in real-time
docker compose logs -f

# In another terminal, check service status
docker compose ps

# Expected output after ~2 minutes:
# NAME            STATE    STATUS                   PORTS
# mcp_gateway     Up       Up (healthy)             0.0.0.0:9100->8000/tcp
# mcp_ml_backend  Up       Up (healthy)             0.0.0.0:9101->8001/tcp
# mcp_qdrant      Up       Up (healthy)             0.0.0.0:6333->6333/tcp
# mcp_dashboard   Up       Up                       0.0.0.0:9102->80/tcp
```

**Wait for "healthy" status** (might take 2-3 minutes):

```powershell
# Keep checking until all show "healthy"
docker compose ps
```

### Step 7: Test All Services

```powershell
# Test ML Backend
curl http://localhost:9101/health
# Expected: {"status":"healthy","version":"..."}

# Test Qdrant Vector DB
curl http://localhost:6333/healthz
# Expected: {"status":"ok"}

# Test MCP Gateway
curl http://localhost:9100
# Expected: HTML or JSON response

# Open Dashboard in Browser
Start-Process "http://localhost:9102"
```

### Step 8: Run Integration Tests

```powershell
# Activate environment
& .\venv\Scripts\Activate.ps1

# Run Wave 6 tests to verify everything works
pytest tests/test_wave6_retrieval_integration.py -v

# Expected: 5/5 tests passing
# If any fail, check docker compose logs
```

### Step 9: Test Wave 6 Features

Create a quick test script:

```powershell
# Create test_local_deployment.py
@"
from aura_ia_mcp.services.model_gateway.embedding_service import EmbeddingService
from aura_ia_mcp.services.model_gateway.retrieval_pipeline import Retriever, RetrievalConfig
from qdrant_client import QdrantClient

print("🧪 Testing Local Deployment...")

# Test 1: Embedding Service
print("\n1️⃣ Testing Embedding Service...")
embed_service = EmbeddingService(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device="cpu"
)
test_vector = embed_service.encode("test query")
print(f"   ✅ Generated {len(test_vector)}-dim vector")

# Test 2: Qdrant Connection
print("\n2️⃣ Testing Qdrant Connection...")
client = QdrantClient(host="localhost", port=6333)
print(f"   ✅ Connected to Qdrant: {client.get_collections()}")

# Test 3: Create Test Collection
print("\n3️⃣ Creating Test Collection...")
from qdrant_client.models import VectorParams, Distance
try:
    client.delete_collection("test_collection")
except:
    pass

client.create_collection(
    collection_name="test_collection",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
print("   ✅ Test collection created")

# Test 4: Insert Test Data
print("\n4️⃣ Inserting Test Documents...")
from qdrant_client.models import PointStruct
points = [
    PointStruct(
        id=1,
        vector=embed_service.encode("machine learning tutorial"),
        payload={"text": "machine learning tutorial"}
    ),
    PointStruct(
        id=2,
        vector=embed_service.encode("python programming guide"),
        payload={"text": "python programming guide"}
    ),
]
client.upsert(collection_name="test_collection", points=points)
print("   ✅ 2 documents inserted")

# Test 5: Retrieval
print("\n5️⃣ Testing Retrieval...")
config = RetrievalConfig(collection="test_collection", top_k=2)
retriever = Retriever(client=client, embed_fn=embed_service, cfg=config)
results = retriever.retrieve("machine learning")
print(f"   ✅ Retrieved {len(results)} results:")
for r in results:
    print(f"      - {r['text']} (score: {r['score']:.3f})")

print("\n🎉 All tests passed! Deployment working correctly.")
print("\n📊 System Status:")
print(f"   • Embeddings: Working (384-dim)")
print(f"   • Qdrant: Connected and operational")
print(f"   • Retrieval: Functional")
print(f"   • Total deployment size: ~200MB models + containers")

# Cleanup
client.delete_collection("test_collection")
print("\n🧹 Cleaned up test collection")
"@ | Out-File -FilePath test_local_deployment.py -Encoding UTF8

# Run the test
python test_local_deployment.py
```

### Step 10: Test Network Access (Optional)

```powershell
# Find your PC's local IP
ipconfig | Select-String "IPv4"
# Example: 192.168.1.50

# From another device (phone/laptop) on same WiFi:
# http://192.168.1.50:9102  (Dashboard)
# http://192.168.1.50:6333  (Qdrant)
```

---

## ✅ Verification Checklist

Before proceeding to home server, verify:

- [ ] All 4 containers running and healthy
- [ ] ML Backend responds to health check
- [ ] Qdrant accepts connections
- [ ] Dashboard opens in browser
- [ ] Embedding models loaded successfully
- [ ] Can create Qdrant collection
- [ ] Can insert and retrieve documents
- [ ] Wave 6 integration tests pass (5/5)
- [ ] Custom test script passes all checks
- [ ] Total disk usage acceptable (check with `docker system df`)

```powershell
# Check disk usage
docker system df

# Expected:
# TYPE            TOTAL     ACTIVE    SIZE
# Images          4-6       4         ~2GB
# Containers      4         4         ~200MB
# Local Volumes   3         3         ~500MB
# Total:                              ~3GB
```

---

## 🎮 Interactive Testing Session

Try these commands to explore:

```powershell
# 1. Check logs for any errors
docker compose logs gateway | Select-String "error|ERROR|Error"
docker compose logs ml-backend | Select-String "error|ERROR|Error"

# 2. Check resource usage
docker stats --no-stream

# 3. Test restart resilience
docker compose restart gateway
Start-Sleep -Seconds 5
curl http://localhost:9100
# Should recover and respond

# 4. Test volume persistence
docker compose down  # Stop containers
docker compose up -d  # Start again
# Models should NOT re-download (cached in volumes)

# 5. Check model cache size
docker volume inspect latest_mcp_backend-model-cache
docker volume inspect latest_mcp_mcp-model-cache
```

---

## 🧹 Cleanup After Testing

### Option 1: Stop but Keep Data

```powershell
# Stop containers, keep volumes (models stay cached)
docker compose down

# Start again later - instant startup
docker compose up -d
```

### Option 2: Full Cleanup

```powershell
# Stop and remove everything (including model cache)
docker compose down -v

# Remove all unused Docker resources
docker system prune -a

# Delete test directory (optional)
cd ..
Remove-Item -Path "D:\MCP_Test_Deploy" -Recurse -Force
```

---

## 🐛 Troubleshooting Local Test

### Issue: Port Already in Use

```powershell
# Find what's using port 9100
netstat -ano | findstr "9100"

# Kill the process
taskkill /PID <pid> /F

# Or change ports in docker-compose.yml:
# ports:
#   - "9200:8000"  # Use 9200 instead of 9100
```

### Issue: Out of Disk Space

```powershell
# Check space on test drive
Get-PSDrive D  # or your test drive

# Clean Docker
docker system prune -a

# Free up Windows space
cleanmgr
```

### Issue: Docker Desktop Not Starting

```powershell
# Restart Docker Desktop
Get-Process "*docker desktop*" | Stop-Process -Force
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Or restart WSL
wsl --shutdown
# Then start Docker Desktop
```

### Issue: Models Download Slow

```powershell
# Pre-download all models before docker compose up
pip install sentence-transformers torch

python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('Models downloaded to:', import('sentence_transformers').__file__)
"

# Then models will be cached for Docker volumes
```

---

## 📊 Success Criteria

**Your test is successful when:**

✅ All services start without errors
✅ Health checks pass within 2 minutes
✅ Can retrieve documents from Qdrant
✅ Embedding vectors are 384-dimensional
✅ Dashboard loads in browser
✅ Integration tests pass (5/5)
✅ Can stop and restart without issues
✅ Total disk usage < 5GB

**Once successful, you're ready to deploy to home server!**

---

## 🎯 Next Steps After Successful Test

1. **Document any issues** you encountered
2. **Note actual disk usage** on your test drive
3. **Record startup time** (for comparison with home server)
4. **Take screenshots** of dashboard (optional)
5. **Copy .env settings** that worked well
6. **Deploy to home server** with confidence!

**Deployment command for home server:**

```powershell
# On home server:
.\scripts\deploy_home_server.ps1

# Use the same configuration that worked in testing
```

---

## 💡 Pro Tips

1. **Keep test deployment** - useful for development without affecting home server
2. **Use different ports** if running both test + home server simultaneously
3. **Test Wave 6 rollout** - enable re-ranking in test first, verify, then on server
4. **Benchmark performance** - compare PC vs home server hardware
5. **Test backups** - practice backup/restore on test deployment first

---

**Ready to test? Start with Step 1!** 🚀

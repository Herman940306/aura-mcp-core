# Wave 6 Advanced Retrieval - Deployment Runbook

**Version**: 1.0
**Status**: Phases 1-3 Complete (45/45 tests passing)
**Target**: Production deployment with phased rollout strategy

---

## 📋 Executive Summary

Wave 6 introduces production-grade retrieval with three core capabilities:

1. **Real Embeddings (Phase 1)**: sentence-transformers models replace pseudo-embeddings
2. **Connection Pooling (Phase 2)**: Retry logic, circuit breaker, concurrent connections
3. **Re-Ranking & Query Expansion (Phase 3)**: Cross-encoder re-scoring, WordNet synonyms, multi-query templates

**Deployment Strategy**: Conservative phased rollout with monitoring at each stage.

**Rollback**: Feature flags enable instant rollback without code changes.

---

## 🎯 Prerequisites

### System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 4 cores | 8 cores (12+ for high traffic) |
| **RAM** | 4GB | 8GB (16GB+ with re-ranking) |
| **Disk** | 5GB free | 10GB+ (model cache + logs) |
| **Python** | 3.9+ | 3.11+ |
| **Qdrant** | v1.7.0+ | v1.11.0+ (query_points API) |

**GPU (Optional)**:

- CUDA 11.8+ for GPU acceleration
- 4GB+ VRAM (8GB+ for large models)
- 5-10x latency improvement over CPU

### Python Dependencies

Install additional Wave 6 dependencies:

```bash
pip install sentence-transformers==2.2.2
pip install torch>=2.0.0
pip install nltk==3.9.2
pip install qdrant-client==1.16.1

# Download NLTK data (required for synonym expansion)
python -c "import nltk; nltk.download('wordnet')"
```

**Verify Installation**:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
python -c "from nltk.corpus import wordnet; print(len(wordnet.all_synsets()))"
```

### Model Downloads

Models auto-download on first use (~200MB total). Pre-download for faster startup:

```bash
python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('all-MiniLM-L6-v2')
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
"
```

Models cache to:

- Linux/macOS: `~/.cache/huggingface/hub/`
- Windows: `%USERPROFILE%\.cache\huggingface\hub\`

**Disk Space**:

- Bi-encoder (all-MiniLM-L6-v2): 80MB
- Cross-encoder (ms-marco-MiniLM-L-6-v2): 90MB
- NLTK WordNet: 10MB
- Total: ~200MB

---

## 🚀 Phased Rollout Strategy

### Week 1: Baseline (Real Embeddings Only)

**Goal**: Establish baseline quality with real embeddings, no advanced features.

**Configuration**:

```bash
# Enable real embeddings, disable advanced features
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RERANK_ENABLED=0
QUERY_EXPANSION_ENABLED=0
QDRANT_POOL_SIZE=3
QDRANT_POOL_RETRY_ENABLED=1
```

**Expected Impact**:

- Quality: +5-10% over pseudo-embeddings
- Latency: 15-25ms per query (CPU)
- Model load: +80MB memory

**Monitoring**:

- `embedding_latency_seconds`: p50 <20ms, p99 <50ms
- `qdrant_retry_attempts_total`: <1% retry rate
- `qdrant_circuit_breaker_open`: 0 (no circuit trips)

**Success Criteria**:

- Zero crashes or OOM errors
- <50ms p99 latency
- Quality improvement confirmed by spot checks
- No increase in error rate

**Rollback** (if needed):

```bash
EMBEDDING_MODEL=  # Empty to use pseudo-embeddings
```

---

### Week 2: Enable Re-Ranking

**Goal**: Add cross-encoder re-ranking for quality boost.

**Configuration**:

```bash
# Week 1 config + re-ranking
RERANK_ENABLED=1
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANK_DEVICE=cpu
RERANK_TOP_K=50  # Retrieve 50, re-rank to top-10
```

**Expected Impact**:

- Quality: +10-15% over baseline (total +15-25%)
- Latency: +40-50ms per query (CPU), +5-10ms (GPU)
- Model load: +90MB memory

**Monitoring**:

- `reranker_latency_seconds`: p50 <50ms (CPU), <10ms (GPU)
- `reranker_score_distribution`: Check score variance
- `reranker_candidates_total`: Should match RERANK_TOP_K

**Success Criteria**:

- <100ms p99 total latency
- Quality improvement visible in user metrics (CTR, satisfaction)
- No memory issues (monitor RSS)

**Rollback** (if needed):

```bash
RERANK_ENABLED=0
```

---

### Week 3-4: Full Strategy (Expansion + Re-Ranking)

**Goal**: Maximum quality with query expansion.

**Configuration**:

```bash
# Week 2 config + query expansion
QUERY_EXPANSION_ENABLED=1
EXPANSION_STRATEGY=synonyms  # Start with synonyms (faster)
EXPANSION_MAX_VARIANTS=5
```

**Expected Impact**:

- Quality: +5-10% over Week 2 (total +20-35%)
- Latency: +15-20ms per query
- Recall: +10-20% (more relevant results found)

**Monitoring**:

- `query_expansion_variants_total`: Should average ~4-5 per query
- `query_expansion_latency_seconds`: p50 <10ms
- End-to-end latency: p99 <150ms

**Success Criteria**:

- <150ms p99 total latency
- Quality at target level (user feedback, A/B test if available)
- System stable under load

**Switch to Multi-Query** (Week 4, optional):

```bash
EXPANSION_STRATEGY=multi_query  # More diverse, slightly slower
```

**Rollback** (if needed):

```bash
QUERY_EXPANSION_ENABLED=0
```

---

### Week 5+: Production Optimization

**Goal**: Optimize for scale, build A/B testing framework.

**Configuration** (Production Profile):

```bash
# Full features, optimized
EMBEDDING_MODEL=all-mpnet-base-v2  # Upgrade to higher quality
EMBEDDING_DEVICE=cuda  # GPU acceleration
RERANK_ENABLED=1
RERANK_MODEL=ms-marco-electra-base  # Highest quality cross-encoder
RERANK_DEVICE=cuda
RERANK_TOP_K=50
QUERY_EXPANSION_ENABLED=1
EXPANSION_STRATEGY=multi_query
EXPANSION_MAX_VARIANTS=5
QDRANT_POOL_SIZE=10  # Scale for concurrency
```

**Expected Impact**:

- Quality: +10-15% over Week 3 (total +30-50%)
- Latency: 50-100ms p99 (GPU), better than Week 3 on CPU
- Throughput: 10x with pool size 10

**Monitoring**:

- All metrics stable under production load
- p99 latency <100ms
- Quality metrics at target

**Next Steps**:

- Build A/B testing framework (Wave 6 Phase 4)
- Experiment with model combinations
- Fine-tune based on real usage patterns

---

## 🔧 Configuration Profiles

### Development (Fast Iteration)

```bash
# Minimal overhead, fast feedback
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RERANK_ENABLED=0
QUERY_EXPANSION_ENABLED=0
QDRANT_POOL_SIZE=1
QDRANT_POOL_RETRY_ENABLED=1
QDRANT_POOL_MAX_RETRIES=3
```

**Use Case**: Local development, unit tests, fast iteration

---

### Staging (Balanced)

```bash
# Test quality improvements with moderate resources
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RERANK_ENABLED=1
RERANK_TOP_K=30
QUERY_EXPANSION_ENABLED=1
EXPANSION_STRATEGY=synonyms
QDRANT_POOL_SIZE=3
QDRANT_POOL_RETRY_ENABLED=1
```

**Use Case**: Pre-production testing, load testing, quality validation

---

### Production (Maximum Quality)

```bash
# Full features, optimized for GPU
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DEVICE=cuda
RERANK_ENABLED=1
RERANK_MODEL=ms-marco-electra-base
RERANK_DEVICE=cuda
RERANK_TOP_K=50
QUERY_EXPANSION_ENABLED=1
EXPANSION_STRATEGY=multi_query
EXPANSION_MAX_VARIANTS=5
QDRANT_POOL_SIZE=10
QDRANT_POOL_TIMEOUT=30.0
QDRANT_POOL_RETRY_ENABLED=1
QDRANT_POOL_MAX_RETRIES=3
QDRANT_POOL_RETRY_DELAY=1.0
```

**Use Case**: High-traffic production, GPU-accelerated, maximum quality

---

## 📊 Re-Indexing Qdrant

Wave 6 uses real embeddings, so existing collections must be re-indexed.

### Step 1: Backup Existing Data

```bash
# Export Qdrant collection (if needed)
curl -X POST http://localhost:6333/collections/my_docs/snapshots
```

### Step 2: Create Collection with New Schema

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(host="localhost", port=6333)

client.recreate_collection(
    collection_name="my_docs",
    vectors_config=VectorParams(
        size=384,  # all-MiniLM-L6-v2 dimensions
        distance=Distance.COSINE,
    ),
)
```

**For all-mpnet-base-v2 (production)**:

```python
vectors_config=VectorParams(
    size=768,  # 768 dimensions
    distance=Distance.COSINE,
)
```

### Step 3: Re-Index Documents

```python
from aura_ia_mcp.services.model_gateway.embedding_service import EmbeddingService

embed_service = EmbeddingService(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device="cpu",
)

documents = [
    {"id": 1, "text": "Example document 1"},
    {"id": 2, "text": "Example document 2"},
    # ... more documents
]

points = []
for doc in documents:
    vector = embed_service.encode(doc["text"])
    points.append({
        "id": doc["id"],
        "vector": vector,
        "payload": {"text": doc["text"]},
    })

client.upsert(collection_name="my_docs", points=points)
```

**Batch Upsert** (for large datasets):

```python
from qdrant_client.models import PointStruct

batch_size = 100
for i in range(0, len(documents), batch_size):
    batch = documents[i:i+batch_size]
    points = [
        PointStruct(
            id=doc["id"],
            vector=embed_service.encode(doc["text"]),
            payload={"text": doc["text"]},
        )
        for doc in batch
    ]
    client.upsert(collection_name="my_docs", points=points)
    print(f"Indexed {i+len(batch)}/{len(documents)}")
```

### Step 4: Verify Indexing

```python
# Check collection info
info = client.get_collection("my_docs")
print(f"Points count: {info.points_count}")
print(f"Vector size: {info.config.params.vectors.size}")

# Test retrieval
from aura_ia_mcp.services.model_gateway.retrieval_pipeline import Retriever, RetrievalConfig

config = RetrievalConfig(collection="my_docs", top_k=5)
retriever = Retriever(client=client, embed_fn=embed_service, cfg=config)
results = retriever.retrieve("example query")
print(f"Retrieved {len(results)} results")
```

---

## 📈 Monitoring & Metrics

### Prometheus Metrics

Wave 6 exposes metrics at `http://localhost:9103/metrics`:

#### Embedding Metrics

```
embedding_latency_seconds_bucket{le="0.01"} 45
embedding_latency_seconds_bucket{le="0.05"} 98
embedding_latency_seconds_bucket{le="0.1"} 100
embedding_latency_seconds_sum 4.2
embedding_latency_seconds_count 100
```

**Key Metrics**:

- `embedding_latency_seconds`: Time to encode queries/documents
- `embedding_batch_size`: Current batch size (if batching enabled)

**Alerts**:

- `embedding_latency_seconds{quantile="0.99"} > 0.1` (p99 >100ms)

#### Re-Ranking Metrics

```
reranker_latency_seconds_bucket{le="0.05"} 20
reranker_latency_seconds_bucket{le="0.1"} 85
reranker_latency_seconds_bucket{le="0.2"} 100
reranker_latency_seconds_sum 8.5
reranker_latency_seconds_count 100

reranker_score_distribution_bucket{le="0.5"} 30
reranker_score_distribution_bucket{le="0.7"} 70
reranker_score_distribution_bucket{le="0.9"} 95

reranker_candidates_total 5000
```

**Key Metrics**:

- `reranker_latency_seconds`: Time to re-rank candidates
- `reranker_score_distribution`: Cross-encoder score distribution
- `reranker_candidates_total`: Number of documents re-ranked

**Alerts**:

- `reranker_latency_seconds{quantile="0.99"} > 0.2` (p99 >200ms)
- `rate(reranker_candidates_total[1m]) == 0` (no re-ranking happening)

#### Query Expansion Metrics

```
query_expansion_variants_total 450
query_expansion_latency_seconds_bucket{le="0.01"} 90
query_expansion_latency_seconds_bucket{le="0.02"} 100
```

**Key Metrics**:

- `query_expansion_variants_total`: Number of query variants generated
- `query_expansion_latency_seconds`: Time to expand queries

**Alerts**:

- `rate(query_expansion_variants_total[1m]) / rate(embedding_latency_seconds_count[1m]) < 3` (expansion not working)

#### Connection Pool Metrics

```
qdrant_pool_size 5
qdrant_pool_waiting 0
qdrant_circuit_breaker_open 0
qdrant_retry_attempts_total 12
```

**Key Metrics**:

- `qdrant_pool_size`: Active connections in pool
- `qdrant_pool_waiting`: Queries waiting for connection
- `qdrant_circuit_breaker_open`: 1 if circuit breaker is open
- `qdrant_retry_attempts_total`: Total retry attempts

**Alerts**:

- `qdrant_circuit_breaker_open > 0` (circuit breaker tripped)
- `qdrant_pool_waiting > 10` (pool exhausted)
- `rate(qdrant_retry_attempts_total[5m]) > 0.01` (>1% retry rate)

### Grafana Dashboard

**Panels**:

1. **Retrieval Latency Breakdown**:
   - Embedding latency (p50, p90, p99)
   - Re-ranking latency (p50, p90, p99)
   - Query expansion latency (p50, p90, p99)
   - Total end-to-end latency

2. **Pool Health**:
   - Pool size (current vs configured)
   - Waiting queries
   - Circuit breaker status
   - Retry rate (per second)

3. **Quality Indicators**:
   - Re-ranker score distribution
   - Query expansion rate (variants per query)
   - Retrieval success rate

4. **Resource Usage**:
   - Memory RSS (track model loading)
   - CPU utilization
   - GPU utilization (if available)

**Import Dashboard**:

```bash
# Download pre-built dashboard
curl -o wave6_dashboard.json https://example.com/wave6_dashboard.json

# Import to Grafana
curl -X POST http://admin:admin@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @wave6_dashboard.json
```

---

## 🔥 Troubleshooting

### Issue 1: Out of Memory (OOM)

**Symptom**: Process killed during model loading or inference

**Diagnosis**:

```bash
# Check memory usage
ps aux | grep python
top -p <pid>

# Check model sizes
du -sh ~/.cache/huggingface/hub/
```

**Solutions**:

1. **Use smaller models**:

   ```bash
   EMBEDDING_MODEL=all-MiniLM-L6-v2  # 80MB instead of all-mpnet-base-v2 (420MB)
   RERANK_MODEL=ms-marco-TinyBERT-L-2-v2  # 16MB instead of electra-base (420MB)
   ```

2. **Disable re-ranking**:

   ```bash
   RERANK_ENABLED=0  # Saves ~90MB
   ```

3. **Reduce pool size**:

   ```bash
   QDRANT_POOL_SIZE=1  # Single connection
   ```

4. **Use CPU instead of GPU**:

   ```bash
   EMBEDDING_DEVICE=cpu
   RERANK_DEVICE=cpu
   ```

5. **Increase system memory**:
   - Minimum 4GB → 8GB
   - Swap space: 4GB+ (not recommended for production)

---

### Issue 2: Slow Inference (>500ms)

**Symptom**: Queries take too long, timeout errors

**Diagnosis**:

```bash
# Check Prometheus metrics
curl http://localhost:9103/metrics | grep latency

# Check CPU/GPU usage
nvidia-smi  # GPU
htop        # CPU
```

**Solutions**:

1. **Enable GPU acceleration**:

   ```bash
   EMBEDDING_DEVICE=cuda
   RERANK_DEVICE=cuda
   # Requires CUDA-capable GPU (5-10x speedup)
   ```

2. **Reduce re-ranking candidates**:

   ```bash
   RERANK_TOP_K=20  # Instead of 50
   ```

3. **Disable query expansion**:

   ```bash
   QUERY_EXPANSION_ENABLED=0  # Saves 15-20ms
   ```

4. **Use faster models**:

   ```bash
   RERANK_MODEL=ms-marco-TinyBERT-L-2-v2  # 3x faster than MiniLM
   ```

5. **Optimize Qdrant**:
   - Increase Qdrant resources (CPU, RAM)
   - Use SSD for Qdrant storage
   - Tune Qdrant indexing parameters (HNSW)

---

### Issue 3: Model Loading Fails

**Symptom**: `OSError: Can't load model` or `ConnectionError`

**Diagnosis**:

```bash
# Check network connectivity
curl https://huggingface.co

# Check disk space
df -h ~/.cache/huggingface

# Check model cache
ls -lh ~/.cache/huggingface/hub/
```

**Solutions**:

1. **Pre-download models**:

   ```bash
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
   python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
   ```

2. **Set local cache**:

   ```bash
   export TRANSFORMERS_CACHE=/path/to/cache
   ```

3. **Use offline mode** (if models already cached):

   ```bash
   export TRANSFORMERS_OFFLINE=1
   ```

4. **Check firewall/proxy**:
   - Allow outbound HTTPS to huggingface.co
   - Set proxy: `export HTTPS_PROXY=http://proxy:8080`

5. **Check disk space**:
   - Ensure 1GB+ free space in cache directory
   - Clean old models: `rm -rf ~/.cache/huggingface/hub/models--*`

---

### Issue 4: NLTK WordNet Missing

**Symptom**: `LookupError: WordNet not found` when using synonym expansion

**Diagnosis**:

```bash
python -c "from nltk.corpus import wordnet; print(wordnet.synsets('test'))"
```

**Solutions**:

1. **Download WordNet**:

   ```bash
   python -c "import nltk; nltk.download('wordnet')"
   ```

2. **Verify installation**:

   ```bash
   python -c "from nltk.corpus import wordnet; print(len(wordnet.all_synsets()))"
   # Should print: 117659
   ```

3. **Use multi-query strategy instead**:

   ```bash
   EXPANSION_STRATEGY=multi_query  # Doesn't require WordNet
   ```

---

### Issue 5: Qdrant API Compatibility

**Symptom**: `AttributeError: 'QdrantClient' object has no attribute 'search'`

**Diagnosis**:

```bash
python -c "from qdrant_client import QdrantClient; print(QdrantClient.__version__)"
# Should be 1.16.1 or higher
```

**Solutions**:

1. **Upgrade qdrant-client**:

   ```bash
   pip install --upgrade qdrant-client==1.16.1
   ```

2. **Verify API usage**:
   - Old API: `client.search(collection_name=..., query_vector=...)`
   - New API: `client.query_points(collection_name=..., query=...).points`

3. **Check code version**:
   - Ensure using Wave 6 Phase 3 code (with `query_points()` API)

---

### Issue 6: Circuit Breaker Keeps Opening

**Symptom**: `qdrant_circuit_breaker_open` metric = 1, queries failing

**Diagnosis**:

```bash
# Check Qdrant health
curl http://localhost:6333/health

# Check circuit breaker metric
curl http://localhost:9103/metrics | grep circuit_breaker
```

**Solutions**:

1. **Fix underlying Qdrant issue**:
   - Check Qdrant logs: `docker logs qdrant`
   - Restart Qdrant: `docker restart qdrant`
   - Check Qdrant resources (CPU, RAM, disk)

2. **Adjust circuit breaker settings**:

   ```python
   # In code: pool.py
   self.circuit_failure_threshold = 10  # Increase from 5
   self.circuit_reset_timeout = 120.0  # Increase from 60s
   ```

3. **Reduce retry attempts**:

   ```bash
   QDRANT_POOL_MAX_RETRIES=1  # Fail faster
   ```

4. **Increase pool timeout**:

   ```bash
   QDRANT_POOL_TIMEOUT=60.0  # Longer wait before timeout
   ```

---

## 🔐 Security Considerations

### Model Integrity

**Threat**: Malicious model files from HuggingFace

**Mitigation**:

1. Pin model versions in requirements.txt
2. Use checksum verification (future enhancement)
3. Host models internally (air-gapped environments)

### Prompt Injection

**Threat**: Malicious queries exploit model behavior

**Mitigation**:

1. Input validation (max length, character whitelist)
2. Rate limiting per user/IP
3. Audit logging of all queries

### Resource Exhaustion

**Threat**: Large models or high query volume exhaust resources

**Mitigation**:

1. Memory limits (Docker: `--memory=8g`)
2. Query rate limiting (100 qps per user)
3. Circuit breaker protects against Qdrant failures
4. Auto-scaling (Kubernetes HPA)

---

## 📦 Rollback Procedures

### Instant Rollback (Feature Flags)

Disable features without code changes:

```bash
# Disable all Wave 6 features
RERANK_ENABLED=0
QUERY_EXPANSION_ENABLED=0
EMBEDDING_MODEL=  # Falls back to pseudo-embeddings
```

Restart service:

```bash
docker restart mcp-server
# Or
systemctl restart aura-mcp-server
```

**Rollback Time**: <30 seconds (container restart)

### Code Rollback (Git)

Revert to previous release:

```bash
git revert <wave6-commit-hash>
git push origin main
```

Redeploy:

```bash
docker compose build --no-cache mcp-server
docker compose up -d mcp-server
```

**Rollback Time**: 5-10 minutes (rebuild + redeploy)

### Data Rollback (Qdrant)

Restore old collection with pseudo-embeddings:

```bash
# Restore from snapshot
curl -X POST http://localhost:6333/collections/my_docs/snapshots/<snapshot-name>/recover
```

Or use old collection:

```bash
# Switch collection name
QDRANT_COLLECTION=my_docs_v5  # Old Wave 5 collection
```

**Rollback Time**: <1 minute (collection switch) or 10-30 minutes (snapshot restore)

---

## ✅ Post-Deployment Checklist

### Week 1 (Baseline)

- [ ] All dependencies installed (`sentence-transformers`, `nltk`, `torch`)
- [ ] Models downloaded and cached (~200MB)
- [ ] Qdrant upgraded to v1.7.0+ (query_points API support)
- [ ] Environment variables configured (baseline profile)
- [ ] Service restarted successfully (no errors in logs)
- [ ] Prometheus metrics visible (`embedding_latency_seconds`)
- [ ] Test query returns results (<50ms p99 latency)
- [ ] No OOM errors in first 24 hours
- [ ] Quality spot check: results are relevant

### Week 2 (Re-Ranking)

- [ ] `RERANK_ENABLED=1` set in environment
- [ ] Cross-encoder model downloaded (~90MB)
- [ ] `reranker_latency_seconds` metric visible in Prometheus
- [ ] Test query returns re-ranked results (<100ms p99 latency)
- [ ] Quality improvement confirmed (spot check or A/B test)
- [ ] No memory issues (monitor RSS)
- [ ] Rollback procedure tested (disable re-ranking, verify)

### Week 3-4 (Expansion)

- [ ] `QUERY_EXPANSION_ENABLED=1` set in environment
- [ ] NLTK WordNet downloaded (~10MB)
- [ ] `query_expansion_variants_total` metric increasing
- [ ] Test query generates multiple variants (check logs)
- [ ] End-to-end latency <150ms p99
- [ ] Quality at target level (user feedback positive)
- [ ] Multi-query strategy tested (optional)

### Week 5+ (Production)

- [ ] GPU acceleration enabled (if available)
- [ ] Production profile configured (high-quality models)
- [ ] Pool size tuned for concurrency (`QDRANT_POOL_SIZE=10`)
- [ ] Grafana dashboard deployed and monitoring
- [ ] All alerts configured (latency, circuit breaker, OOM)
- [ ] Runbook shared with ops team
- [ ] Incident response plan documented
- [ ] A/B testing framework (Wave 6 Phase 4) prioritized

---

## 📞 Support & Escalation

### First Response

1. **Check Prometheus metrics**: `http://localhost:9103/metrics`
2. **Check logs**: `tail -f logs/mcp_tool_spans.jsonl`
3. **Verify Qdrant health**: `curl http://localhost:6333/health`
4. **Review this runbook**: Search for symptom in Troubleshooting section

### Escalation Path

1. **Level 1**: On-call engineer (ops team)
   - Restart service
   - Disable problematic feature (rollback)
   - Check resource usage (CPU, RAM, disk)

2. **Level 2**: ML infrastructure team
   - Model loading issues
   - Performance degradation
   - Qdrant issues

3. **Level 3**: Development team
   - Code bugs
   - API compatibility issues
   - Feature requests

### Contact

- **Slack**: `#aura-mcp-alerts`
- **PagerDuty**: `aura-mcp-oncall`
- **Email**: `mcp-ops@example.com`

---

## 📚 Related Documentation

- [WAVE6_PLAN.md](../WAVE6_PLAN.md) - Full Wave 6 roadmap (Phases 1-5)
- [WAVE6_PHASE1_COMPLETE.md](./WAVE6_PHASE1_COMPLETE.md) - Real embeddings implementation
- [WAVE6_PHASE2_COMPLETE.md](./WAVE6_PHASE2_COMPLETE.md) - Connection pooling
- [WAVE6_PHASE3_COMPLETE.md](./WAVE6_PHASE3_COMPLETE.md) - Re-ranking + query expansion
- [README.md](../README.md) - Wave 6 configuration reference
- [PROJECT_STATE_OVERVIEW.md](./PROJECT_STATE_OVERVIEW.md) - Overall project status

---

## 🎉 Deployment Complete

Wave 6 Phases 1-3 are production-ready with comprehensive monitoring, rollback procedures, and troubleshooting guides. Follow the phased rollout strategy for a safe, controlled deployment.

**Next Steps**:

1. Deploy Week 1 (baseline embeddings)
2. Monitor for 7 days
3. Proceed to Week 2 (re-ranking)
4. Monitor and tune
5. Complete rollout by Week 5
6. Build A/B testing framework (Phase 4) based on real usage

**Questions?** Contact the MCP ops team on Slack: `#aura-mcp-support`

---

**Version**: 1.0
**Last Updated**: 2025-01-20
**Status**: Ready for Production Deployment 🚀

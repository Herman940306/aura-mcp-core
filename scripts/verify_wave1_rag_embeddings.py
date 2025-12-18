#!/usr/bin/env python3
"""Verify Wave 1 implementation (RAG, Embeddings, LLM Proxy)."""

import asyncio
import sys

import httpx


async def verify_wave1():
    """Verify all Wave 1 services are operational."""
    base_url = "http://localhost:9200"
    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Check Embeddings Service Health
        print("🔍 Checking Embeddings Service...")
        try:
            response = await client.get(f"{base_url}/embed/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Embeddings: {data['status']} ({data['model']})")
                results.append(("embeddings_health", True))
            else:
                print(
                    f"❌ Embeddings health check failed: {response.status_code}"
                )
                results.append(("embeddings_health", False))
        except Exception as e:
            print(f"❌ Embeddings service error: {e}")
            results.append(("embeddings_health", False))

        # 2. Test Embeddings Generation
        print("\n🔍 Testing Embeddings Generation...")
        try:
            response = await client.post(
                f"{base_url}/embed/vectors",
                json={
                    "texts": ["Hello world", "Test document"],
                    "normalize": True,
                },
            )
            if response.status_code == 200:
                data = response.json()
                print(
                    f"✅ Generated {len(data['embeddings'])} embeddings "
                    f"({data['dimensions']} dimensions)"
                )
                results.append(("embeddings_generate", True))

                # Store embeddings for RAG test
                test_embeddings = data["embeddings"]
            else:
                print(
                    f"❌ Embeddings generation failed: {response.status_code}"
                )
                results.append(("embeddings_generate", False))
                test_embeddings = None
        except Exception as e:
            print(f"❌ Embeddings generation error: {e}")
            results.append(("embeddings_generate", False))
            test_embeddings = None

        # 3. Check RAG Service Health
        print("\n🔍 Checking RAG Service...")
        try:
            response = await client.get(f"{base_url}/rag/health")
            if response.status_code == 200:
                data = response.json()
                print(
                    f"✅ RAG: {data['status']} "
                    f"({data.get('points_count', 0)} documents)"
                )
                results.append(("rag_health", True))
            else:
                print(f"❌ RAG health check failed: {response.status_code}")
                results.append(("rag_health", False))
        except Exception as e:
            print(f"❌ RAG service error: {e}")
            results.append(("rag_health", False))

        # 4. Test RAG Upsert (if embeddings work)
        if test_embeddings:
            print("\n🔍 Testing RAG Document Upsert...")
            try:
                documents = [
                    {
                        "id": 1,
                        "text": "Hello world",
                        "vector": test_embeddings[0],
                        "metadata": {"source": "test"},
                    },
                    {
                        "id": 2,
                        "text": "Test document",
                        "vector": test_embeddings[1],
                        "metadata": {"source": "test"},
                    },
                ]

                response = await client.post(
                    f"{base_url}/rag/upsert", json={"documents": documents}
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Upserted {data['upserted']} documents")
                    results.append(("rag_upsert", True))
                else:
                    print(f"❌ RAG upsert failed: {response.status_code}")
                    results.append(("rag_upsert", False))
            except Exception as e:
                print(f"❌ RAG upsert error: {e}")
                results.append(("rag_upsert", False))

            # 5. Test RAG Query
            print("\n🔍 Testing RAG Query...")
            try:
                response = await client.post(
                    f"{base_url}/rag/query",
                    json={"query_vector": test_embeddings[0], "top_k": 2},
                )

                if response.status_code == 200:
                    data = response.json()
                    print(
                        f"✅ Retrieved {len(data['results'])} documents "
                        f"(top score: {data['results'][0]['score']:.3f})"
                    )
                    results.append(("rag_query", True))
                else:
                    print(f"❌ RAG query failed: {response.status_code}")
                    results.append(("rag_query", False))
            except Exception as e:
                print(f"❌ RAG query error: {e}")
                results.append(("rag_query", False))

        # 6. Check LLM Proxy Health
        print("\n🔍 Checking LLM Proxy Service...")
        try:
            response = await client.get(f"{base_url}/llm/health")
            if response.status_code == 200:
                data = response.json()
                backends = data.get("backends", {})
                print(f"✅ LLM Proxy: {data['status']}")
                for backend, status in backends.items():
                    print(f"   - {backend}: {status}")
                results.append(("llm_health", True))
            else:
                print(
                    f"❌ LLM proxy health check failed: {response.status_code}"
                )
                results.append(("llm_health", False))
        except Exception as e:
            print(f"❌ LLM proxy service error: {e}")
            results.append(("llm_health", False))

        # 7. Test LLM Generation (if Ollama is available)
        print("\n🔍 Testing LLM Generation (Ollama)...")
        try:
            response = await client.post(
                f"{base_url}/llm/generate",
                json={
                    "prompt": "Say hello in one word",
                    "model": "llama3.2:1b",
                    "max_tokens": 10,
                    "backend": "ollama",
                },
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Generated: {data['generated_text'][:50]}...")
                results.append(("llm_generate", True))
            else:
                print(
                    f"⚠️  LLM generation skipped (Ollama not available): "
                    f"{response.status_code}"
                )
                results.append(("llm_generate", False))
        except Exception as e:
            print(f"⚠️  LLM generation skipped: {e}")
            results.append(("llm_generate", False))

    # Summary
    print("\n" + "=" * 60)
    print("WAVE 1 VERIFICATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test}")

    print("=" * 60)
    print(f"Result: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(verify_wave1())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Verification interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""
NEXORA AI Authentic Latency, Concurrency & Subsystem Benchmark Runner.

Executes real asynchronous HTTP load measurements via httpx.ASGITransport against
FastAPI + SQLAlchemy Async in an isolated temporary database directory, plus
micro-benchmarks for RAG hybrid retrieval and document parsing.
All metrics printed are directly measured on the host runtime — never fabricated.
"""
import asyncio
import json
import math
import os
import statistics
import sys
import tempfile
import time
from typing import Any, Callable, Coroutine, Dict, List

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 3)
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return round(sorted_vals[int(k)], 3)
    return round(sorted_vals[lo] + (k - lo) * (sorted_vals[hi] - sorted_vals[lo]), 3)


def _summarize(latencies_ms: List[float], errors: int, total_wall_s: float) -> Dict[str, Any]:
    s = sorted(latencies_ms)
    n = len(latencies_ms)
    return {
        "requests": n,
        "errors": errors,
        "error_rate_pct": round((errors / max(1, n)) * 100.0, 2),
        "wall_time_s": round(total_wall_s, 4),
        "rps": round(n / max(1e-6, total_wall_s), 2),
        "min_ms": round(s[0], 3) if s else 0.0,
        "mean_ms": round(statistics.mean(s), 3) if s else 0.0,
        "p50_ms": _percentile(s, 50),
        "p95_ms": _percentile(s, 95),
        "p99_ms": _percentile(s, 99),
        "max_ms": round(s[-1], 3) if s else 0.0,
    }


async def _run_concurrent_load(
    fn: Callable[[], Coroutine[Any, Any, int]],
    total_requests: int,
    concurrency: int,
) -> Dict[str, Any]:
    sem = asyncio.Semaphore(concurrency)
    latencies: List[float] = []
    errors = 0

    async def _one():
        nonlocal errors
        async with sem:
            t0 = time.perf_counter()
            code = await fn()
            dt = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt)
            if code >= 400:
                errors += 1

    wall0 = time.perf_counter()
    await asyncio.gather(*[_one() for _ in range(total_requests)])
    wall_s = time.perf_counter() - wall0
    return _summarize(latencies, errors, wall_s)


async def run_benchmarks() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="nexora_bench_", ignore_cleanup_errors=True) as tmp_dir:
        db_file = os.path.join(tmp_dir, "bench_nexora.db").replace("\\", "/")
        upload_dir = os.path.join(tmp_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
        os.environ["SECRET_KEY"] = "benchmark_secret_key_nexora_32_characters_minimum"
        os.environ["REDIS_ENABLED"] = "false"
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        os.environ["UPLOAD_DIR"] = upload_dir

        from httpx import ASGITransport, AsyncClient
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.database import Base, get_db
        from app.lab.telemetry.monitor import HardwareTelemetryMonitor
        from app.main import app
        from app.services.billing_service import billing_service
        from app.services.document.document_service import document_intelligence_service
        from app.services.rag.rag_service import rag_service

        bench_engine = create_async_engine(
            os.environ["DATABASE_URL"],
            connect_args={"check_same_thread": False},
        )
        BenchSession = async_sessionmaker(
            bind=bench_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        async def override_db():
            async with BenchSession() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()

        app.dependency_overrides[get_db] = override_db

        try:
            async with bench_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            transport = ASGITransport(app=app)
            results: Dict[str, Any] = {
                "hardware": HardwareTelemetryMonitor.get_system_telemetry(),
                "endpoints": {},
                "subsystems": {},
            }

            async with AsyncClient(transport=transport, base_url="http://bench") as client:
                # Provision benchmark user & Pro developer API key
                reg = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "bench@nexora.ai",
                        "username": "benchuser",
                        "password": "BenchPassword123!",
                        "display_name": "Benchmark Runner",
                    },
                )
                assert reg.status_code == 201, reg.text
                jwt_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

                sub = await client.post(
                    "/api/v1/billing/subscribe",
                    headers=jwt_headers,
                    json={"tier": "pro", "billing_cycle": "monthly"},
                )
                assert sub.status_code == 200

                key_res = await client.post(
                    "/api/v1/developer/keys",
                    headers=jwt_headers,
                    json={"name": "Bench Key"},
                )
                assert key_res.status_code == 201
                api_headers = {"Authorization": f"Bearer {key_res.json()['plaintext_key']}"}

                conv_res = await client.post(
                    "/api/v1/conversations",
                    headers=jwt_headers,
                    json={"title": "Benchmark Session", "model_id": "nexora-fast"},
                )
                assert conv_res.status_code in (200, 201)
                conv_id = conv_res.json()["id"]

                # Warmup
                await client.get("/health")
                await client.get("/api/v1/models", headers=jwt_headers)

                concurrencies = [1, 10, 25]
                reqs_per_tier = 30

                # 1. GET /health
                results["endpoints"]["GET /health"] = {}
                for c in concurrencies:
                    results["endpoints"]["GET /health"][f"c={c}"] = await _run_concurrent_load(
                        lambda: _status(client.get("/health")),
                        total_requests=reqs_per_tier,
                        concurrency=c,
                    )

                # 2. GET /api/v1/models
                results["endpoints"]["GET /api/v1/models"] = {}
                for c in concurrencies:
                    results["endpoints"]["GET /api/v1/models"][f"c={c}"] = await _run_concurrent_load(
                        lambda: _status(client.get("/api/v1/models", headers=jwt_headers)),
                        total_requests=reqs_per_tier,
                        concurrency=c,
                    )

                # 3. POST /v1/embeddings
                results["endpoints"]["POST /v1/embeddings"] = {}
                for c in concurrencies:
                    results["endpoints"]["POST /v1/embeddings"][f"c={c}"] = await _run_concurrent_load(
                        lambda: _status(
                            client.post(
                                "/v1/embeddings",
                                headers=api_headers,
                                json={"model": "text-embedding-3-small", "input": "NEXORA production embedding benchmark"},
                            )
                        ),
                        total_requests=reqs_per_tier,
                        concurrency=c,
                    )

                # 4. POST /v1/chat/completions (non-streaming gateway completion)
                results["endpoints"]["POST /v1/chat/completions"] = {}
                for c in concurrencies:
                    results["endpoints"]["POST /v1/chat/completions"][f"c={c}"] = await _run_concurrent_load(
                        lambda: _status(
                            client.post(
                                "/v1/chat/completions",
                                headers=api_headers,
                                json={
                                    "model": "nexora-fast",
                                    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
                                    "max_tokens": 24,
                                },
                            )
                        ),
                        total_requests=20,
                        concurrency=c,
                    )

                # 5. POST /api/v1/messages SSE Streaming TTFT & End-to-End (10 sequential runs)
                ttfts: List[float] = []
                e2es: List[float] = []
                sse_errs = 0
                for i in range(10):
                    t0 = time.perf_counter()
                    ttft = None
                    async with client.stream(
                        "POST",
                        "/api/v1/messages",
                        headers=jwt_headers,
                        json={
                            "conversation_id": conv_id,
                            "content": f"Benchmark SSE stream iteration {i}",
                            "model": "nexora-fast",
                            "stream": True,
                        },
                    ) as resp:
                        if resp.status_code >= 400:
                            sse_errs += 1
                        async for line in resp.aiter_lines():
                            if line.startswith("data: ") and '"type": "token"' in line and ttft is None:
                                ttft = (time.perf_counter() - t0) * 1000.0
                        e2e = (time.perf_counter() - t0) * 1000.0
                        ttfts.append(ttft or e2e)
                        e2es.append(e2e)
                results["endpoints"]["POST /api/v1/messages (SSE stream)"] = {
                    "samples": 10,
                    "errors": sse_errs,
                    "ttft_ms": {
                        "min": round(min(ttfts), 2),
                        "p50": _percentile(sorted(ttfts), 50),
                        "p95": _percentile(sorted(ttfts), 95),
                        "mean": round(statistics.mean(ttfts), 2),
                    },
                    "e2e_ms": {
                        "min": round(min(e2es), 2),
                        "p50": _percentile(sorted(e2es), 50),
                        "p95": _percentile(sorted(e2es), 95),
                        "mean": round(statistics.mean(e2es), 2),
                    },
                }

            # 6. RAG Hybrid Retrieval & Document Parsing micro-benchmarks
            async with BenchSession() as session:
                u_res = await session.execute(
                    __import__("sqlalchemy").select(__import__("app.models.user", fromlist=["User"]).User)
                )
                user_obj = u_res.scalars().first()
                col = await rag_service.create_collection(session, user_obj.id, "Bench KB", "RAG Latency Benchmark")
                corpus = "\n\n".join(
                    [
                        f"Document chunk {i}: NEXORA distributed training uses PyTorch, PEFT LoRA, SafeTensors checksums, and hybrid BM25 + vector RRF retrieval."
                        for i in range(40)
                    ]
                )
                t_ingest0 = time.perf_counter()
                await rag_service.ingest_document(session, col.id, "bench_corpus.txt", corpus)
                ingest_ms = round((time.perf_counter() - t_ingest0) * 1000.0, 2)

                rag_lats: List[float] = []
                for _ in range(15):
                    tq0 = time.perf_counter()
                    hits = await rag_service.hybrid_search(session, user_obj.id, "SafeTensors LoRA hybrid RRF", collection_ids=[col.id], top_k=5)
                    rag_lats.append((time.perf_counter() - tq0) * 1000.0)
                    assert len(hits) > 0

                results["subsystems"]["rag_hybrid_search"] = {
                    "ingest_40_chunks_ms": ingest_ms,
                    "queries": len(rag_lats),
                    "mean_ms": round(statistics.mean(rag_lats), 3),
                    "p50_ms": _percentile(sorted(rag_lats), 50),
                    "p95_ms": _percentile(sorted(rag_lats), 95),
                }

            # Document Intelligence CSV Parse throughput (1,000 rows)
            csv_path = os.path.join(tmp_dir, "bench_1000_rows.csv")
            with open(csv_path, "w", encoding="utf-8") as cf:
                cf.write("id,model,latency_ms,tokens,tier\n")
                for idx in range(1000):
                    cf.write(f"{idx},nexora-flagship,{12.5 + (idx % 10)},{100 + idx},pro\n")

            doc_lats: List[float] = []
            for _ in range(10):
                td0 = time.perf_counter()
                parsed = document_intelligence_service.parse_file(csv_path)
                doc_lats.append((time.perf_counter() - td0) * 1000.0)
                assert len(parsed.tables) == 1 and len(parsed.tables[0].rows) == 1000
            results["subsystems"]["document_csv_1000_rows"] = {
                "runs": len(doc_lats),
                "mean_ms": round(statistics.mean(doc_lats), 3),
                "p95_ms": _percentile(sorted(doc_lats), 95),
                "rows_per_sec": round(1000.0 / (statistics.mean(doc_lats) / 1000.0), 1),
            }
            return results
        finally:
            await bench_engine.dispose()
            from app.core.database import engine as core_engine
            await core_engine.dispose()
            app.dependency_overrides.clear()


async def _status(coro) -> int:
    resp = await coro
    return resp.status_code


if __name__ == "__main__":
    output = asyncio.run(run_benchmarks())
    print(json.dumps(output, indent=2))

"""
Independent OpenAI-Compatible Inference Deployment & Commercial API Server.
Protects control-plane routes with RBAC (`require_lab_access`) and serves authenticated
`/v1/models`, `/v1/embeddings`, `/v1/chat/completions`, `/v1/completions`, and `/v1/health`
for both Lab checkpoint deployments and UnifiedModelGateway models with usage accounting.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthPrincipal, authenticate_api_principal, require_lab_access
from app.core.database import get_db
from app.lab.checkpoints.manager import CheckpointManager
from app.lab.inference.server import InferenceDeploymentManager, inference_manager
from app.lab.telemetry.monitor import HardwareTelemetryMonitor
from app.models.ecosystem import ApiUsageLog, PublishedModel
from app.models.lab import LabCheckpoint, LabInferenceDeployment
from app.services.billing_service import billing_service
from app.services.embedding.embedding_service import embedding_service
from app.services.llm.base import LLMMessage, LLMRequest
from app.services.llm.gateway import gateway
from app.services.model_registry.registry import model_registry

lab_deployments_router = APIRouter(
    prefix="/lab/deployments",
    tags=["Model Serving Deployments"],
    dependencies=[Depends(require_lab_access)],
)
openai_router = APIRouter(tags=["Independent OpenAI Inference Server"])


class DeployCheckpointRequest(BaseModel):
    model_alias: str
    checkpoint_id: str
    engine: str = "transformers"  # vllm, transformers, pytorch_native
    quantization: str = "none"  # none, fp16, bf16, int8_dynamic
    max_model_len: int = 2048
    max_concurrent_requests: int = 8
    gpu_memory_utilization: float = 0.85


class ChatMessageInput(BaseModel):
    role: str
    content: str


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessageInput]
    max_tokens: int = 64
    temperature: float = 0.7
    stream: bool = False


class OpenAICompletionRequest(BaseModel):
    model: str
    prompt: str
    max_tokens: int = 64
    temperature: float = 0.7


class OpenAIEmbeddingsRequest(BaseModel):
    model: str = "text-embedding-3-small"
    input: Union[str, List[str]]


async def _sync_registry_from_db(db: AsyncSession) -> None:
    """Keep active ModelRegistry synchronized with DB PublishedModel rows."""
    res = await db.execute(select(PublishedModel))
    rows = list(res.scalars().all())
    if not rows:
        return
    ckpt_ids = [r.checkpoint_id for r in rows if r.checkpoint_id]
    ckpt_paths: Dict[str, str] = {}
    if ckpt_ids:
        c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id.in_(ckpt_ids)))
        for c in c_res.scalars().all():
            ckpt_paths[c.id] = c.storage_path
    model_registry.sync_published_models(rows, ckpt_paths)


# --- Deployment Lifecycle Routes ---

@lab_deployments_router.get("")
async def list_deployments(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LabInferenceDeployment).order_by(desc(LabInferenceDeployment.created_at)))
    return {
        "engines": InferenceDeploymentManager.check_engine_capabilities(),
        "deployments": res.scalars().all(),
    }


@lab_deployments_router.post("", status_code=status.HTTP_201_CREATED)
async def deploy_validated_checkpoint(payload: DeployCheckpointRequest, db: AsyncSession = Depends(get_db)):
    """Deploys a validated checkpoint to an OpenAI-compatible serving endpoint."""
    c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == payload.checkpoint_id))
    ckpt = c_res.scalar_one_or_none()
    if not ckpt:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    val_report = CheckpointManager.validate_checkpoint(ckpt.storage_path, expected_sha256=ckpt.weights_sha256 or None)
    if not val_report["validated"]:
        raise HTTPException(
            status_code=400,
            detail=f"Refusing to deploy unvalidated checkpoint: {val_report.get('error')}",
        )
    ckpt.validated = True
    ckpt.validation_report = val_report

    existing_res = await db.execute(
        select(LabInferenceDeployment).where(LabInferenceDeployment.model_alias == payload.model_alias)
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Model alias '{payload.model_alias}' is already deployed")

    hw = HardwareTelemetryMonitor.get_system_telemetry()
    caps = InferenceDeploymentManager.check_engine_capabilities()
    effective_engine = payload.engine
    if payload.engine == "vllm" and not caps["vllm"]["ready"]:
        effective_engine = "transformers"

    load_info = inference_manager.load_deployment_runtime(
        model_alias=payload.model_alias,
        checkpoint_path=ckpt.storage_path,
        engine=effective_engine,
        quantization=payload.quantization,
    )
    if not load_info["loaded"]:
        raise HTTPException(status_code=400, detail="Failed to load checkpoint into inference runtime.")

    dep = LabInferenceDeployment(
        id=str(uuid.uuid4()),
        model_alias=payload.model_alias,
        checkpoint_id=ckpt.id,
        model_name=f"checkpoint-{ckpt.version}",
        engine=effective_engine,
        quantization=payload.quantization,
        device=hw["accelerator"],
        max_model_len=payload.max_model_len,
        max_concurrent_requests=payload.max_concurrent_requests,
        gpu_memory_utilization=payload.gpu_memory_utilization,
        status="healthy",
        last_health_check_at=datetime.now(timezone.utc),
    )
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    return dep


@lab_deployments_router.post("/{deployment_id}/stop")
async def stop_deployment(deployment_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LabInferenceDeployment).where(LabInferenceDeployment.id == deployment_id))
    dep = res.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    inference_manager.unload_deployment_runtime(dep.model_alias)
    dep.status = "stopped"
    await db.commit()
    await db.refresh(dep)
    return dep


# --- OpenAI-Compatible Serving Endpoints (/v1/models, /v1/embeddings, /v1/chat/completions, /v1/completions) ---

@openai_router.get("/v1/models")
async def openai_list_models(
    principal: AuthPrincipal = Depends(authenticate_api_principal),
    db: AsyncSession = Depends(get_db),
):
    await _sync_registry_from_db(db)
    res = await db.execute(
        select(LabInferenceDeployment).where(LabInferenceDeployment.status == "healthy")
    )
    deps = res.scalars().all()
    data = [
        {
            "id": d.model_alias,
            "object": "model",
            "created": int(d.created_at.timestamp()) if d.created_at else int(time.time()),
            "owned_by": "nexora-model-lab",
            "engine": d.engine,
            "quantization": d.quantization,
            "device": d.device,
            "checkpoint_id": d.checkpoint_id,
        }
        for d in deps
    ]
    seen = {item["id"] for item in data}
    for m in model_registry.list_models(include_inactive=False):
        if m.id not in seen:
            data.append(
                {
                    "id": m.id,
                    "object": "model",
                    "created": 1730000000,
                    "owned_by": f"nexora-{m.provider.value}",
                    "provider": m.provider.value,
                    "proprietary": m.is_proprietary,
                    "min_plan_tier": m.min_plan_tier,
                }
            )
    return {"object": "list", "data": data}


@openai_router.get("/v1/health")
async def openai_inference_health(db: AsyncSession = Depends(get_db)):
    hw = HardwareTelemetryMonitor.get_system_telemetry()
    res = await db.execute(select(LabInferenceDeployment))
    deps = res.scalars().all()
    return {
        "status": "healthy",
        "accelerator": hw["accelerator"],
        "gpu_available": hw["gpu_available"],
        "engines": InferenceDeploymentManager.check_engine_capabilities(),
        "active_deployments": sum(1 for d in deps if d.status == "healthy"),
        "total_requests_served": sum(d.requests_served for d in deps),
    }


@openai_router.post("/v1/embeddings")
async def openai_embeddings(
    payload: OpenAIEmbeddingsRequest,
    principal: AuthPrincipal = Depends(authenticate_api_principal),
    db: AsyncSession = Depends(get_db),
):
    """OpenAI-compatible `/v1/embeddings` endpoint powered by NEXORA EmbeddingService."""
    t0 = time.perf_counter()
    inputs = [payload.input] if isinstance(payload.input, str) else list(payload.input)
    if not inputs:
        raise HTTPException(status_code=400, detail="Input cannot be empty.")

    vectors = await embedding_service.get_batch_embeddings(inputs)
    total_tokens = sum(max(1, len(txt) // 4) for txt in inputs)
    cost = round((total_tokens / 1_000_000.0) * 0.02, 6)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    await billing_service.record_consumption(db, principal.user.id, total_tokens, requests_inc=1)
    if principal.api_key:
        principal.api_key.total_requests += 1
        principal.api_key.total_tokens += total_tokens
    db.add(
        ApiUsageLog(
            user_id=principal.user.id,
            api_key_id=principal.api_key.id if principal.api_key else None,
            endpoint="/v1/embeddings",
            method="POST",
            status_code=200,
            model=payload.model,
            provider="nexora-embeddings",
            prompt_tokens=total_tokens,
            completion_tokens=0,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
    )
    await db.commit()

    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": vec}
            for i, vec in enumerate(vectors)
        ],
        "model": payload.model,
        "usage": {
            "prompt_tokens": total_tokens,
            "total_tokens": total_tokens,
        },
    }


@openai_router.post("/v1/chat/completions")
async def openai_chat_completions(
    payload: OpenAIChatCompletionRequest,
    request: Request,
    principal: AuthPrincipal = Depends(authenticate_api_principal),
    db: AsyncSession = Depends(get_db),
):
    await _sync_registry_from_db(db)
    t0 = time.perf_counter()

    # Check deployed Lab checkpoint first
    res = await db.execute(
        select(LabInferenceDeployment).where(
            LabInferenceDeployment.model_alias == payload.model,
            LabInferenceDeployment.status == "healthy",
        )
    )
    dep = res.scalar_one_or_none()

    if dep:
        ckpt_path = None
        if dep.checkpoint_id:
            c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == dep.checkpoint_id))
            c_row = c_res.scalar_one_or_none()
            if c_row:
                ckpt_path = c_row.storage_path

        messages = [{"role": m.role, "content": m.content} for m in payload.messages]

        if payload.stream:
            dep.requests_served += 1
            dep.last_health_check_at = datetime.now(timezone.utc)
            if principal.api_key:
                principal.api_key.total_requests += 1
            db.add(
                ApiUsageLog(
                    user_id=principal.user.id,
                    api_key_id=principal.api_key.id if principal.api_key else None,
                    endpoint="/v1/chat/completions",
                    method="POST",
                    status_code=200,
                    model=dep.model_alias,
                    provider="nexora-lab-serving",
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                )
            )
            await db.commit()
            return StreamingResponse(
                inference_manager.stream_chat_completion(
                    model_alias=dep.model_alias,
                    checkpoint_path=ckpt_path,
                    messages=messages,
                    max_tokens=payload.max_tokens,
                    temperature=payload.temperature,
                    max_concurrent=dep.max_concurrent_requests,
                    quantization=dep.quantization,
                ),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no"},
            )

        dep.active_queue_depth += 1
        await db.commit()
        try:
            result = await inference_manager.generate_chat_completion(
                model_alias=dep.model_alias,
                checkpoint_path=ckpt_path,
                messages=messages,
                max_tokens=payload.max_tokens,
                temperature=payload.temperature,
                max_concurrent=dep.max_concurrent_requests,
                quantization=dep.quantization,
            )
            latency_ms = float(result["nexora_metrics"]["latency_ms"])
            pt = int(result["usage"]["prompt_tokens"])
            ct = int(result["usage"]["completion_tokens"])
            tt = pt + ct
            n = dep.requests_served
            dep.avg_latency_ms = round(((dep.avg_latency_ms * n) + latency_ms) / (n + 1), 2)
            dep.requests_served += 1
            dep.total_prompt_tokens += pt
            dep.total_completion_tokens += ct
            dep.last_health_check_at = datetime.now(timezone.utc)

            await billing_service.record_consumption(db, principal.user.id, tt, requests_inc=1)
            if principal.api_key:
                principal.api_key.total_requests += 1
                principal.api_key.total_tokens += tt
            db.add(
                ApiUsageLog(
                    user_id=principal.user.id,
                    api_key_id=principal.api_key.id if principal.api_key else None,
                    endpoint="/v1/chat/completions",
                    method="POST",
                    status_code=200,
                    model=dep.model_alias,
                    provider="nexora-lab-serving",
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=tt,
                    cost_usd=model_registry.calculate_cost(dep.model_alias, pt, ct),
                    latency_ms=latency_ms,
                )
            )
            return result
        finally:
            dep.active_queue_depth = max(0, dep.active_queue_depth - 1)
            await db.commit()

    # Path 2: Gateway model (published NEXORA proprietary / built-in / external model)
    model_desc = model_registry.get_model(payload.model)
    if not model_desc or model_desc.status.value != "active":
        raise HTTPException(
            status_code=404,
            detail=f"No active deployed or registered model found with id '{payload.model}'",
        )

    if principal.plan:
        permitted, reason = billing_service.check_model_permitted(
            principal.plan, principal.user.role, model_desc.id, model_desc.min_plan_tier
        )
        if not permitted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    llm_msgs = [LLMMessage(role=m.role, content=m.content) for m in payload.messages]
    llm_req = LLMRequest(
        messages=llm_msgs,
        model=model_desc.id,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
        stream=payload.stream,
        user_id=principal.user.id,
    )

    if payload.stream:
        async def _openai_sse():
            cid = f"chatcmpl-{uuid.uuid4().hex[:16]}"
            created = int(time.time())
            resolved_id = model_desc.id
            async for chunk in gateway.stream(llm_req):
                if chunk.resolved_model:
                    resolved_id = chunk.resolved_model
                if chunk.type in ("token", "reasoning") and chunk.content:
                    yield "data: " + json.dumps(
                        {
                            "id": cid,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": resolved_id,
                            "choices": [{"index": 0, "delta": {"content": chunk.content}, "finish_reason": None}],
                        }
                    ) + "\n\n"
                elif chunk.type == "done":
                    yield "data: " + json.dumps(
                        {
                            "id": cid,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": resolved_id,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        }
                    ) + "\n\n"
                    yield "data: [DONE]\n\n"

        if principal.api_key:
            principal.api_key.total_requests += 1
        db.add(
            ApiUsageLog(
                user_id=principal.user.id,
                api_key_id=principal.api_key.id if principal.api_key else None,
                endpoint="/v1/chat/completions",
                method="POST",
                status_code=200,
                model=model_desc.id,
                provider=model_desc.provider.value,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            )
        )
        await db.commit()
        return StreamingResponse(_openai_sse(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    resp = await gateway.generate(llm_req)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    await billing_service.record_consumption(db, principal.user.id, resp.usage.total_tokens, requests_inc=1)
    if principal.api_key:
        principal.api_key.total_requests += 1
        principal.api_key.total_tokens += resp.usage.total_tokens
    db.add(
        ApiUsageLog(
            user_id=principal.user.id,
            api_key_id=principal.api_key.id if principal.api_key else None,
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=200,
            model=resp.model,
            provider=resp.actual_provider,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            cost_usd=resp.usage.estimated_cost_usd,
            latency_ms=latency_ms,
        )
    )
    await db.commit()

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:16]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": resp.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": resp.content},
                "finish_reason": resp.finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        },
        "nexora_attribution": {
            "requested_model": payload.model,
            "resolved_model": resp.model,
            "actual_provider": resp.actual_provider,
            "fallback_used": resp.fallback_used,
            "fallback_from_model": resp.fallback_from_model,
            "cost_usd": resp.usage.estimated_cost_usd,
        },
    }


@openai_router.post("/v1/completions")
async def openai_completions(
    payload: OpenAICompletionRequest,
    request: Request,
    principal: AuthPrincipal = Depends(authenticate_api_principal),
    db: AsyncSession = Depends(get_db),
):
    chat_req = OpenAIChatCompletionRequest(
        model=payload.model,
        messages=[ChatMessageInput(role="user", content=payload.prompt)],
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
        stream=False,
    )
    chat_res = await openai_chat_completions(chat_req, request, principal, db)
    text = chat_res["choices"][0]["message"]["content"]
    return {
        "id": chat_res["id"].replace("chatcmpl-", "cmpl-"),
        "object": "text_completion",
        "created": chat_res["created"],
        "model": chat_res["model"],
        "choices": [{"text": text, "index": 0, "finish_reason": "stop"}],
        "usage": chat_res["usage"],
    }

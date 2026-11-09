"""
Independent OpenAI-Compatible Inference Deployment & Serving API.
Provides deployment lifecycle management (requiring checkpoint validation),
health checks, concurrency queuing, token usage accounting, and standard
OpenAI `/v1/models` and `/v1/chat/completions` endpoints.
"""
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.lab.checkpoints.manager import CheckpointManager
from app.lab.inference.server import InferenceDeploymentManager, inference_manager
from app.lab.telemetry.monitor import HardwareTelemetryMonitor
from app.models.lab import LabCheckpoint, LabInferenceDeployment

# Control-plane routes under /api/v1/lab/deployments + Serving routes under /api/v1/inference
lab_deployments_router = APIRouter(prefix="/lab/deployments", tags=["Model Serving Deployments"])
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
    """
    Deploys a validated checkpoint to an OpenAI-compatible serving endpoint.
    Rejects unvalidated or missing checkpoints strictly.
    """
    c_res = await db.execute(select(LabCheckpoint).where(LabCheckpoint.id == payload.checkpoint_id))
    ckpt = c_res.scalar_one_or_none()
    if not ckpt:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    # Enforce validation gate before deployment
    val_report = CheckpointManager.validate_checkpoint(ckpt.storage_path, expected_sha256=ckpt.weights_sha256 or None)
    if not val_report["validated"]:
        raise HTTPException(
            status_code=400,
            detail=f"Refusing to deploy unvalidated checkpoint: {val_report.get('error')}",
        )
    ckpt.validated = True
    ckpt.validation_report = val_report

    # Check alias conflict
    existing_res = await db.execute(
        select(LabInferenceDeployment).where(LabInferenceDeployment.model_alias == payload.model_alias)
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Model alias '{payload.model_alias}' is already deployed")

    hw = HardwareTelemetryMonitor.get_system_telemetry()
    caps = InferenceDeploymentManager.check_engine_capabilities()
    effective_engine = payload.engine
    if payload.engine == "vllm" and not caps["vllm"]["ready"]:
        # Graceful explicit downgrade when CUDA/vLLM isn't present on CPU host
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


# --- OpenAI-Compatible Serving Endpoints (/v1/models, /v1/chat/completions, /v1/completions) ---

@openai_router.get("/v1/models")
async def openai_list_models(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(LabInferenceDeployment).where(LabInferenceDeployment.status == "healthy")
    )
    deps = res.scalars().all()
    return {
        "object": "list",
        "data": [
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
        ],
    }


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


@openai_router.post("/v1/chat/completions")
async def openai_chat_completions(payload: OpenAIChatCompletionRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(LabInferenceDeployment).where(
            LabInferenceDeployment.model_alias == payload.model,
            LabInferenceDeployment.status == "healthy",
        )
    )
    dep = res.scalar_one_or_none()
    if not dep:
        raise HTTPException(
            status_code=404,
            detail=f"No healthy deployed model found with alias '{payload.model}'",
        )

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
        n = dep.requests_served
        dep.avg_latency_ms = round(((dep.avg_latency_ms * n) + latency_ms) / (n + 1), 2)
        dep.requests_served += 1
        dep.total_prompt_tokens += int(result["usage"]["prompt_tokens"])
        dep.total_completion_tokens += int(result["usage"]["completion_tokens"])
        dep.last_health_check_at = datetime.now(timezone.utc)
        return result
    finally:
        dep.active_queue_depth = max(0, dep.active_queue_depth - 1)
        await db.commit()


@openai_router.post("/v1/completions")
async def openai_completions(payload: OpenAICompletionRequest, db: AsyncSession = Depends(get_db)):
    chat_req = OpenAIChatCompletionRequest(
        model=payload.model,
        messages=[ChatMessageInput(role="user", content=payload.prompt)],
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
        stream=False,
    )
    chat_res = await openai_chat_completions(chat_req, db)
    text = chat_res["choices"][0]["message"]["content"]
    return {
        "id": chat_res["id"].replace("chatcmpl-", "cmpl-"),
        "object": "text_completion",
        "created": chat_res["created"],
        "model": payload.model,
        "choices": [{"text": text, "index": 0, "finish_reason": "stop"}],
        "usage": chat_res["usage"],
    }

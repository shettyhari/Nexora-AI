import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security_guards import resolve_safe_file_path
from app.models.attachment import Attachment
from app.models.media_job import MediaJob
from app.models.user import User
from app.services.multimodal.image_service import image_intelligence_service
from app.services.multimodal.video_service import video_intelligence_service

router = APIRouter(prefix="/multimodal", tags=["Multimodal Intelligence"])


class ImageAnalyzeRequest(BaseModel):
    attachment_id: Optional[str] = None
    file_path: Optional[str] = None
    prompt: str = "Analyze this visual in detail."
    analysis_type: str = "general"  # general, ocr, chart, diagram, screenshot
    model: str = "nexora-vision"


class ImageGenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"


class VideoAnalyzeRequest(BaseModel):
    attachment_id: Optional[str] = None
    file_path: Optional[str] = None
    query: Optional[str] = None


async def _resolve_file(file_path: Optional[str], attachment_id: Optional[str], user_id: str, db: AsyncSession) -> str:
    return await resolve_safe_file_path(
        file_path, attachment_id, user_id, db, endpoint="/api/v1/multimodal"
    )


@router.post("/image/analyze")
async def analyze_image(
    req: ImageAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Analyze an image using vision AI for OCR, chart, diagram, or screenshot interpretation."""
    path = await _resolve_file(req.file_path, req.attachment_id, current_user.id, db)
    try:
        result = await image_intelligence_service.analyze_image(
            file_path=path,
            prompt=req.prompt,
            analysis_type=req.analysis_type,
            model=req.model
        )
        return {
            "success": True,
            "data": result.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/image/generate")
async def generate_image(
    req: ImageGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate high-fidelity imagery via configured image generation provider."""
    try:
        result = await image_intelligence_service.generate_image(
            prompt=req.prompt,
            size=req.size,
            quality=req.quality
        )
        return {
            "success": True,
            "data": result.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/video/analyze")
async def analyze_video(
    req: VideoAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Analyze video synchronously for immediate scene segmentation and timestamps."""
    path = await _resolve_file(req.file_path, req.attachment_id, current_user.id, db)
    try:
        result = await video_intelligence_service.analyze_video(
            file_path=path,
            query=req.query
        )
        return {
            "success": True,
            "data": result.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/video/jobs")
async def create_async_video_job(
    req: VideoAnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit asynchronous video processing job for large media files."""
    path = await _resolve_file(req.file_path, req.attachment_id, current_user.id, db)
    job_id = str(uuid.uuid4())
    file_name = os.path.basename(path)

    job = MediaJob(
        id=job_id,
        user_id=current_user.id,
        media_type="video",
        status="queued",
        file_path=path,
        file_name=file_name,
        progress=0.0
    )
    db.add(job)
    await db.commit()

    # Background task handler
    async def process_job(jid: str, fpath: str, q: Optional[str]):
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            try:
                # Update status to processing
                q_job = select(MediaJob).where(MediaJob.id == jid)
                res = await session.execute(q_job)
                curr_job = res.scalar_one_or_none()
                if curr_job:
                    curr_job.status = "processing"
                    curr_job.progress = 0.2
                    await session.commit()

                analysis = await video_intelligence_service.analyze_video(fpath, query=q)

                curr_job.status = "completed"
                curr_job.progress = 1.0
                curr_job.result_json = analysis.json()
                await session.commit()
            except Exception as ex:
                if curr_job:
                    curr_job.status = "failed"
                    curr_job.error = str(ex)
                    await session.commit()

    background_tasks.add_task(process_job, job_id, path, req.query)

    return {
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "message": "Async video analysis job created."
    }


@router.get("/video/jobs/{job_id}")
async def get_video_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve status and results of an asynchronous video processing job."""
    q = select(MediaJob).where(MediaJob.id == job_id, MediaJob.user_id == current_user.id)
    res = await db.execute(q)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media job not found.")

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "media_type": job.media_type,
        "result": job.result_json,
        "error": job.error,
        "created_at": job.created_at.isoformat()
    }

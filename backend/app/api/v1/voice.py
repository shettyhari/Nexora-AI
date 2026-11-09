import os
import tempfile
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.security_guards import sanitize_filename
from app.models.user import User
from app.services.voice.voice_service import voice_intelligence_service

router = APIRouter(prefix="/voice", tags=["Voice Intelligence"])
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "webm", "flac"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class SynthesizeRequest(BaseModel):
    text: str
    voice: Optional[str] = "alloy"
    speed: float = 1.0


class AudioSummarizeRequest(BaseModel):
    transcription: str


@router.post("/transcribe")
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Transcribe spoken audio to text using configured speech-to-text provider."""
    safe_name = sanitize_filename(file.filename or "audio.mp3")
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "mp3"
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}."
        )
    content = await file.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds maximum size of 25MB."
        )

    suffix = f".{ext}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        tmp.write(content)

    try:
        result = await voice_intelligence_service.transcribe_audio(tmp_path, language=language)
        return {
            "success": True,
            "data": result.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/synthesize")
async def synthesize_speech(
    req: SynthesizeRequest,
    current_user: User = Depends(get_current_user)
):
    """Synthesize text into playable natural speech audio stream."""
    if not req.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text cannot be empty.")

    try:
        synth = await voice_intelligence_service.synthesize_speech(
            text=req.text,
            voice=req.voice,
            speed=req.speed
        )
        return Response(
            content=synth.audio_bytes,
            media_type=synth.media_type,
            headers={
                "Content-Disposition": 'inline; filename="synthesized_speech.wav"',
                "X-NEXORA-Voice": synth.voice,
                "X-NEXORA-Duration": str(synth.duration_seconds)
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/summarize")
async def summarize_speech(
    req: AudioSummarizeRequest,
    current_user: User = Depends(get_current_user)
):
    """Summarize spoken transcription into key points and actionable items."""
    try:
        summary = await voice_intelligence_service.summarize_audio(req.transcription)
        return {
            "success": True,
            "data": summary.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

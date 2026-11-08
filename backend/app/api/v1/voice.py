import os
import tempfile
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.voice.voice_service import voice_intelligence_service

router = APIRouter(prefix="/voice", tags=["Voice Intelligence"])


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
    suffix = f".{file.filename.split('.')[-1]}" if file.filename and "." in file.filename else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        content = await file.read()
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

import os
import tempfile
import pytest
from app.services.voice.voice_service import voice_intelligence_service


@pytest.mark.asyncio
async def test_speech_synthesis_audio_bytes():
    text = "Welcome to NEXORA AI multimodal and agentic intelligence."
    res = await voice_intelligence_service.synthesize_speech(text, voice="alloy")
    assert res.audio_bytes is not None
    assert len(res.audio_bytes) > 1000  # Valid non-empty audio binary payload
    assert res.media_type in ("audio/mpeg", "audio/wav")
    assert res.duration_seconds > 0


@pytest.mark.asyncio
async def test_audio_transcription():
    # Create test audio file container
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(b"\xFF\xFB\x90\x00" * 200)
        tmp_audio = f.name

    try:
        res = await voice_intelligence_service.transcribe_audio(tmp_audio)
        assert res.text != ""
        assert res.duration_seconds > 0
        assert res.confidence > 0.9
    finally:
        if os.path.exists(tmp_audio):
            os.remove(tmp_audio)


@pytest.mark.asyncio
async def test_audio_summarization():
    spoken_text = (
        "During our team sync, we decided to migrate all LLM calls through the Unified Gateway. "
        "Hari will deploy the FastAPI backend. Sarah will configure the React frontend components. "
        "Next sprint review is scheduled for Monday morning."
    )
    summary = await voice_intelligence_service.summarize_audio(spoken_text)
    assert summary.summary != ""
    assert len(summary.key_points) > 0
    assert len(summary.action_items) > 0

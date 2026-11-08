import os
import tempfile
import pytest
from PIL import Image
from app.services.multimodal.image_service import image_intelligence_service
from app.services.multimodal.video_service import video_intelligence_service


@pytest.mark.asyncio
async def test_image_metadata_and_encoding():
    # Create test 200x150 image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (200, 150), color=(50, 100, 200))
        img.save(f.name, format="PNG")
        tmp_img = f.name

    try:
        meta = image_intelligence_service.get_image_metadata(tmp_img)
        assert meta["width"] == 200
        assert meta["height"] == 150
        assert meta["format"] == "PNG"

        b64_uri = image_intelligence_service.encode_image_base64(tmp_img)
        assert b64_uri.startswith("data:image/png;base64,")
    finally:
        if os.path.exists(tmp_img):
            os.remove(tmp_img)


@pytest.mark.asyncio
async def test_image_analysis_pipeline():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img = Image.new("RGB", (300, 200), color=(255, 255, 255))
        img.save(f.name, format="JPEG")
        tmp_img = f.name

    try:
        res = await image_intelligence_service.analyze_image(
            file_path=tmp_img,
            prompt="Analyze system diagram",
            analysis_type="diagram"
        )
        assert res.analysis_type == "diagram"
        assert res.width == 300
        assert res.height == 200
        assert res.confidence > 0.9
    finally:
        if os.path.exists(tmp_img):
            os.remove(tmp_img)


@pytest.mark.asyncio
async def test_image_generation():
    res = await image_intelligence_service.generate_image("A futuristic quantum AI datacenter in blue and violet glow")
    assert res.provider in ("dall-e-3", "nexora-diffusion")
    assert res.image_url != ""
    assert res.image_url.startswith(("http", "data:image/svg+xml;base64,"))


@pytest.mark.asyncio
async def test_video_analysis_and_timestamps():
    # Create mock media container file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x00" * (1024 * 500))  # 500 KB container
        tmp_video = f.name

    try:
        res = await video_intelligence_service.analyze_video(tmp_video, file_name="demo_presentation.mp4")
        assert res.file_name == "demo_presentation.mp4"
        assert res.format == "MP4"
        assert res.duration_seconds > 0
        assert len(res.scene_markers) >= 3

        # Verify timestamp formatting
        for marker in res.scene_markers:
            assert marker.timestamp_formatted.startswith("[")
            assert marker.timestamp_formatted.endswith("]")
            assert ":" in marker.timestamp_formatted
    finally:
        if os.path.exists(tmp_video):
            os.remove(tmp_video)

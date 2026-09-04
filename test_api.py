from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from src.api.main import app


client = TestClient(app)


def create_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (40, 20), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_inspect_image_endpoint():
    response = client.post(
        "/images/inspect",
        files={"file": ("map.png", create_png(), "image/png")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["filename"] == "map.png"
    assert result["format"] == "PNG"
    assert result["width"] == 40
    assert result["height"] == 20
    assert result["status"] == "accepted"


def test_inspect_rejects_unsupported_extension():
    response = client.post(
        "/images/inspect",
        files={"file": ("document.pdf", b"not a PDF", "application/pdf")},
    )

    assert response.status_code == 415


def test_analyze_image_endpoint(
    monkeypatch,
):
    def fake_pipeline(filename, content):
        return {
            "filename": filename,
            "status": "completed",
            "elements": [
                {
                    "element": "title",
                    "present": False,
                    "confidence": None,
                    "location": None,
                },
                {
                    "element": "legend",
                    "present": True,
                    "confidence": None,
                    "location": None,
                },
                {
                    "element": "scale",
                    "present": True,
                    "confidence": None,
                    "location": None,
                },
                {
                    "element": "north_arrow",
                    "present": True,
                    "confidence": None,
                    "location": None,
                },
            ],
            "issues": [
                {
                    "error_type": "missing_title",
                    "severity": "warning",
                    "message": (
                        "The map does not contain "
                        "a detectable title."
                    ),
                    "confidence": None,
                }
            ],
        }

    monkeypatch.setattr(
        "src.api.main.run_vision_pipeline",
        fake_pipeline,
    )

    response = client.post(
        "/images/analyze",
        files={
            "file": (
                "map.png",
                create_png(),
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["filename"] == "map.png"
    assert result["status"] == "completed"
    assert len(result["elements"]) == 4
    assert result["issues"][0]["error_type"] == (
        "missing_title"
    )
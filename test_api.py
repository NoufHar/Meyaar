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

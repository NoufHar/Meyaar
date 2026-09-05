from fastapi.testclient import TestClient

from src.api.main import app
from src.api.vector_pipeline import (
    InvalidVectorFileError,
)


client = TestClient(app)


def successful_vector_result(filename):
    return {
        "filename": filename,
        "status": "completed",
        "layer_name": "roads",
        "run_id": (
            "11111111-1111-1111-1111-111111111111"
        ),
        "insertion": {
            "status": "success",
            "inserted_rows": 10,
        },
        "validation": {
            "status": "success",
            "total_errors": 2,
        },
        "analysis": {
            "status": "completed",
            "analyses": [],
        },
    }


def test_process_vector_endpoint(
    monkeypatch,
):
    def fake_process(
        filename,
        content,
        requested_layer,
    ):
        assert content == b"vector-data"
        assert requested_layer == "roads"

        return successful_vector_result(
            filename
        )

    monkeypatch.setattr(
        "src.api.main.process_vector_upload",
        fake_process,
    )

    response = client.post(
        "/vectors/process",
        files={
            "file": (
                "roads.geojson",
                b"vector-data",
                "application/geo+json",
            )
        },
        data={
            "layer_type": "roads",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["filename"] == (
        "roads.geojson"
    )
    assert result["layer_name"] == "roads"
    assert result["validation"][
        "total_errors"
    ] == 2


def test_process_vector_rejects_empty_file():
    response = client.post(
        "/vectors/process",
        files={
            "file": (
                "roads.geojson",
                b"",
                "application/geo+json",
            )
        },
        data={
            "layer_type": "roads",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file is empty."
    }


def test_process_vector_returns_invalid_error(
    monkeypatch,
):
    def fake_process(
        filename,
        content,
        requested_layer,
    ):
        raise InvalidVectorFileError(
            "Unsupported vector file."
        )

    monkeypatch.setattr(
        "src.api.main.process_vector_upload",
        fake_process,
    )

    response = client.post(
        "/vectors/process",
        files={
            "file": (
                "data.txt",
                b"invalid",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unsupported vector file."
    }
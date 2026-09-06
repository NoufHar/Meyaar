from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 7,
    "medium": 4,
    "warning": 2,
    "low": 2,
}


def compliance_score(errors: list[dict], item_count: int) -> float:
    """Return a transparent 0-100 internal quality score."""
    weighted = sum(
        SEVERITY_WEIGHTS.get(str(item.get("severity", "")).lower(), 2)
        for item in errors
    )
    capacity = max(item_count, 1) * 10
    return round(max(0.0, 100.0 - min(100.0, weighted / capacity * 100.0)), 1)


def compliance_score_from_summary(summary: list[dict], item_count: int) -> float:
    weighted = sum(
        SEVERITY_WEIGHTS.get(str(row.get("severity", "")).lower(), 2)
        * int(row.get("errors_found", row.get("findings", 0)) or 0)
        for row in summary
    )
    capacity = max(item_count, 1) * 10
    return round(max(0.0, 100.0 - min(100.0, weighted / capacity * 100.0)), 1)


def inspect_image_quality(content: bytes) -> dict[str, Any]:
    with Image.open(BytesIO(content)) as image:
        gray = np.asarray(image.convert("L"), dtype=np.float32)

    brightness = float(gray.mean())
    contrast = float(gray.std())
    laplacian = (
        -4 * gray
        + np.roll(gray, 1, axis=0)
        + np.roll(gray, -1, axis=0)
        + np.roll(gray, 1, axis=1)
        + np.roll(gray, -1, axis=1)
    )
    sharpness = float(laplacian[1:-1, 1:-1].var()) if min(gray.shape) > 2 else 0.0
    dynamic_range = float(gray.max() - gray.min())

    checks = {
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "sharpness": round(sharpness, 2),
        "dynamic_range": round(dynamic_range, 2),
    }
    issues: list[dict] = []
    if dynamic_range < 3 or contrast < 1.5:
        issues.append({"error_type": "empty_or_uniform_image", "severity": "high", "message": "The image contains almost no visual variation.", "confidence": None})
    if brightness < 40:
        issues.append({"error_type": "image_too_dark", "severity": "warning", "message": "The image brightness is unusually low.", "confidence": None})
    if contrast < 20:
        issues.append({"error_type": "low_contrast", "severity": "warning", "message": "The image has low contrast and may be difficult to interpret.", "confidence": None})
    if sharpness < 35:
        issues.append({"error_type": "possible_blur", "severity": "warning", "message": "The image may be blurred or lack sufficient edge detail.", "confidence": None})
    return {"metrics": checks, "issues": issues}


def inspect_geotiff(content: bytes, filename: str) -> dict[str, Any] | None:
    if Path(filename).suffix.lower() not in {".tif", ".tiff"}:
        return None
    try:
        from rasterio.io import MemoryFile
    except ImportError:
        return {"available": False, "message": "Install rasterio to read GeoTIFF metadata."}

    try:
        with MemoryFile(content) as memory_file, memory_file.open() as dataset:
            bounds = dataset.bounds
            nodata_ratio = None
            if dataset.nodata is not None:
                mask = dataset.dataset_mask()
                nodata_ratio = round(float((mask == 0).mean() * 100), 2)
            return {
                "available": True,
                "crs": dataset.crs.to_string() if dataset.crs else None,
                "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                "pixel_size": [abs(dataset.transform.a), abs(dataset.transform.e)],
                "bands": dataset.count,
                "dtype": list(dataset.dtypes),
                "nodata": dataset.nodata,
                "nodata_ratio": nodata_ratio,
                "width": dataset.width,
                "height": dataset.height,
                "transform": list(dataset.transform)[:6],
            }
    except Exception as error:
        return {"available": False, "message": f"GeoTIFF metadata could not be read: {error}"}

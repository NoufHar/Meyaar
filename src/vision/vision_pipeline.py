from io import BytesIO

from PIL import Image

from src.api.schemas import VisionAnalysisResponse
from src.vision.image_preprocessor import preprocess_image
from src.vision.vision_model import analyze_image
from src.vision.vision_model import VisionModelNotConfiguredError
from src.quality import compliance_score, inspect_geotiff, inspect_image_quality


def run_vision_pipeline(
    filename: str,
    content: bytes,
) -> VisionAnalysisResponse:
    """
    Open the image, prepare it, run Moondream,
    then return a standardized result.
    """
    with Image.open(BytesIO(content)) as image:
        prepared_image = preprocess_image(image)

    quality = inspect_image_quality(content)
    geotiff = inspect_geotiff(content, filename)
    try:
        model_result = analyze_image(prepared_image)
        model_status = "completed"
    except VisionModelNotConfiguredError:
        model_result = {"elements": [], "issues": []}
        model_status = "not_configured"

    issues = [*quality["issues"], *model_result.get("issues", [])]
    if geotiff and not geotiff.get("crs"):
        issues.append({"error_type": "missing_crs", "severity": "high", "message": "The GeoTIFF does not define a coordinate reference system.", "confidence": None})
    if geotiff and geotiff.get("nodata_ratio") is not None and geotiff["nodata_ratio"] > 30:
        issues.append({"error_type": "high_nodata_ratio", "severity": "warning", "message": f"NoData covers {geotiff['nodata_ratio']}% of the GeoTIFF.", "confidence": None})

    return VisionAnalysisResponse(
        filename=filename,
        elements=model_result.get("elements", []),
        issues=issues,
        quality_checks=quality["metrics"],
        geotiff=geotiff,
        compliance_score=compliance_score(issues, max(len(model_result.get("elements", [])), 4)),
        model_status=model_status,
    )

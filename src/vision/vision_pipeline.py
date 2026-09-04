from io import BytesIO

from PIL import Image

from src.api.schemas import VisionAnalysisResponse
from src.vision.image_preprocessor import preprocess_image
from src.vision.vision_model import analyze_image


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

    model_result = analyze_image(prepared_image)

    return VisionAnalysisResponse(
        filename=filename,
        elements=model_result.get("elements", []),
        issues=model_result.get("issues", []),
    )
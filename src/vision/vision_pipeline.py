from io import BytesIO
from PIL import Image
from src.api.schemas import VisionAnalysisResponse
from src.vision.image_preprocessor import preprocess_image
from src.vision.vision_model import analyze_image


def normalize_vision_findings(issues:list)->list[dict]:
    return [
        {
            "finding_id":f"IMG{i:03}",
            "source_type":"image",
            "rule_id":None,
            "feature_id":None,
            "error_type":issue.get("error_type","unknown"),
            "severity":issue.get("severity","warning"),
            "status":"confirmed",
            "message":issue.get("message",""),
            "recommendation":None,
            "confidence":issue.get("confidence"),
            "location":None,
            "measurements":[],
        }
        for i,issue in enumerate(issues,1)
    ]


def run_vision_pipeline(filename:str,content:bytes)->VisionAnalysisResponse:
    with Image.open(BytesIO(content)) as image:
        prepared_image=preprocess_image(image)

    model_result=analyze_image(prepared_image)

    return VisionAnalysisResponse(
        filename=filename,
        elements=model_result.get("elements",[]),
        issues=model_result.get("issues",[]),
    )
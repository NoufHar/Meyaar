from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.reporting.report_generator import (
    create_pdf,
    generate_report_content,
)
from src.voice.voice_summary import create_audio_summary
from src.notifications.telegram import (
    send_document,
    send_voice,
)

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from src.api.schemas import (
    ImageInspectionResponse,
    VectorProcessingResponse,
    VisionAnalysisResponse,
)

from src.vision.image_loader import InvalidImageError, inspect_image

from src.vision.vision_model import (
    VisionModelNotConfiguredError,
    VisionModelServiceError,
)

from src.vision.vision_pipeline import run_vision_pipeline

from agent.api.router import router as analysis_router

from src.api.vector_pipeline import (
    InvalidVectorFileError,
    VectorProcessingError,
    process_vector_upload,
)


app = FastAPI(
    title="Meyaar Backend API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    analysis_router,
    prefix="/api",
)

MAX_IMAGE_SIZE = 25 * 1024 * 1024

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
}


@app.get("/health")
def health():
    return {"status": "healthy"}

class VoiceSummaryRequest(BaseModel):
    dataset: dict
    validation: dict
    quality_summary: dict
    report: dict


@app.post("/voice/summary")
def generate_voice_summary(payload: VoiceSummaryRequest):
    try:
        result = create_audio_summary(
            dataset=payload.dataset,
            validation=payload.validation,
            quality_summary=payload.quality_summary,
            report=payload.report,
            output_path="outputs/MEYAAR_API_Summary.mp3",
        )

        # Send generated MP3 to Telegram
        send_voice(
            result["audio_path"],
            caption="Meyaar Analysis Summary",
        )

        return {
            **result,
            "telegram_sent": True,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

@app.post("/images/inspect", response_model=ImageInspectionResponse)
async def inspect_uploaded_image(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: JPG, JPEG, PNG, TIF, and TIFF.",
        )

    content = await file.read(MAX_IMAGE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 25 MB limit.",
        )

    try:
        metadata = inspect_image(content)
    except InvalidImageError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return ImageInspectionResponse(
        filename=filename,
        size_bytes=len(content),
        **metadata,
    )



@app.post("/images/analyze", response_model=VisionAnalysisResponse)
async def analyze_uploaded_image(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: JPG, JPEG, PNG, TIF, and TIFF.",
        )

    content = await file.read(MAX_IMAGE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 25 MB limit.",
        )

    try:
        inspect_image(content)
        return run_vision_pipeline(filename, content)

    except InvalidImageError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except VisionModelNotConfiguredError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except VisionModelServiceError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error



MAX_VECTOR_SIZE = 100 * 1024 * 1024


@app.post(
    "/vectors/process",
    response_model=VectorProcessingResponse,
)
async def process_uploaded_vector(
    file: UploadFile = File(...),
    layer_type: str | None = Form(None),
):
    filename = file.filename or ""

    content = await file.read(
        MAX_VECTOR_SIZE + 1
    )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_VECTOR_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "The vector file exceeds "
                "the 100 MB limit."
            ),
        )

    try:
        return process_vector_upload(
            filename=filename,
            content=content,
            requested_layer=layer_type,
        )

    except InvalidVectorFileError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except VectorProcessingError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
class ReportGenerationRequest(BaseModel):
    dataset: dict
    validation: dict


@app.post("/reports/generate")
def generate_report(payload: ReportGenerationRequest):
    try:
        # 1. Generate report narrative
        report = generate_report_content(
            dataset=payload.dataset,
            validation=payload.validation,
        )

        # 2. Generate PDF
        pdf_path = create_pdf(
            dataset=payload.dataset,
            validation=payload.validation,
            report=report,
            output_path="outputs/MEYAAR_Report.pdf",
        )

        # 3. Generate audio summary
        audio_result = create_audio_summary(
            dataset=payload.dataset,
            validation=payload.validation,
            quality_summary={
                "total_findings": payload.validation.get(
                    "total_findings",
                    payload.validation.get("total_errors", 0),
                )
            },
            report=report,
            output_path="outputs/MEYAAR_Summary.mp3",
        )

        # 4. Send PDF to Telegram
        send_document(
            pdf_path,
            caption="Meyaar Quality Assessment Report",
        )

        # 5. Send audio to Telegram
        send_voice(
            audio_result["audio_path"],
            caption="Meyaar Audio Summary",
        )

        return {
            "status": "success",
            "report_path": pdf_path,
            "audio_path": audio_result["audio_path"],
            "telegram_sent": True,
            "report": report,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
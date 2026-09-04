from pathlib import Path

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
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from src.api.schemas import ImageInspectionResponse
from src.vision.image_loader import InvalidImageError, inspect_image


app = FastAPI(
    title="Meyaar Backend API",
    version="0.1.0",
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
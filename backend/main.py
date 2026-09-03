from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(
    title="Meyaar API",
    version="0.1.0",
)

SUPPORTED_FILES = {
    ".geojson": "vector",
    ".gpkg": "vector",
    ".zip": "vector",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


@app.get("/")
def root():
    return {"message": "Meyaar Backend is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/uploads/inspect")
async def inspect_upload(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_FILES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type",
        )

    content = await file.read()
    size = len(content)

    if size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 25 MB limit",
        )

    return {
        "filename": filename,
        "extension": extension,
        "size_bytes": size,
        "track": SUPPORTED_FILES[extension],
        "status": "accepted",
    }
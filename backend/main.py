from fastapi import FastAPI

app = FastAPI(
    title="Meyaar API",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"message": "Meyaar is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
from pathlib import Path
from uuid import uuid4
from src.history.routes import router as history_router
from fastapi import Depends,FastAPI,File,Form,HTTPException,UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agent.api.router import router as analysis_router
from src.admin.routes import router as admin_router
from src.api.result_adapter import build_reporting_input
from src.api.routing import IMAGE_EXTENSIONS,detect_input_type
from src.api.schemas import (
    ImageInspectionResponse,
    UnifiedInspectionResponse,
    VectorProcessingResponse,
    VisionAnalysisResponse,
)
from src.api.vector_pipeline import (
    InvalidVectorFileError,
    VectorProcessingError,
    process_vector_upload,
)
from src.auth.dependencies import get_current_user
from src.auth.routes import router as auth_router
from src.database.database import SessionLocal
from src.database.models import Analysis,Finding,Report,User
from src.notifications.email import send_analysis_email
from src.reporting.final_outputs import generate_all_outputs
from src.reporting.report_generator import create_pdf,generate_report_content
from src.vision.image_loader import InvalidImageError,inspect_image
from src.vision.vision_model import (
    VisionModelNotConfiguredError,
    VisionModelServiceError,
)
from src.vision.vision_pipeline import normalize_vision_findings,run_vision_pipeline
from src.voice.voice_summary import create_audio_summary


app=FastAPI(
    title="Meyaar Backend API",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(history_router)
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

MAX_IMAGE_SIZE=25*1024*1024
MAX_VECTOR_SIZE=100*1024*1024


class VoiceSummaryRequest(BaseModel):
    dataset:dict
    validation:dict
    quality_summary:dict
    report:dict


class ReportGenerationRequest(BaseModel):
    dataset:dict
    validation:dict


def save_inspection(user_id:int,result:dict)->int:
    db=SessionLocal()

    try:
        analysis=Analysis(
            user_id=user_id,
            run_id=str(result["run_id"]),
            filename=result["filename"],
            input_type=result["input_type"],
            layer_type=result.get("layer_type"),
            status=result["status"],
            total_findings=len(result.get("findings",[])),
        )

        db.add(analysis)
        db.flush()

        for item in result.get("findings",[]):
            finding=Finding(
                analysis_id=analysis.id,
                finding_id=item.get("finding_id"),
                rule_id=item.get("rule_id"),
                feature_id=item.get("feature_id"),
                error_type=item.get("error_type","unknown"),
                severity=item.get("severity"),
                status=item.get("status"),
                message=item.get("message"),
                recommendation=item.get("recommendation"),
                confidence=item.get("confidence"),
                location=item.get("location"),
                measurements=item.get("measurements"),
            )

            db.add(finding)

        saved_report=Report(
            analysis_id=analysis.id,
            report_path=result.get("report_path"),
            audio_path=result.get("audio_path"),
            audio_text=result.get("audio_text"),
            report_json=result.get("report"),
        )

        db.add(saved_report)
        db.commit()

        return analysis.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

def generate_inspection_outputs(
    result:dict,
    user_id:int,
    user_email:str,
)->dict:
    outputs=generate_all_outputs(result,user_email)

    analysis_id=save_inspection(
        user_id=user_id,
        result={
            **result,
            **outputs,
        },
    )

    return {
        **result,
        **outputs,
        "analysis_id":analysis_id,
    }

@app.get("/health")
def health():
    return {
        "status":"healthy"
    }


@app.post(
    "/inspect",
    response_model=UnifiedInspectionResponse,
)
async def inspect_file(
    file:UploadFile=File(...),
    layer_type:str|None=Form(None),
    current_user:User=Depends(get_current_user),
):
    filename=file.filename or ""
    input_type=detect_input_type(filename)
    inspection_id=str(uuid4())

    if input_type=="unsupported":
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type.",
        )

    limit=(
        MAX_VECTOR_SIZE
        if input_type=="vector"
        else MAX_IMAGE_SIZE
    )

    content=await file.read(limit+1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content)>limit:
        raise HTTPException(
            status_code=413,
            detail="File size limit exceeded.",
        )

    if input_type=="vector":
        try:
            result=process_vector_upload(
                filename=filename,
                content=content,
                requested_layer=layer_type,
            )

            inspection={
                "filename":filename,
                "input_type":"vector",
                "status":"completed",
                "run_id":str(result["run_id"]),
                "layer_type":result["layer_name"],
                "feature_count":result["insertion"].get(
                    "inserted_rows",
                    0,
                ),
                "crs":result["insertion"].get(
                    "crs",
                    "Not Available",
                ),
                "findings":result["findings"],
                "visualization":result["map_data"],
            }

            return await run_in_threadpool(
                generate_inspection_outputs,
                inspection,
                current_user.id,
                current_user.email,
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

    try:
        inspect_image(content)

        result=run_vision_pipeline(
            filename=filename,
            content=content,
        )

        findings=normalize_vision_findings(
            [
                issue.model_dump()
                for issue in result.issues
            ]
        )

        inspection={
            "filename":filename,
            "input_type":"image",
            "status":"completed",
            "run_id":inspection_id,
            "layer_type":None,
            "feature_count":0,
            "crs":"Not Available",
            "findings":findings,
            "visualization":None,
        }

        return await run_in_threadpool(
            generate_inspection_outputs,
            inspection,
            current_user.id,
            current_user.email,
        )

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

@app.post("/voice/summary")
def generate_voice_summary(
    payload:VoiceSummaryRequest,
    current_user:User=Depends(get_current_user),
):
    try:
        result=create_audio_summary(
            dataset=payload.dataset,
            validation=payload.validation,
            quality_summary=payload.quality_summary,
            report=payload.report,
            output_path="outputs/MEYAAR_API_Summary.mp3",
        )

        filename=payload.dataset.get(
            "file_name",
            "Meyaar Analysis",
        )

        send_analysis_email(
            to_email=current_user.email,
            filename=filename,
            audio_path=str(result["audio_path"]),
        )

        return {
            **result,
            "email_status":"sent",
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

@app.post(
    "/images/inspect",
    response_model=ImageInspectionResponse,
)
async def inspect_uploaded_image(
    file:UploadFile=File(...),
):
    filename=file.filename or ""
    extension=Path(filename).suffix.lower()

    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: JPG, JPEG, PNG, TIF, and TIFF.",
        )

    content=await file.read(MAX_IMAGE_SIZE+1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content)>MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 25 MB limit.",
        )

    try:
        metadata=inspect_image(content)

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


@app.post(
    "/images/analyze",
    response_model=VisionAnalysisResponse,
)
async def analyze_uploaded_image(
    file:UploadFile=File(...),
):
    filename=file.filename or ""
    extension=Path(filename).suffix.lower()

    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: JPG, JPEG, PNG, TIF, and TIFF.",
        )

    content=await file.read(MAX_IMAGE_SIZE+1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content)>MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 25 MB limit.",
        )

    try:
        inspect_image(content)

        return run_vision_pipeline(
            filename=filename,
            content=content,
        )

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


@app.post(
    "/vectors/process",
    response_model=VectorProcessingResponse,
)
async def process_uploaded_vector(
    file:UploadFile=File(...),
    layer_type:str|None=Form(None),
):
    filename=file.filename or ""
    content=await file.read(MAX_VECTOR_SIZE+1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content)>MAX_VECTOR_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The vector file exceeds the 100 MB limit.",
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

@app.post("/reports/generate")
def generate_report(
    payload:ReportGenerationRequest,
    current_user:User=Depends(get_current_user),
):
    try:
        report=generate_report_content(
            dataset=payload.dataset,
            validation=payload.validation,
        )

        pdf_path=create_pdf(
            dataset=payload.dataset,
            validation=payload.validation,
            report=report,
            output_path="outputs/MEYAAR_Report.pdf",
        )

        audio_result=create_audio_summary(
            dataset=payload.dataset,
            validation=payload.validation,
            quality_summary={
                "total_findings":payload.validation.get(
                    "total_findings",
                    payload.validation.get(
                        "total_errors",
                        0,
                    ),
                )
            },
            report=report,
            output_path="outputs/MEYAAR_Summary.mp3",
        )

        filename=payload.dataset.get(
            "file_name",
            "Meyaar Analysis",
        )

        send_analysis_email(
            to_email=current_user.email,
            filename=filename,
            report_path=str(pdf_path),
            audio_path=str(audio_result["audio_path"]),
        )

        return {
            "status":"success",
            "report_path":str(pdf_path),
            "audio_path":str(audio_result["audio_path"]),
            "email_status":"sent",
            "report":report,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
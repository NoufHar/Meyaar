from pathlib import Path

from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.database.database import get_db
from src.database.models import Analysis,Report,User

router=APIRouter(
    prefix="/analyses",
    tags=["History"],
)


@router.get("")
def get_analyses(
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db),
):
    analyses=db.scalars(
        select(Analysis)
        .where(Analysis.user_id==current_user.id)
        .order_by(Analysis.created_at.desc())
    ).all()

    return [
        {
            "id":a.id,
            "run_id":a.run_id,
            "filename":a.filename,
            "input_type":a.input_type,
            "layer_type":a.layer_type,
            "status":a.status,
            "total_findings":a.total_findings,
            "created_at":a.created_at,
        }
        for a in analyses
    ]


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id:int,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db),
):
    analysis=db.scalar(
        select(Analysis).where(
            Analysis.id==analysis_id,
            Analysis.user_id==current_user.id,
        )
    )

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found.",
        )

    return {
        "id":analysis.id,
        "run_id":analysis.run_id,
        "filename":analysis.filename,
        "input_type":analysis.input_type,
        "layer_type":analysis.layer_type,
        "status":analysis.status,
        "total_findings":analysis.total_findings,
        "created_at":analysis.created_at,
        "findings":[
            {
                "finding_id":f.finding_id,
                "rule_id":f.rule_id,
                "feature_id":f.feature_id,
                "error_type":f.error_type,
                "severity":f.severity,
                "status":f.status,
                "message":f.message,
                "recommendation":f.recommendation,
                "confidence":f.confidence,
                "location":f.location,
                "measurements":f.measurements,
            }
            for f in analysis.findings
        ],
        "report":analysis.report.report_json if analysis.report else None,
    }


@router.get("/{analysis_id}/report")
def get_report(
    analysis_id:int,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db),
):
    analysis=db.scalar(
        select(Analysis).where(
            Analysis.id==analysis_id,
            Analysis.user_id==current_user.id,
        )
    )

    if not analysis or not analysis.report:
        raise HTTPException(
            status_code=404,
            detail="Report not found.",
        )

    path=Path(analysis.report.report_path)

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report file not found.",
        )

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
    )


@router.get("/{analysis_id}/audio")
def get_audio(
    analysis_id:int,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db),
):
    analysis=db.scalar(
        select(Analysis).where(
            Analysis.id==analysis_id,
            Analysis.user_id==current_user.id,
        )
    )

    if not analysis or not analysis.report:
        raise HTTPException(
            status_code=404,
            detail="Audio not found.",
        )

    path=Path(analysis.report.audio_path)

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found.",
        )

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=path.name,
    )


@router.delete("/{analysis_id}")
def delete_analysis(
    analysis_id:int,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db),
):
    analysis=db.scalar(
        select(Analysis).where(
            Analysis.id==analysis_id,
            Analysis.user_id==current_user.id,
        )
    )

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found.",
        )

    report_path=None
    audio_path=None

    if analysis.report:
        report_path=analysis.report.report_path
        audio_path=analysis.report.audio_path

    db.delete(analysis)
    db.commit()

    for file_path in [report_path,audio_path]:
        if file_path:
            path=Path(file_path)
            if path.exists():
                path.unlink()

    return {
        "status":"deleted"
    }
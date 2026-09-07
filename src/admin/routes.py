from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.orm import Session

from src.auth.dependencies import require_admin
from src.database.database import get_db
from src.database.models import Analysis,User

router=APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get("/me")
def admin_me(
    current_user:User=Depends(require_admin),
):
    return {
        "id":current_user.id,
        "name":current_user.name,
        "email":current_user.email,
        "role":current_user.role,
    }


@router.get("/users")
def get_users(
    current_user:User=Depends(require_admin),
    db:Session=Depends(get_db),
):
    users=db.scalars(
        select(User).order_by(User.created_at.desc())
    ).all()

    return [
        {
            "id":u.id,
            "name":u.name,
            "email":u.email,
            "role":u.role,
            "is_active":u.is_active,
            "created_at":u.created_at,
        }
        for u in users
    ]


@router.get("/analyses")
def get_all_analyses(
    current_user:User=Depends(require_admin),
    db:Session=Depends(get_db),
):
    analyses=db.scalars(
        select(Analysis).order_by(Analysis.created_at.desc())
    ).all()

    return [
        {
            "id":a.id,
            "user_id":a.user_id,
            "filename":a.filename,
            "input_type":a.input_type,
            "status":a.status,
            "total_findings":a.total_findings,
            "created_at":a.created_at,
        }
        for a in analyses
    ]


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id:int,
    is_active:bool,
    current_user:User=Depends(require_admin),
    db:Session=Depends(get_db),
):
    user=db.get(User,user_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    if user.id==current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot disable own account.",
        )

    user.is_active=is_active
    db.commit()

    return {
        "id":user.id,
        "is_active":user.is_active,
    }


@router.get("/stats")
def get_stats(
    current_user:User=Depends(require_admin),
    db:Session=Depends(get_db),
):
    users=db.scalar(
        select(func.count()).select_from(User)
    )

    analyses=db.scalar(
        select(func.count()).select_from(Analysis)
    )

    findings=db.scalar(
        select(func.coalesce(func.sum(Analysis.total_findings),0))
    )

    return {
        "users":users,
        "analyses":analyses,
        "findings":findings,
    }
from pydantic import BaseModel,EmailStr
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from src.database.database import get_db
from src.database.models import User

router=APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


class RegisterRequest(BaseModel):
    name:str
    email:EmailStr
    password:str


class LoginRequest(BaseModel):
    email:EmailStr
    password:str


class UserResponse(BaseModel):
    id:int
    name:str
    email:str
    role:str
    is_active:bool

    model_config={"from_attributes":True}


class TokenResponse(BaseModel):
    access_token:str
    token_type:str="bearer"
    user:UserResponse


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data:RegisterRequest,
    db:Session=Depends(get_db),
):
    email=data.email.lower().strip()

    existing=db.scalar(
        select(User).where(User.email==email)
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    if len(data.password)<8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )

    user=User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role="user",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data:LoginRequest,
    db:Session=Depends(get_db),
):
    email=data.email.lower().strip()

    user=db.scalar(
        select(User).where(User.email==email)
    )

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    token=create_access_token(user.id)

    return {
        "access_token":token,
        "token_type":"bearer",
        "user":user,
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user:User=Depends(get_current_user),
):
    return current_user
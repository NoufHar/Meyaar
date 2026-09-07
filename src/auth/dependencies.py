import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.database.models import User

load_dotenv()

SECRET_KEY=os.getenv("SECRET_KEY")
ALGORITHM="HS256"

security=HTTPBearer()


def get_current_user(
    credentials:HTTPAuthorizationCredentials=Depends(security),
    db:Session=Depends(get_db),
)->User:
    token=credentials.credentials

    try:
        payload=jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id=int(payload.get("sub"))

    except (jwt.InvalidTokenError,TypeError,ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    user=db.get(User,user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user


def require_admin(
    current_user:User=Depends(get_current_user),
)->User:
    if current_user.role!="admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )

    return current_user
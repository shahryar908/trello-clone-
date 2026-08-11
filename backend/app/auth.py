from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlmodel import Session

from .config import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY
from .database import get_session
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> int:
    """Return the user id from a valid token; raises on any failure."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return int(payload["sub"])


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    unauthorized = HTTPException(status_code=401, detail="Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        user_id = decode_token(credentials.credentials)
    except Exception:
        raise unauthorized
    user = session.get(User, user_id)
    if user is None:
        raise unauthorized
    return user

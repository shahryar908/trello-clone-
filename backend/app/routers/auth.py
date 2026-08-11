from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_session
from ..models import User
from ..schemas import LoginRequest, SignupRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=201)
def signup(body: SignupRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, password=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email)).first()
    # same message for unknown email and wrong password — don't reveal which
    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))

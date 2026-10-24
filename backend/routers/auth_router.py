from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    oauth2_scheme,
)
from rate_limit import auth_rate_limit
from config import COOKIE_SAMESITE, COOKIE_SECURE, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, user: models.User) -> None:
    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        "access_token",
        token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


@router.post("/register", response_model=schemas.AuthResponse, dependencies=[Depends(auth_rate_limit)])
def register(payload: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_auth_cookie(response, user)
    return {"user": user}


@router.post("/login", response_model=schemas.AuthResponse, dependencies=[Depends(auth_rate_limit)])
def login(payload: schemas.UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _set_auth_cookie(response, user)
    return {"user": user}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        "access_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    return {"ok": True}


@router.get("/me", response_model=Optional[schemas.UserOut])
def me(
    request: Request,
    response: Response,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    try:
        return get_current_user(request=request, token=token, db=db)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        response.delete_cookie(
            "access_token",
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            path="/",
        )
        return None

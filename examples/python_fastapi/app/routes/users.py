"""User routes: registration, login, profile."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app import auth
from app.models import Token, User, UserCreate, UserPublic

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate) -> UserPublic:
    if auth.get_user(body.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed = auth.get_password_hash(body.password)
    auth._FAKE_DB[body.username] = {
        "username": body.username,
        "email": body.email,
        "hashed_password": hashed,
        "role": "user",
    }
    return UserPublic(username=body.username, email=body.email, role="user")


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()) -> Token:
    user = auth.authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.create_access_token(
        {"sub": user.username},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserPublic)
def read_me(current_user: User = Depends(auth.get_current_user)) -> UserPublic:
    return UserPublic(
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
    )

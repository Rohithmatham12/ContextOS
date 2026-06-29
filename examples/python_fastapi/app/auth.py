"""JWT authentication helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.models import TokenData, User

SECRET_KEY = "replace-me-in-production"  # noqa: S105
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")

# In-memory user store for example purposes only.
_FAKE_DB: dict[str, dict[str, str]] = {
    "alice": {
        "username": "alice",
        "hashed_password": pwd_context.hash("secret"),
        "email": "alice@example.com",
        "role": "admin",
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user(username: str) -> User | None:
    row = _FAKE_DB.get(username)
    if row is None:
        return None
    return User(**row)


def authenticate_user(username: str, password: str) -> User | None:
    user = get_user(username)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict[str, object], expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(tz=UTC) + (expires_delta or timedelta(minutes=15))
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exc
        token_data = TokenData(username=username)
    except JWTError as exc:
        raise credentials_exc from exc

    user = get_user(token_data.username)
    if user is None:
        raise credentials_exc
    return user

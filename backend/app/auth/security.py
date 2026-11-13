"""JWT creation and database-backed user authentication."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionDB, UserDB, get_db, hash_session_token, pwd_context
from app.core.sessions import get_session_user, get_session_user_by_hash

SECRET_KEY = os.getenv("JENGA_SECRET_KEY", "change-this-development-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def create_access_token(username: str, role: str, session_token: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": username, "role": role, "exp": expires, "sid": hash_session_token(session_token)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def authenticate_user(db: Session, username: str, password: str) -> UserDB | None:
    user = db.scalar(select(UserDB).where(UserDB.username == username))
    if (
        user is None or not user.is_active or user.role not in {"engineer", "customer"}
        or not pwd_context.verify(password, user.hashed_password)
    ):
        return None
    return user


def get_current_session(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[SessionDB, UserDB]:
    """Prefer an explicit bearer token; never recover invalid bearer auth via a cookie."""

    if token is None:
        session_user = get_session_user(request, db)
        if session_user is not None:
            return session_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        session_hash = payload.get("sid")
        if (
            not isinstance(username, str) or role not in {"engineer", "customer"}
            or not isinstance(session_hash, str) or len(session_hash) != 64
        ):
            raise credentials_error
    except (JWTError, TypeError):
        raise credentials_error from None

    session_user = get_session_user_by_hash(session_hash, db)
    if session_user is None:
        raise credentials_error
    _, user = session_user
    if user.username != username or user.role != role:
        raise credentials_error
    return session_user


def get_current_user(
    authenticated: Annotated[tuple[SessionDB, UserDB], Depends(get_current_session)],
) -> UserDB:
    return authenticated[1]

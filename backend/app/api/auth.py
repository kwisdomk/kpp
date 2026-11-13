"""Authentication routes."""

from typing import Annotated
from fastapi import Request

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.security import (
    authenticate_user, create_access_token, get_current_session, get_current_user, oauth2_scheme,
)
from app.core.config import SESSION_COOKIE_NAME
from app.core.sessions import create_session, get_session_user
from app.db.database import UserDB, get_db, utc_now
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(db, credentials.username, credentials.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    session_token = create_session(db, user)
    response.set_cookie(SESSION_COOKIE_NAME, session_token, httponly=True, samesite="lax", secure=False, max_age=8 * 3600)
    return TokenResponse(
        access_token=create_access_token(user.username, user.role, session_token),
        token_type="bearer",
        role=user.role,  # type: ignore[arg-type]
    )


@router.get("/me")
def me(user: Annotated[UserDB, Depends(get_current_user)]) -> dict[str, object]:
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    sessions = {}
    try:
        session, _ = get_current_session(request, token, db)
    except HTTPException as error:
        if error.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        # Already signed out or expired: still clear the browser cookie.
    else:
        sessions[session.id] = session
    if token is not None:
        # Logout can revoke a submitted cookie even when its bearer is expired,
        # or the two credentials represent different logins. This never grants
        # access to a protected resource or revokes credentials not submitted.
        cookie_session = get_session_user(request, db)
        if cookie_session is not None:
            session, _ = cookie_session
            sessions[session.id] = session
    for session in sessions.values():
        session.revoked_at = utc_now()
    if sessions:
        db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME)

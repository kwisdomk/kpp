"""Server-side opaque session lifecycle."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import (
    SESSION_ABSOLUTE_HOURS,
    SESSION_COOKIE_NAME,
    SESSION_CUSTOMER_IDLE_MINUTES,
    SESSION_ENGINEER_IDLE_MINUTES,
)
from app.db.database import SessionDB, UserDB, hash_session_token, new_session_token, utc_now


def create_session(db: Session, user: UserDB) -> str:
    token = new_session_token()
    now = utc_now()
    db.add(
        SessionDB(
            token_hash=hash_session_token(token),
            user_id=user.id,
            issued_at=now,
            last_active_at=now,
            expires_at=now + timedelta(hours=SESSION_ABSOLUTE_HOURS),
        )
    )
    db.commit()
    return token


def get_session_user(request: Request, db: Session) -> tuple[SessionDB, UserDB] | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return get_session_user_by_hash(hash_session_token(token), db)


def get_session_user_by_hash(token_hash: str, db: Session) -> tuple[SessionDB, UserDB] | None:
    """Apply the same lifecycle checks to cookie and session-bound bearer auth."""

    session = db.scalar(select(SessionDB).where(SessionDB.token_hash == token_hash))
    if session is None or session.revoked_at is not None:
        return None
    user = db.get(UserDB, session.user_id)
    if user is None or not user.is_active or user.role not in {"engineer", "customer"}:
        session.revoked_at = utc_now()
        db.commit()
        return None
    now = utc_now()
    expires_at = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    last_active_at = (
        session.last_active_at.replace(tzinfo=timezone.utc)
        if session.last_active_at.tzinfo is None
        else session.last_active_at
    )
    idle_minutes = SESSION_ENGINEER_IDLE_MINUTES if user.role == "engineer" else SESSION_CUSTOMER_IDLE_MINUTES
    if expires_at <= now or last_active_at + timedelta(minutes=idle_minutes) <= now:
        session.revoked_at = now
        db.commit()
        return None
    session.last_active_at = now
    db.commit()
    return session, user


def require_session(request: Request, db: Session) -> tuple[SessionDB, UserDB]:
    result = get_session_user(request, db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or expired session",
        )
    return result

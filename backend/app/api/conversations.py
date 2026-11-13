"""Owner-bound conversation lifecycle routes."""

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.db.database import AuditLogDB, ConversationDB, ConversationMessageDB, UserDB, get_db
from app.schemas.catalogue import ConversationCreate

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _owner_or_404(conversation_id: str, user: UserDB, db: Session) -> ConversationDB:
    conversation = db.scalar(
        select(ConversationDB).where(
            ConversationDB.id == conversation_id,
            ConversationDB.user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def get_or_create_current_conversation(
    current_user: UserDB,
    db: Session,
) -> ConversationDB:
    conversation = db.scalar(
        select(ConversationDB)
        .where(
            ConversationDB.user_id == current_user.id,
            ConversationDB.status == "active",
        )
        .order_by(ConversationDB.created_at.desc())
    )
    if conversation is None:
        conversation = ConversationDB(
            id=f"conv_{uuid.uuid4().hex}",
            user_id=current_user.id,
            title="Product Copilot",
            created_at=datetime.now(timezone.utc),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


@router.post("/current")
def current_conversation(
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    conversation = get_or_create_current_conversation(current_user, db)
    return {"id": conversation.id, "status": conversation.status, "title": conversation.title}


@router.post("")
def create_conversation(
    payload: ConversationCreate,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    conversation = ConversationDB(
        id=f"conv_{uuid.uuid4().hex}",
        user_id=current_user.id,
        title=payload.title,
        created_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    db.commit()
    return {"id": conversation.id, "status": conversation.status, "title": conversation.title}


@router.get("/{conversation_id}/messages")
def list_conversation_messages(
    conversation_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    _owner_or_404(conversation_id, current_user, db)
    if current_user.role == "customer":
        # A demoted account must not recover prior engineer answers from history.
        # Inspect only server-written audit IDs/roles before selecting message text.
        has_customer_audit = db.scalar(select(AuditLogDB.id).where(
            AuditLogDB.session_id == conversation_id, AuditLogDB.user_role == "customer",
        ).limit(1))
        has_other_role_audit = db.scalar(select(AuditLogDB.id).where(
            AuditLogDB.session_id == conversation_id, AuditLogDB.user_role != "customer",
        ).limit(1))
        if has_customer_audit is None or has_other_role_audit is not None:
            return []
    messages = db.scalars(
        select(ConversationMessageDB)
        .where(ConversationMessageDB.conversation_id == conversation_id)
        .order_by(ConversationMessageDB.created_at, ConversationMessageDB.id)
    ).all()
    return [
        {
            "id": str(message.id),
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
            "metadata": json.loads(message.metadata_json) if message.metadata_json else {},
        }
        for message in messages
    ]


@router.get("")
def list_conversations(
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, object]]:
    conversations = db.scalars(
        select(ConversationDB)
        .where(ConversationDB.user_id == current_user.id)
        .order_by(ConversationDB.created_at.desc())
    ).all()
    return [
        {
            "id": conversation.id,
            "title": conversation.title or "Untitled conversation",
            "updatedAt": conversation.created_at.isoformat(),
        }
        for conversation in conversations
    ]


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    conversation = _owner_or_404(conversation_id, current_user, db)
    return {"id": conversation.id, "status": conversation.status, "title": conversation.title}


@router.post("/{conversation_id}/finish", status_code=204)
def finish_conversation(
    conversation_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    conversation = _owner_or_404(conversation_id, current_user, db)
    conversation.status = "finished"
    conversation.finished_at = datetime.now(timezone.utc)
    db.commit()

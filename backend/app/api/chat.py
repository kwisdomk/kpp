"""Chat routes."""

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.db.database import AuditLogDB, ConversationDB, UserDB, get_db, utc_now
from app.schemas.chat import Citation, ChatQuery, ChatResponse
from app.services.chat import route_query
from app.services.authorization import get_authorized_product
from app.services.multimodal import prepare_media

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/query", response_model=ChatResponse)
def chat_query(
    request: ChatQuery,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    started = time.perf_counter()
    text = request.resolved_text() if request.text is not None or request.query is not None else ""
    requested_id = request.conversation_id or request.session_id
    if requested_id:
        conversation = db.scalar(
            select(ConversationDB).where(
                ConversationDB.id == requested_id,
                ConversationDB.user_id == current_user.id,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.status != "active":
            raise HTTPException(status_code=409, detail="Conversation is finished")
    structured_results = {}
    if request.media_ids:
        answer, structured_results, warnings = prepare_media(db, current_user, request.media_ids, text)
        tool, citation_names, confidence = "multimodal_input", [], "low"
    else:
        answer, tool, citation_names, warnings, confidence = route_query(
            text, current_user, db, structured_results=structured_results,
        )
    if not requested_id:
        conversation = ConversationDB(
            id=f"conv_{uuid.uuid4().hex}",
            user_id=current_user.id,
            created_at=utc_now(),
        )
        db.add(conversation)
        db.commit()
    session_id = conversation.id
    execution_time_ms = round((time.perf_counter() - started) * 1000, 3)
    db.add(
        AuditLogDB(
            session_id=session_id,
            user_role=current_user.role,
            tool_used=tool,
            status="success" if tool != "access_control" else "rejected",
            timestamp=utc_now(),
        )
    )
    db.commit()
    citations = []
    for source_id in citation_names:
        excerpt = None
        if source_id.startswith("product:") and source_id[8:].isdigit():
            product = get_authorized_product(db, current_user, int(source_id[8:]))
            if product is None:
                continue
            excerpt = f"{product.name} ({product.model_number}): {product.specifications}. Synthetic demo catalogue."
        citations.append(Citation(source_id=source_id, excerpt=excerpt))
    return ChatResponse(
        answer=answer,
        citations=citations,
        warnings=warnings,
        confidence=confidence,
        tool_executed=tool,
        execution_time_ms=execution_time_ms,
        request_id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        tool_trace_id=session_id,
        latency_ms=execution_time_ms,
        needs_human_review=tool == "safety_notice",
        structured_results=structured_results,
    )

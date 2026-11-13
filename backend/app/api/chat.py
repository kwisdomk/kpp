"""Owner-bound chat with local media by default and explicit hosted opt-in."""

import json
import os
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.conversations import _owner_or_404, get_or_create_current_conversation
from app.auth.security import get_current_user
from app.db.database import AuditLogDB, ConversationMessageDB, MediaContentDB, MediaDB, UserDB, get_db, utc_now
from app.schemas.chat import Citation, ChatQuery, ChatResponse
from app.services.authorization import get_authorized_product
from app.services.chat import route_query
from app.services.media import assert_hosted_media_allowed, load_chat_attachments
from app.services.multimodal import prepare_media
from app.services.images import image_path
from app.services.audio import audio_path

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
    conversation = _owner_or_404(requested_id, current_user, db) if requested_id else None
    if conversation is not None and conversation.status != "active":
        raise HTTPException(409, "Conversation is finished")

    structured_results = {}
    media_rows = []
    if request.media_ids:
        if len(set(request.media_ids)) != len(request.media_ids):
            raise HTTPException(422, "Each attachment may only be included once")
        media_rows = list(db.scalars(select(MediaDB).where(
            MediaDB.id.in_(request.media_ids), MediaDB.user_id == current_user.id,
            MediaDB.active.is_(True),
        )))
        if len(media_rows) != len(request.media_ids):
            raise HTTPException(404, "One or more attachments were not found")
        if request.allow_external_processing:
            assert_hosted_media_allowed(current_user.id, db)
            attachments = load_chat_attachments(request.media_ids, current_user.id, db)
            text = text or "Please analyze the attached file(s)."
            answer, tool, citation_names, warnings, confidence = route_query(
                text, current_user, db, structured_results=structured_results, attachments=attachments,
            )
        else:
            if any(row.kind == "document" or row.content_type not in {"image/png", "audio/wav"} for row in media_rows):
                raise HTTPException(428, "Confirm you are allowed to send these attachments to the configured AI service")
            answer, structured_results, warnings = prepare_media(db, current_user, request.media_ids, text)
            tool, citation_names, confidence = "multimodal_input", [], "low"
    else:
        answer, tool, citation_names, warnings, confidence = route_query(
            text, current_user, db, structured_results=structured_results,
        )

    citations = []
    for source_id in citation_names:
        excerpt = None
        if source_id.startswith("product:") and source_id[8:].isdigit():
            product = get_authorized_product(db, current_user, int(source_id[8:]))
            if product is None:
                continue
            excerpt = f"{product.name} ({product.model_number}): {product.specifications}. Synthetic demo catalogue."
        citations.append(Citation(source_id=source_id, excerpt=excerpt))

    conversation = conversation or get_or_create_current_conversation(current_user, db)
    now = utc_now()
    attachment_names = [row.filename for row in media_rows]
    if request.media_ids and request.allow_external_processing:
        for row in media_rows:
            row.active = False
            if row.filename == f"{row.id}.png":
                image_path(row.id).unlink(missing_ok=True)
            elif row.filename == f"{row.id}.wav":
                audio_path(row.id).unlink(missing_ok=True)
        db.execute(delete(MediaContentDB).where(MediaContentDB.media_id.in_(request.media_ids)))
    execution_time_ms = round((time.perf_counter() - started) * 1000, 3)
    metadata = {
        "citations": [citation.model_dump() for citation in citations],
        "warnings": warnings, "confidence": confidence, "tool_executed": tool,
        "attachments": attachment_names, "structured_results": structured_results,
        "comparison": structured_results.get("comparison"),
    }
    db.add_all([
        AuditLogDB(session_id=conversation.id, user_role=current_user.role, tool_used=tool,
                   status="rejected" if tool == "access_control" else "success", timestamp=now),
        ConversationMessageDB(conversation_id=conversation.id, role="user", content=text or "Photo / spoken question",
                              metadata_json=json.dumps({"attachments": attachment_names,
                                  "external_processing_approved": request.allow_external_processing}), created_at=now),
        ConversationMessageDB(conversation_id=conversation.id, role="assistant", content=answer,
                              metadata_json=json.dumps(metadata), created_at=now),
    ])
    db.commit()
    return ChatResponse(
        answer=answer, citations=citations, warnings=warnings, confidence=confidence,
        tool_executed=tool, execution_time_ms=execution_time_ms, request_id=str(uuid.uuid4()),
        conversation_id=conversation.id, tool_trace_id=conversation.id, latency_ms=execution_time_ms,
        needs_human_review=tool == "safety_notice", structured_results=structured_results,
    )

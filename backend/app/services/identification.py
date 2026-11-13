"""Authorize the image and candidate pool before invoking OCR or matching."""

import time
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ai.multimodal.nameplate_ocr import (
    ModelCandidate, OcrExecutionError, OcrTimeoutError, OcrUnavailableError,
    identify_models, read_nameplate,
)
from app.db.database import AuditLogDB, UserDB, utc_now
from app.schemas.identification import IdentificationCandidate, IdentificationResponse
from app.services.images import get_owned_image, image_processing_slot
from app.tools.catalog import lookup_products


def identify_image(db: Session, user: UserDB, media_id: str) -> IdentificationResponse:
    _, path = get_owned_image(db, user, media_id)
    rows = lookup_products(db, user)
    by_id = {str(row.id): row for row in rows}
    candidates = [ModelCandidate(str(row.id), row.model_number) for row in rows]
    if not image_processing_slot.acquire(blocking=False):
        raise HTTPException(429, "Image processing is busy; retry shortly")
    started = time.perf_counter()
    trace_id = f"ocr_{uuid.uuid4().hex}"
    outcome = "failed"
    try:
        try:
            text = read_nameplate(path.read_bytes())
        except OcrUnavailableError as error:
            raise HTTPException(503, "Local OCR is unavailable; configure Tesseract and English language data") from error
        except OcrTimeoutError as error:
            raise HTTPException(504, "Local OCR timed out") from error
        except OcrExecutionError as error:
            raise HTTPException(502, "Local OCR could not read the image") from error
        matches = identify_models(text, candidates).candidates
        outcome = "identified" if len(matches) == 1 else "ambiguous" if matches else "unidentified"
        reason = "one_model_match" if len(matches) == 1 else "multiple_model_matches" if matches else (
            "no_text" if not text.strip() else "no_match"
        )
        return IdentificationResponse(
            media_id=media_id, status=outcome, reason=reason,
            candidates=[IdentificationCandidate(
                product_id=by_id[row.product_id].id, model_number=row.model_number,
                name=by_id[row.product_id].name, category=by_id[row.product_id].category,
                source_id=f"product:{row.product_id}",
            ) for row in matches[:10]],
            candidates_truncated=len(matches) > 10,
            warnings=["OCR matches catalogue model text only. Confirm the equipment and use approved documentation before technical work."],
            tool_trace_id=trace_id, latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
    finally:
        image_processing_slot.release()
        db.add(AuditLogDB(
            session_id=trace_id, user_role=user.role, tool_used="identify_equipment",
            status=outcome, timestamp=utc_now(),
        ))
        db.commit()

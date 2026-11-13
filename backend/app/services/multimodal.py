"""Authorize all attachments before inference; prepare inputs without inventing evidence."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.multimodal.media_fusion import fuse_inputs
from ai.multimodal.nameplate_ocr import ModelCandidate, identify_models
from app.db.database import MediaDB, UserDB
from app.services.audio import get_owned_audio, transcribe_owned_audio
from app.services.identification import identify_image
from app.services.images import get_owned_image
from app.tools.catalog import lookup_products


def prepare_media(db: Session, user: UserDB, media_ids: list[str], text: str) -> tuple[str, dict, list[str]]:
    if len(set(media_ids)) != len(media_ids):
        raise HTTPException(422, "Attach at most one photo and one audio recording")
    attachments = {}
    # Preflight the complete set before any native inference is invoked.
    for media_id in media_ids:
        row = db.scalar(select(MediaDB).where(MediaDB.id == media_id, MediaDB.user_id == user.id))
        if row is None or row.kind not in {"image", "audio"}:
            raise HTTPException(404, "Media not found")
        if row.kind in attachments:
            raise HTTPException(422, "Attach at most one photo and one audio recording")
        (get_owned_audio if row.kind == "audio" else get_owned_image)(db, user, media_id)
        attachments[row.kind] = media_id
    candidates = [ModelCandidate(str(row.id), row.model_number) for row in lookup_products(db, user)]
    speech = transcribe_owned_audio(db, user, attachments["audio"]) if "audio" in attachments else None
    image = identify_image(db, user, attachments["image"]) if "image" in attachments else None
    transcript = speech.text if speech else ""
    combined = "\n".join((text, transcript))
    if len(combined) > 4000:
        raise HTTPException(422, "Combined question is too long; use a shorter recording or message")
    mentions = identify_models(combined, candidates).candidates
    fused = fuse_inputs(
        text, transcript, [item.model_number for item in image.candidates] if image else [],
        [item.model_number for item in mentions], has_image=image is not None,
        truncated=image.candidates_truncated if image else False,
    )
    replies = {
        "missing_question": "I couldn't hear a question. Please record it again or type what you need.",
        "ambiguous_image": "The photo matches multiple catalogue models. Which model should I use?",
        "unidentified_image": "I couldn't identify a catalogue model from the photo. Please provide the exact model or a clearer nameplate photo.",
        "model_disagreement": "The model mentioned in your question differs from the photo candidate. Which equipment should I use? If comparing them, name both models explicitly.",
    }
    if fused.needs_clarification:
        answer = replies[fused.reason]
    else:
        identity = f"The photo/question matches catalogue model {fused.model_number}. " if fused.model_number else ""
        answer = (identity + "I have your question, but I don't know the technical answer based on the available documentation. "
                  "Approved manual retrieval is not connected yet. Provide the exact model/manual for review. "
                  "For technical work, check the manual and follow local regulations.")
    structured = {
        "input_status": "clarification_required" if fused.needs_clarification else "evidence_unavailable",
        "reason": fused.reason, "question": fused.question,
        "model_number": fused.model_number,
        "transcription": speech.model_dump() if speech else None,
        "identification": image.model_dump() if image else None,
    }
    warnings = ["Media input is untrusted. Catalogue matching does not verify equipment identity or provide manufacturer instructions."]
    return answer, structured, warnings

"""Authenticated uploads and owner-bound sanitized-image identification."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.security import get_current_user
from app.core.config import ALLOWED_AUDIO_TYPES, ALLOWED_IMAGE_TYPES, MAX_MEDIA_BYTES
from app.db.database import MediaDB, UserDB, get_db
from app.schemas.identification import IdentificationResponse
from app.services.identification import identify_image
from app.services.images import get_owned_image, image_path, image_processing_slot, sanitize_image
from app.services.audio import audio_path, get_owned_audio, sanitize_audio, transcribe_owned_audio
from app.schemas.transcription import TranscriptionResponse

router = APIRouter(prefix="/media", tags=["media"])


@router.post("")
async def upload_media(
    file: Annotated[UploadFile, File(...)],
    kind: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    allowed_types = ALLOWED_IMAGE_TYPES if kind == "image" else ALLOWED_AUDIO_TYPES if kind == "audio" else set()
    if not allowed_types or file.content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported media type")
    content = await file.read(MAX_MEDIA_BYTES + 1)
    if len(content) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Media exceeds 8 MiB limit")
    media_id = f"media_{uuid.uuid4().hex}"
    path = None
    content_type = file.content_type
    if kind == "image":
        if not image_processing_slot.acquire(blocking=False):
            raise HTTPException(429, "Image processing is busy; retry shortly")
        try:
            content = await run_in_threadpool(sanitize_image, content, content_type)
        finally:
            image_processing_slot.release()
        path = image_path(media_id)
        content_type = "image/png"
    else:
        content = sanitize_audio(content)
        path = audio_path(media_id)
        content_type = "audio/wav"
    if path is not None:
        created = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("xb") as output:
                created = True
                output.write(content)
        except OSError as error:
            if created:
                path.unlink(missing_ok=True)
            raise HTTPException(503, "Private media storage is unavailable") from error
    media = MediaDB(
        id=media_id,
        user_id=current_user.id,
        kind=kind,
        filename=f"{media_id}.png" if kind == "image" else f"{media_id}.wav",
        content_type=content_type,
        size_bytes=len(content),
        created_at=datetime.now(timezone.utc),
    )
    try:
        db.add(media)
        db.commit()
    except Exception:
        db.rollback()
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    return {"id": media.id, "kind": media.kind, "content_type": media.content_type, "size_bytes": media.size_bytes}


@router.get("/{media_id}", response_class=FileResponse)
def read_image(
    media_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    row = db.scalar(select(MediaDB).where(MediaDB.id == media_id, MediaDB.user_id == current_user.id))
    if row is None:
        raise HTTPException(404, "Media not found")
    _, path = (get_owned_audio if row.kind == "audio" else get_owned_image)(db, current_user, media_id)
    return FileResponse(path, media_type="audio/wav" if row.kind == "audio" else "image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })


@router.delete("/{media_id}", status_code=204)
def delete_image(
    media_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    media = db.scalar(select(MediaDB).where(
        MediaDB.id == media_id, MediaDB.user_id == current_user.id,
        MediaDB.kind.in_(["image", "audio"]),
    ))
    if media is None:
        raise HTTPException(404, "Image not found")
    try:
        (audio_path if media.kind == "audio" else image_path)(media.id).unlink(missing_ok=True)
    except OSError as error:
        raise HTTPException(503, "Private image storage is unavailable") from error
    media.active = False
    db.commit()


@router.post("/{media_id}/identify", response_model=IdentificationResponse)
def identify_equipment(
    media_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IdentificationResponse:
    return identify_image(db, current_user, media_id)


@router.post("/{media_id}/transcribe", response_model=TranscriptionResponse)
def transcribe_media(
    media_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptionResponse:
    return transcribe_owned_audio(db, current_user, media_id)

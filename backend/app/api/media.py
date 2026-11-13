"""Authenticated uploads and owner-bound sanitized-image identification."""

import uuid
import os
import mimetypes
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.security import get_current_user
from app.core.config import ALLOWED_AUDIO_TYPES, ALLOWED_IMAGE_TYPES, ALLOWED_DOCUMENT_TYPES, HOSTED_AUDIO_TYPES, MAX_MEDIA_BYTES
from app.db.database import MediaContentDB, MediaDB, UserDB, get_db
from app.schemas.identification import IdentificationResponse
from app.services.identification import identify_image
from app.services.images import get_owned_image, image_path, image_processing_slot, sanitize_image
from app.services.audio import audio_path, get_owned_audio, sanitize_audio, transcribe_owned_audio
from app.schemas.transcription import TranscriptionResponse

router = APIRouter(prefix="/media", tags=["media"])


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_ACTIVE_MEDIA_BYTES = 64 * 1024 * 1024
MAX_ACTIVE_MEDIA_FILES = 20
MEDIA_RETENTION = timedelta(hours=24)


def _validate_content(content: bytes, content_type: str) -> None:
    valid = True
    if content_type == "image/jpeg":
        valid = content.startswith(b"\xff\xd8\xff")
    elif content_type == "image/png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif content_type == "image/webp":
        valid = content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    elif content_type == "application/pdf":
        valid = content.startswith(b"%PDF-")
    elif content_type in {"audio/wav", "audio/x-wav", "audio/wave"}:
        valid = (
            content.startswith(b"RIFF") and content[8:12] == b"WAVE"
        ) or (content.startswith(b"RF64") and content[8:12] == b"WAVE")
    elif content_type == "audio/webm":
        valid = content.startswith(b"\x1aE\xdf\xa3")
    elif content_type == "audio/mp4":
        valid = len(content) >= 8 and content[4:8] == b"ftyp"
    elif content_type == "audio/mpeg":
        valid = content.startswith(b"ID3") or (
            len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
        )
    elif content_type == DOCX_TYPE:
        try:
            with ZipFile(BytesIO(content)) as archive:
                valid = "word/document.xml" in archive.namelist()
        except BadZipFile:
            valid = False
    elif content_type in ALLOWED_DOCUMENT_TYPES:
        try:
            content.decode("utf-8-sig")
            valid = b"\x00" not in content
        except UnicodeDecodeError:
            valid = False
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match its declared type.",
        )


def _expire_pending_uploads(user_id: int, db: Session, now: datetime) -> None:
    expired = db.scalars(
        select(MediaDB).where(
            MediaDB.user_id == user_id,
            MediaDB.active.is_(True),
            MediaDB.created_at < now - MEDIA_RETENTION,
        )
    ).all()
    if not expired:
        return
    expired_ids = [media.id for media in expired]
    for media in expired:
        media.active = False
    db.execute(
        delete(MediaContentDB).where(MediaContentDB.media_id.in_(expired_ids))
    )
    db.flush()


@router.post("")
async def upload_media(
    file: Annotated[UploadFile, File(...)],
    kind: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    hosted_enabled = os.getenv("ENABLE_HOSTED_MEDIA", "").lower() == "true" and not os.getenv("LLM_BASE_URL", "").strip()
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type in {"", "application/octet-stream"}:
        content_type = mimetypes.guess_type(file.filename or "")[0] or content_type
    allowed_types = ALLOWED_IMAGE_TYPES if kind == "image" else ALLOWED_AUDIO_TYPES if kind == "audio" else set()
    if hosted_enabled:
        allowed_types = allowed_types | HOSTED_AUDIO_TYPES if kind == "audio" else ALLOWED_DOCUMENT_TYPES if kind == "document" else allowed_types
    if not allowed_types or content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported media type")
    content = await file.read(MAX_MEDIA_BYTES + 1)
    if len(content) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Media exceeds 8 MiB limit")
    if not content:
        raise HTTPException(415, "Uploaded media must contain valid nonempty content")
    now = datetime.now(timezone.utc)
    _expire_pending_uploads(current_user.id, db, now)
    active_count, active_bytes = db.execute(select(func.count(), func.coalesce(func.sum(MediaDB.size_bytes), 0)).where(
        MediaDB.user_id == current_user.id, MediaDB.active.is_(True),
    )).one()
    if active_count >= MAX_ACTIVE_MEDIA_FILES or active_bytes + len(content) > MAX_ACTIVE_MEDIA_BYTES:
        raise HTTPException(413, "Pending uploads exceed the per-account storage limit")
    media_id = f"media_{uuid.uuid4().hex}"
    path = None
    if kind == "image":
        if not image_processing_slot.acquire(blocking=False):
            raise HTTPException(429, "Image processing is busy; retry shortly")
        try:
            content = await run_in_threadpool(sanitize_image, content, content_type)
        finally:
            image_processing_slot.release()
        path = image_path(media_id)
        content_type = "image/png"
    elif kind == "audio" and content_type in ALLOWED_AUDIO_TYPES:
        content = sanitize_audio(content)
        path = audio_path(media_id)
        content_type = "audio/wav"
    else:
        _validate_content(content, content_type)
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
        filename=path.name if path is not None else (file.filename or "upload").replace(chr(92), "/").rsplit("/", 1)[-1][:255],
        content_type=content_type,
        size_bytes=len(content),
        created_at=datetime.now(timezone.utc),
    )
    try:
        db.add(media)
        db.flush()
        if path is None:
            db.add(MediaContentDB(media_id=media.id, content=content))
        db.commit()
    except Exception:
        db.rollback()
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    return {"id": media.id, "filename": media.filename, "kind": media.kind, "content_type": media.content_type, "size_bytes": media.size_bytes}


@router.get("/{media_id}", response_class=FileResponse)
def read_image(
    media_id: str,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    row = db.scalar(select(MediaDB).where(MediaDB.id == media_id, MediaDB.user_id == current_user.id))
    if row is None or row.kind not in {"image", "audio"}:
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
    ))
    if media is None:
        raise HTTPException(404, "Image not found")
    try:
        if media.filename in {f"{media.id}.png", f"{media.id}.wav"}:
            (audio_path if media.kind == "audio" else image_path)(media.id).unlink(missing_ok=True)
        db.execute(delete(MediaContentDB).where(MediaContentDB.media_id == media.id))
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

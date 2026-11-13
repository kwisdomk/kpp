"""Owner-bound canonical audio storage and local speech transcription."""

from dataclasses import asdict
from datetime import timedelta, timezone
import os
from pathlib import Path
import re
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.multimodal.asr import (
    AsrBusyError, AsrExecutionError, AsrTimeoutError, AsrUnavailableError,
    InvalidAudioError, transcribe_audio, validate_wav,
)
from app.core.config import IMAGE_TTL_MINUTES, MAX_MEDIA_BYTES, MEDIA_STORAGE_DIR
from app.db.database import AuditLogDB, MediaDB, UserDB, utc_now
from app.schemas.transcription import TranscriptionResponse


def sanitize_audio(content: bytes) -> bytes:
    try:
        canonical, _ = validate_wav(content)
        return canonical
    except InvalidAudioError as error:
        raise HTTPException(415, "Audio must be complete PCM16 mono 16 kHz WAV, up to 60 seconds") from error


def audio_path(media_id: str) -> Path:
    if re.fullmatch(r"media_[0-9a-f]{32}", media_id) is None:
        raise HTTPException(404, "Audio not found")
    root = MEDIA_STORAGE_DIR.resolve()
    path = (root / f"{media_id}.wav").resolve()
    if path.parent != root:
        raise HTTPException(404, "Audio not found")
    return path


def get_owned_audio(db: Session, user: UserDB, media_id: str) -> tuple[MediaDB, Path]:
    media = db.scalar(select(MediaDB).where(
        MediaDB.id == media_id, MediaDB.user_id == user.id,
        MediaDB.kind == "audio", MediaDB.active.is_(True),
    ))
    if media is None:
        raise HTTPException(404, "Audio not found")
    created = media.created_at.replace(tzinfo=timezone.utc) if media.created_at.tzinfo is None else media.created_at
    if created + timedelta(minutes=IMAGE_TTL_MINUTES) <= utc_now():
        raise HTTPException(410, "Audio expired; upload it again")
    path = audio_path(media.id)
    if not path.is_file():
        raise HTTPException(410, "Audio is unavailable; upload it again")
    if path.stat().st_size > MAX_MEDIA_BYTES:
        raise HTTPException(413, "Stored audio exceeds the allowed size")
    return media, path


def transcribe_owned_audio(db: Session, user: UserDB, media_id: str) -> TranscriptionResponse:
    _, path = get_owned_audio(db, user, media_id)
    started = time.perf_counter()
    trace_id = f"asr_{uuid.uuid4().hex}"
    outcome = "failed"
    try:
        model = os.getenv("WHISPER_MODEL_PATH", "").strip()
        if not model:
            raise HTTPException(503, "Local speech is unavailable; configure whisper.cpp and a verified model")
        try:
            result = transcribe_audio(
                path.read_bytes(), executable=os.getenv("WHISPER_CPP_CMD", "whisper-cli"),
                model_path=Path(model), temporary_directory=path.parent,
            )
        except AsrBusyError as error:
            raise HTTPException(429, "Speech transcription is busy; retry shortly") from error
        except AsrUnavailableError as error:
            raise HTTPException(503, "Local speech engine or model is unavailable") from error
        except AsrTimeoutError as error:
            raise HTTPException(504, "Local speech transcription timed out") from error
        except (AsrExecutionError, InvalidAudioError) as error:
            raise HTTPException(502, "Local speech transcription failed") from error
        outcome = result.status
        return TranscriptionResponse(
            media_id=media_id, **asdict(result), tool_trace_id=trace_id,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
    finally:
        db.add(AuditLogDB(session_id=trace_id, user_role=user.role,
                          tool_used="transcribe_audio", status=outcome, timestamp=utc_now()))
        db.commit()

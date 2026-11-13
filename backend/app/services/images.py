"""Bounded image decoding and private, server-named sanitized image storage."""

from datetime import timedelta, timezone
from io import BytesIO
from pathlib import Path
import re
import threading
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import IMAGE_TTL_MINUTES, MAX_IMAGE_EDGE, MAX_IMAGE_PIXELS, MAX_MEDIA_BYTES, MEDIA_STORAGE_DIR
from app.db.database import MediaDB, UserDB, utc_now

image_processing_slot = threading.BoundedSemaphore(1)
FORMAT_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def sanitize_image(content: bytes, declared_type: str) -> bytes:
    if not content:
        raise HTTPException(415, "Image is empty or invalid")
    if len(content) > MAX_MEDIA_BYTES:
        raise HTTPException(413, "Media exceeds 8 MiB limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content), formats=list(FORMAT_MIME)) as image:
                if FORMAT_MIME.get(image.format) != declared_type:
                    raise HTTPException(415, "Image bytes do not match the declared media type")
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_EDGE:
                    raise HTTPException(413, "Image exceeds 4 megapixels or 4096 pixels per edge; crop or resize it")
                if getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(415, "Animated or multi-frame images are not supported")
                image.verify()
            with Image.open(BytesIO(content), formats=list(FORMAT_MIME)) as image:
                image.load()
                with ImageOps.exif_transpose(image) as oriented:
                    with oriented.convert("RGBA") as pixels:
                        # Copy pixels into a fresh image so no input metadata is
                        # carried forward implicitly by a format-specific saver.
                        with Image.new("RGB", pixels.size, "white") as clean:
                            with pixels.getchannel("A") as alpha:
                                clean.paste(pixels, mask=alpha)
                            output = BytesIO()
                            clean.save(output, format="PNG", exif=b"", icc_profile=None)
        sanitized = output.getvalue()
        if len(sanitized) > MAX_MEDIA_BYTES:
            raise HTTPException(413, "Decoded image is too large to store; crop or resize it")
        return sanitized
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise HTTPException(413, "Image dimensions exceed safe decoding limits") from error
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
        raise HTTPException(415, "Image cannot be safely decoded") from error


def image_path(media_id: str) -> Path:
    if re.fullmatch(r"media_[0-9a-f]{32}", media_id) is None:
        raise HTTPException(404, "Image not found")
    root = MEDIA_STORAGE_DIR.resolve()
    path = (root / f"{media_id}.png").resolve()
    if path.parent != root:
        raise HTTPException(404, "Image not found")
    return path


def get_owned_image(db: Session, user: UserDB, media_id: str) -> tuple[MediaDB, Path]:
    media = db.scalar(select(MediaDB).where(
        MediaDB.id == media_id, MediaDB.user_id == user.id,
        MediaDB.kind == "image", MediaDB.active.is_(True),
    ))
    if media is None:
        raise HTTPException(404, "Image not found")
    created_at = media.created_at.replace(tzinfo=timezone.utc) if media.created_at.tzinfo is None else media.created_at
    if created_at + timedelta(minutes=IMAGE_TTL_MINUTES) <= utc_now():
        raise HTTPException(410, "Image expired; upload it again")
    path = image_path(media.id)
    if not path.is_file():
        raise HTTPException(410, "Image is unavailable; upload it again")
    if path.stat().st_size > MAX_MEDIA_BYTES:
        raise HTTPException(413, "Stored image exceeds the allowed size")
    return media, path

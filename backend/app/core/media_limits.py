"""Bound multipart upload transport bytes before the parser can spool a file."""

from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.core.config import MAX_MEDIA_BYTES

MAX_UPLOAD_REQUEST_BYTES = MAX_MEDIA_BYTES + 64 * 1024


class MediaUploadLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        is_upload = (
            scope["type"] == "http" and scope["method"] == "POST"
            and scope["path"].rstrip("/") in {"/media", "/api/v1/media"}
        )
        if not is_upload:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"detail": "Invalid upload length"}, status_code=400)(scope, receive, send)
            return
        if length < 0 or length > MAX_UPLOAD_REQUEST_BYTES:
            await JSONResponse({"detail": "Upload request exceeds size limit"}, status_code=413)(scope, receive, send)
            return
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_UPLOAD_REQUEST_BYTES:
                    raise HTTPException(413, "Upload request exceeds size limit")
            return message

        await self.app(scope, bounded_receive, send)

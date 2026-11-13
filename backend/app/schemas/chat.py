"""Chat schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Citation(BaseModel):
    source_id: str
    page: int | None = None
    chunk_id: str | None = None
    excerpt: str | None = None
    image_id: str | None = None


class ChatQuery(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=2000)
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)
    media_ids: list[str] = Field(default_factory=list, max_length=2)
    allow_external_processing: bool = False
    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_message(self) -> "ChatQuery":
        if not self.media_ids:
            self.resolved_text()
        elif self.text is not None or self.query is not None:
            self.resolved_text()
        if self.conversation_id and self.session_id and self.conversation_id != self.session_id:
            raise ValueError("conversation_id and legacy session_id must match")
        return self

    def resolved_text(self) -> str:
        value = self.text or self.query
        if not value or not value.strip():
            raise ValueError("Either text or query is required")
        return value


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    warnings: list[str]
    confidence: Literal["high", "medium", "low"]
    tool_executed: str
    execution_time_ms: float
    request_id: str | None = None
    conversation_id: str | None = None
    structured_results: dict[str, object] = Field(default_factory=dict)
    tool_trace_id: str | None = None
    needs_human_review: bool = False
    latency_ms: float | None = None

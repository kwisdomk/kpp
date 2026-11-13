"""Speech output: configured English decoding, never confidence or authority."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TranscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: str
    text: str = Field(max_length=16000)
    language: Literal["en"]
    duration_seconds: float = Field(gt=0, le=60)
    status: Literal["transcribed", "no_speech"]
    tool_trace_id: str
    latency_ms: float

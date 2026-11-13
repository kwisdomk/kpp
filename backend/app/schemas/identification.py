"""OCR response contract: row matching, not verified equipment recognition."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IdentificationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    model_number: str
    name: str
    category: str
    source_id: str
    match_method: Literal["normalized_model_code"] = "normalized_model_code"


class IdentificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: str
    status: Literal["identified", "ambiguous", "unidentified"]
    reason: Literal["one_model_match", "multiple_model_matches", "no_match", "no_text"]
    candidates: list[IdentificationCandidate] = Field(max_length=10)
    candidates_truncated: bool = False
    requires_confirmation: bool = True
    warnings: list[str]
    ocr_engine: Literal["tesseract"] = "tesseract"
    tool_trace_id: str
    latency_ms: float

    @model_validator(mode="after")
    def validate_outcome(self) -> "IdentificationResponse":
        count = len(self.candidates)
        if self.status == "identified" and (count != 1 or self.reason != "one_model_match"):
            raise ValueError("identified requires exactly one candidate")
        if self.status == "ambiguous" and (count < 2 or self.reason != "multiple_model_matches"):
            raise ValueError("ambiguous requires multiple candidates")
        if self.status == "unidentified" and (count or self.reason not in {"no_match", "no_text"}):
            raise ValueError("unidentified cannot expose candidates")
        return self

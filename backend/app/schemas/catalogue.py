"""Catalogue and deterministic calculation contracts."""

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class PriceLineItem(BaseModel):
    product_id: int
    model_number: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int


class PriceRequest(BaseModel):
    items: list[tuple[int, int]] = Field(min_length=1)
    tax_rate_bps: int | None = Field(default=None, ge=0, le=10000)


class PriceResponse(BaseModel):
    line_items: list[PriceLineItem]
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    currency: str = "KES"
    price_date: date
    not_binding_quote: bool = True
    source_row_ids: list[str]


class CompareRequest(BaseModel):
    product_ids: list[int] = Field(min_length=2, max_length=10)
    fields: list[str] = Field(default_factory=list, max_length=20)


class CompareResponse(BaseModel):
    products: list[dict[str, object]]
    fields: list[str]


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ReviewRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)

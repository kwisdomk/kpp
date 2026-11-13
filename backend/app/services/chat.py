"""Deterministic, role-aware chat orchestration."""

from __future__ import annotations

import os
import re
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import ProductAccessDB, UserDB
from app.services.ai import generate_grounded_answer
from app.services.media import ChatAttachment
from app.tools.catalog import lookup_products
from app.tools.safety import safety_notice
from app.tools.comparison import compare_catalogue
from app.schemas.catalogue import CompareRequest
from ai.multimodal.nameplate_ocr import ModelCandidate, identify_models

Confidence = Literal["high", "medium", "low"]
ChatResult = tuple[str, str, list[str], list[str], Confidence]


def _is_restricted_query(query: str) -> bool:
    return bool(
        re.search(
            r"\b(internal\s+margins?|profit\s+margins?|markups?|cost\s+prices?|restricted\s+service\s+manuals?|service\s+manuals?)\b",
            query,
            flags=re.IGNORECASE,
        )
    )


def route_query(query: str, user: UserDB, db: Session, *, structured_results: dict | None = None, attachments: list[ChatAttachment] | None = None) -> ChatResult:
    role = user.role
    lowered = query.lower()
    attachments = attachments or []
    if _is_restricted_query(query) and role == "customer":
        return (
            "I cannot provide internal margins or restricted service manuals.",
            "access_control",
            [],
            ["This request is restricted to authorised Jenga engineers."],
            "high",
        )
    if attachments:
        products = lookup_products(db, user)
        if db.scalar(select(ProductAccessDB.product_id).where(
            ProductAccessDB.product_id.in_([product.id for product in products]),
            ProductAccessDB.access_level == "engineer",
        ).limit(1)) is not None:
            raise HTTPException(503, "Restricted catalogue context cannot use hosted attachment processing")
        answer = generate_grounded_answer(
            query,
            role,
            products,
            attachments=attachments,
        )
        if answer is None:
            raise HTTPException(
                status_code=503,
                detail="Attachment analysis requires OPENAI_API_KEY to be configured.",
            )
        return (
            answer,
            "openai_assistant",
            ["Product catalog", *(f"User attachment: {item.filename}" for item in attachments)],
            [
                "AI-generated answer; verify important specifications with an authorised consultant.",
                "Uploaded materials are user-provided and are not independently verified.",
            ],
            "medium",
        )
    if re.search(r"\b(compare|comparison|versus|vs)\b", lowered):
        products = lookup_products(db, user)
        matches = identify_models(query, [ModelCandidate(str(row.id), row.model_number) for row in products]).candidates
        # Do not silently drop an unknown code from an otherwise valid comparison.
        code_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9]*[-/][A-Za-z0-9][A-Za-z0-9./-]*\b", query)
        unknown_codes = [token for token in code_tokens if any(char.isdigit() for char in token)
                         and not identify_models(token, [ModelCandidate(row.product_id, row.model_number) for row in matches]).candidates]
        if not 2 <= len(matches) <= 10 or unknown_codes:
            return (
                "Please provide two to ten exact catalogue model codes that are available to your account. I cannot resolve every requested model confidently.",
                "comparison_clarification", [], [], "low",
            )
        result = compare_catalogue(CompareRequest(product_ids=[int(row.product_id) for row in matches]), db, user)
        different_fields = [field for field in result.fields
                            if field != "model_number" and len({str(row[field]) for row in result.products}) > 1]
        if structured_results is not None:
            structured_results["comparison"] = {**result.model_dump(), "different_fields": different_fields}
        def cell(value: object) -> str:
            return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
        header = "| Field | " + " | ".join(cell(row["model_number"]) for row in result.products) + " |"
        separator = "| --- | " + " | ".join("---" for _ in result.products) + " |"
        rows = ["| " + cell(field) + " | " + " | ".join(cell(row[field]) for row in result.products) + " |"
                for field in result.fields]
        answer = "Catalogue comparison:\n\n" + "\n".join([header, separator, *rows])
        answer += "\n\nStored fields that differ: " + (", ".join(different_fields) or "none") + "."
        answer += " Task suitability is not established by these rows; approved source-backed specifications are needed."
        return (answer, "compare_products", [f"product:{row['id']}" for row in result.products],
                ["Synthetic demo catalogue; specifications are not approved manufacturer evidence.",
                 "Catalogue price — not a binding quote."], "low")
    if any(word in lowered for word in ("price", "cost", "quote", "pricing")):
        products = lookup_products(db, user)
        if not products:
            return "No product pricing data is currently available.", "price_lookup", [], ["Catalog data unavailable."], "low"
        lines = [f"{product.name} ({product.model_number}): KSh {product.price_ksh:,}" for product in products]
        return (
            "Available catalog pricing: " + "; ".join(lines),
            "price_lookup",
            [f"product:{product.id}" for product in products],
            ["Prices are indicative and should be confirmed by an authorised consultant."],
            "high",
        )
    if role == "engineer" and any(word in lowered for word in ("fault", "troubleshoot", "safety", "alarm")):
        answer, citations, warnings, confidence = safety_notice()
        return answer, "safety_notice", citations, warnings, confidence
    products = lookup_products(db, user)
    if os.getenv("OPENAI_API_KEY") and not os.getenv("LLM_BASE_URL", "").strip():
        restricted_id = db.scalar(select(ProductAccessDB.product_id).where(
            ProductAccessDB.product_id.in_([product.id for product in products]),
            ProductAccessDB.access_level == "engineer",
        ).limit(1))
        if restricted_id is not None:
            raise HTTPException(503, "Restricted catalogue context requires the configured local model endpoint")
    answer = generate_grounded_answer(query, role, products)
    if answer is not None:
        return (
            answer,
            "local_assistant" if os.getenv("LLM_BASE_URL", "").strip() else "openai_assistant",
            [f"product:{product.id}" for product in products],
            ["AI-generated answer using synthetic demo catalogue rows, not approved manufacturer documents; verify specifications with an authorised consultant."],
            "medium",
        )
    return (
        "I can answer grounded questions about Jenga products, specifications, and catalog pricing. "
        "Please include a product name or model number.",
        "product_catalog",
        ["Product catalog"],
        ["AI is not configured; this response is limited to verified catalog data."],
        "medium",
    )

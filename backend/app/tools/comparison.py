"""Shared authorized comparison tool used by the API and chat, without inference."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.database import UserDB
from app.schemas.catalogue import CompareRequest, CompareResponse
from app.services.authorization import get_authorized_product


def compare_catalogue(payload: CompareRequest, db: Session, user: UserDB) -> CompareResponse:
    fields = payload.fields or ["category", "model_number", "specifications", "price_ksh"]
    allowed = {"id", "name", "category", "model_number", "specifications", "price_ksh"}
    if any(field not in allowed for field in fields):
        raise HTTPException(422, "Unsupported comparison field")
    if len(set(payload.product_ids)) < 2:
        raise HTTPException(422, "Choose at least two distinct products")
    products = [get_authorized_product(db, user, product_id) for product_id in payload.product_ids]
    if any(product is None for product in products):
        raise HTTPException(404, "Product not found")
    return CompareResponse(
        products=[{"id": product.id, **{field: getattr(product, field) for field in fields}}
                  for product in products if product is not None], fields=fields,
    )

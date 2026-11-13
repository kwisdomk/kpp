"""Catalogue authorization predicates applied before ORM rows are retrieved."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import ProductAccessDB, ProductDB, UserDB


def authorized_products_statement(user: UserDB):
    levels = ()
    if user.is_active and user.role == "engineer":
        levels = ("public", "engineer")
    elif user.is_active and user.role == "customer":
        levels = ("public",)
    return (
        select(ProductDB)
        .join(ProductAccessDB, ProductAccessDB.product_id == ProductDB.id)
        .where(ProductAccessDB.access_level.in_(levels))
    )


def get_authorized_product(db: Session, user: UserDB, product_id: int) -> ProductDB | None:
    return db.scalar(authorized_products_statement(user).where(ProductDB.id == product_id))

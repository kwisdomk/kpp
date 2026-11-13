"""Catalog lookup tool."""

from sqlalchemy.orm import Session

from app.db.database import ProductDB, UserDB
from app.services.authorization import authorized_products_statement


def lookup_products(db: Session, user: UserDB) -> list[ProductDB]:
    return list(db.scalars(authorized_products_statement(user).order_by(ProductDB.name)).all())

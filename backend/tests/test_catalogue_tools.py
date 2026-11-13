"""Regression coverage for authenticated catalogue calculation and comparison APIs."""

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.catalog import router
from app.auth.security import get_current_user
from app.db.database import Base, ProductAccessDB, ProductDB, get_db


@pytest.fixture
def catalogue_client(tmp_path) -> Generator[tuple[TestClient, dict[str, str]], None, None]:
    """Provide API routes backed only by a per-test temporary SQLite database."""
    database_path = tmp_path / "catalogue_test.sqlite"
    test_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    test_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with test_session() as db:
        db.add_all(
            [
                ProductDB(
                    id=1,
                    category="generator",
                    name="Synthetic Generator One",
                    model_number="SYN-GEN-1",
                    specifications="Synthetic rating: 10 kW",
                    price_ksh=1000,
                ),
                ProductDB(
                    id=2,
                    category="transformer",
                    name="Synthetic Transformer Two",
                    model_number="SYN-TR-2",
                    specifications="Synthetic rating: 20 kVA",
                    price_ksh=2500,
                ),
            ]
        )
        db.flush()
        db.add_all([ProductAccessDB(product_id=product_id, access_level="public") for product_id in (1, 2)])
        db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_db() -> Generator[Session, None, None]:
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    tokens: dict[str, str] = {}
    for role in ("customer", "engineer"):
        tokens[role] = f"synthetic-{role}-token"

    # This fixture auth derives roles only from its private token map.
    from fastapi import Header, HTTPException

    def authenticate(authorization: str | None = Header(default=None)):
        role = next(
            (candidate for candidate, token in tokens.items() if authorization == f"Bearer {token}"),
            None,
        )
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return SimpleNamespace(id=role, username=f"{role}@example.test", role=role, is_active=True)

    app.dependency_overrides[get_current_user] = authenticate

    try:
        with TestClient(app) as client:
            yield client, tokens
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()


@pytest.mark.parametrize("role", ["customer", "engineer"])
def test_price_returns_exact_integer_subtotal_tax_and_total(catalogue_client, role: str) -> None:
    client, tokens = catalogue_client
    response = client.post(
        "/catalogue/price",
        headers={"Authorization": f"Bearer {tokens[role]}"},
        json={"items": [[1, 2], [2, 1]], "tax_rate_bps": 875},
    )

    assert response.status_code == 200
    body = response.json()
    assert [(line["unit_price_minor"], line["line_total_minor"]) for line in body["line_items"]] == [
        (100000, 200000),
        (250000, 250000),
    ]
    assert body["subtotal_minor"] == 450000
    assert body["tax_minor"] == 39375
    assert body["total_minor"] == 489375
    assert body["source_row_ids"] == ["product:1", "product:2"]


@pytest.mark.parametrize("items", [[[1, 0]], [[1, -2]]])
def test_price_rejects_non_positive_quantities(catalogue_client, items) -> None:
    client, tokens = catalogue_client
    response = client.post(
        "/catalogue/price",
        headers={"Authorization": f"Bearer {tokens['customer']}"},
        json={"items": items},
    )

    assert response.status_code == 422


def test_price_rejects_missing_product(catalogue_client) -> None:
    client, tokens = catalogue_client
    response = client.post(
        "/catalogue/price",
        headers={"Authorization": f"Bearer {tokens['engineer']}"},
        json={"items": [[999, 1]]},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("role", ["customer", "engineer"])
def test_comparison_returns_requested_values(catalogue_client, role: str) -> None:
    client, tokens = catalogue_client
    response = client.post(
        "/catalogue/compare",
        headers={"Authorization": f"Bearer {tokens[role]}"},
        json={"product_ids": [1, 2], "fields": ["model_number", "price_ksh"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "products": [
            {"id": 1, "model_number": "SYN-GEN-1", "price_ksh": 1000},
            {"id": 2, "model_number": "SYN-TR-2", "price_ksh": 2500},
        ],
        "fields": ["model_number", "price_ksh"],
    }


def test_comparison_rejects_unsupported_fields(catalogue_client) -> None:
    client, tokens = catalogue_client
    response = client.post(
        "/catalogue/compare",
        headers={"Authorization": f"Bearer {tokens['customer']}"},
        json={"product_ids": [1, 2], "fields": ["supplier_cost"]},
    )

    assert response.status_code == 422


def test_catalogue_denies_unauthenticated_request(catalogue_client) -> None:
    client, _ = catalogue_client

    response = client.post("/catalogue/price", json={"items": [[1, 1]]})

    assert response.status_code == 401


def test_comparison_rejects_missing_product(catalogue_client) -> None:
    client, tokens = catalogue_client
    response = client.post(
        "/catalogue/compare", headers={"Authorization": f"Bearer {tokens['engineer']}"},
        json={"product_ids": [1, 999]},
    )
    assert response.status_code == 404


def test_comparison_denies_unauthenticated_request(catalogue_client) -> None:
    client, _ = catalogue_client
    assert client.post("/catalogue/compare", json={"product_ids": [1, 2]}).status_code == 401

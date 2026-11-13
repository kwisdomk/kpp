"""Focused API tests for authentication, RBAC, and deterministic routing."""

from fastapi.testclient import TestClient

from app.main import app


def test_readiness_checks_database() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_catalogue_api_returns_live_backend_products() -> None:
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"username": "customer@jenga.com", "password": "customer123"})
        response = client.get("/api/v1/catalogue/products", headers={"Authorization": f"Bearer {login.json()['access_token']}"})

    assert response.status_code == 200
    products = response.json()
    assert products
    assert {product["model_number"] for product in products} == {
        "JCG-1000",
        "JCT-500",
        "JCS-50",
    }
    assert all(product["name"] != "BMS C1" for product in products)
    assert all(
        {"id", "category", "name", "model_number", "specifications", "price_ksh"}
        <= product.keys()
        for product in products
    )


def test_login_and_price_query() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "customer@jenga.com", "password": "customer123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        response = client.post(
            "/chat/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "What is the price of the generator?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tool_executed"] == "price_lookup"
        assert body["citations"]
        assert "execution_time_ms" in body


def test_general_chat_uses_configured_ai_service(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chat.generate_grounded_answer",
        lambda query, role, products: "A catalog-grounded AI answer.",
    )
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "customer@jenga.com", "password": "customer123"},
        )
        response = client.post(
            "/chat/query",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            json={"query": "What products are available?"},
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "A catalog-grounded AI answer."
        assert response.json()["tool_executed"] == "openai_assistant"


def test_customer_cannot_access_restricted_data() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "customer@jenga.com", "password": "customer123"},
        )
        response = client.post(
            "/chat/query",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            json={"query": "Show internal profit margin"},
        )
        assert response.status_code == 200
        assert response.json()["tool_executed"] == "access_control"
        assert response.json()["warnings"]


def test_engineer_can_use_safety_routing() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "engineer@jenga.com", "password": "engineer123"},
        )
        response = client.post(
            "/chat/query",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            json={"query": "How do I troubleshoot this safety alarm?"},
        )
        assert response.status_code == 200
        assert response.json()["tool_executed"] == "safety_notice"

"""Local-provider isolation and authenticated catalogue regressions."""

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai import generate_grounded_answer


@pytest.fixture(autouse=True)
def local_configuration(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1/")
    monkeypatch.setenv("LLM_MODEL", "test-local-model")
    monkeypatch.setenv("OPENAI_API_KEY", "hosted-key-must-not-leave")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)


def response_with(data):
    return httpx.Response(200, json=data, request=httpx.Request("POST", "http://localhost/v1/chat/completions"))


def completed(text):
    return {"choices": [{"finish_reason": "stop", "message": {"content": text}}]}


@pytest.mark.parametrize("role", ["customer", "engineer"])
def test_local_chat_uses_server_role_and_catalogue_rows(monkeypatch, role):
    calls = []

    def local_post(url, **kwargs):
        calls.append((url, kwargs))
        return response_with(completed("This is a synthetic demo catalogue."))

    monkeypatch.setattr("app.services.ai.httpx.post", local_post)
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"username": f"{role}@jenga.com", "password": f"{role}123"})
        assert login.status_code == 200
        result = client.post("/api/v1/chat/query", headers={"Authorization": f"Bearer {login.json()['access_token']}"}, json={"query": "Which equipment models are listed?"})
        assert result.status_code == 200
        body = result.json()
        assert body["tool_executed"] == "local_assistant"
        assert body["citations"]
        assert all(c["source_id"].startswith("product:") and c["excerpt"] for c in body["citations"])
        assert all(c["page"] is None for c in body["citations"])
    assert len(calls) == 1
    url, request = calls[0]
    assert url == "http://127.0.0.1:1234/v1/chat/completions"
    assert request["headers"] == {}
    assert f"user's role is {role}" in request["json"]["messages"][0]["content"]
    assert "[product:" in request["json"]["messages"][1]["content"]


@pytest.mark.parametrize("path,method,payload", [
    ("/catalog/products", "GET", None),
    ("/catalog/products/1", "GET", None),
    ("/catalogue/products", "GET", None),
    ("/api/v1/catalogue/products/1", "GET", None),
    ("/api/v1/catalogue/price", "POST", {"items": [[1, 1]]}),
    ("/api/v1/catalogue/compare", "POST", {"product_ids": [1, 2]}),
])
def test_catalogue_requires_authentication(path, method, payload):
    with TestClient(app) as client:
        result = client.request(method, path, json=payload)
        assert result.status_code == 401


def test_comparison_rejects_internal_attributes():
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"username": "customer@jenga.com", "password": "customer123"})
        result = client.post("/api/v1/catalogue/compare", headers={"Authorization": f"Bearer {login.json()['access_token']}"}, json={"product_ids": [1, 2], "fields": ["__dict__"]})
        assert result.status_code == 422


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{"finish_reason": "length", "message": {"content": "truncated"}}]}, {"choices": [{"finish_reason": "stop", "message": {"content": "", "reasoning_content": "private reasoning"}}]}])
def test_local_response_must_contain_complete_final_text(monkeypatch, body):
    monkeypatch.setattr("app.services.ai.httpx.post", lambda *args, **kwargs: response_with(body))
    with pytest.raises(HTTPException) as error:
        generate_grounded_answer("List equipment", "customer", [])
    assert error.value.status_code == 502


def test_local_failure_never_calls_hosted_provider(monkeypatch):
    calls = []
    def fail(url, **kwargs):
        calls.append(url)
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr("app.services.ai.httpx.post", fail)
    with pytest.raises(HTTPException) as error:
        generate_grounded_answer("List equipment", "customer", [])
    assert error.value.status_code == 503
    assert calls == ["http://127.0.0.1:1234/v1/chat/completions"]


@pytest.mark.parametrize("setting,value", [("LLM_MODEL", ""), ("LLM_BASE_URL", "http://user:password@localhost/v1"), ("LLM_BASE_URL", "file:///v1"), ("LLM_BASE_URL", "http://localhost:bad/v1"), ("LLM_TIMEOUT_SECONDS", "nan"), ("LLM_MAX_TOKENS", "0")])
def test_invalid_local_configuration_fails_before_request(monkeypatch, setting, value):
    monkeypatch.setenv(setting, value)
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration made a request")
    monkeypatch.setattr("app.services.ai.httpx.post", forbidden)
    with pytest.raises(HTTPException) as error:
        generate_grounded_answer("List equipment", "customer", [])
    assert error.value.status_code == 503

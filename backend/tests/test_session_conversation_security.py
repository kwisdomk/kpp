"""Session revocation and conversation boundaries, with isolated SQLite fixtures."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.auth.security as security
import app.db.database as database
import app.main as main_module
from app.core.config import SESSION_COOKIE_NAME
from app.db.database import AuditLogDB, ConversationDB, ReviewRequestDB, SessionDB, UserDB, utc_now


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'session_security.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "app.services.chat.generate_grounded_answer",
        lambda *args: "Mocked inference for authorization regression tests.",
    )

    def unexpected_provider(*args, **kwargs):
        pytest.fail("Session/conversation tests must never call a model provider")

    monkeypatch.setattr("app.services.ai.httpx.post", unexpected_provider)
    try:
        with TestClient(main_module.app) as client:
            yield client, session_factory
    finally:
        engine.dispose()


def login(client, role="customer"):
    result = client.post(
        "/api/v1/auth/login",
        json={"username": f"{role}@jenga.com", "password": f"{role}123"},
    )
    assert result.status_code == 200
    return result.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def session_hash(token):
    return jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])["sid"]


@pytest.mark.parametrize("role", ["customer", "engineer"])
@pytest.mark.parametrize("transport", ["cookie", "bearer"])
def test_me_uses_active_server_identity(isolated_app, role, transport):
    client, _ = isolated_app
    token = login(client, role)
    headers = bearer(token) if transport == "bearer" else {}
    if transport == "bearer":
        client.cookies.clear()
    result = client.get("/api/v1/auth/me", headers=headers)
    assert result.status_code == 200
    assert result.json()["role"] == role
    assert result.json()["username"] == f"{role}@jenga.com"


@pytest.mark.parametrize("role", ["customer", "engineer"])
@pytest.mark.parametrize("transport", ["cookie", "bearer"])
@pytest.mark.parametrize("expiry", ["idle", "absolute"])
def test_expired_session_cannot_access_catalogue(isolated_app, role, transport, expiry):
    client, session_factory = isolated_app
    token = login(client, role)
    token_hash = session_hash(token)
    with session_factory() as db:
        session = db.scalar(select(SessionDB).where(SessionDB.token_hash == token_hash))
        if expiry == "idle":
            session.last_active_at = utc_now() - timedelta(days=1)
        else:
            session.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    headers = bearer(token) if transport == "bearer" else {}
    if transport == "bearer":
        client.cookies.clear()
    assert client.get("/api/v1/catalogue/products", headers=headers).status_code == 401
    with session_factory() as db:
        session = db.scalar(select(SessionDB).where(SessionDB.token_hash == token_hash))
        assert session.revoked_at is not None


@pytest.mark.parametrize("transport", ["cookie", "bearer"])
def test_logout_revokes_both_credentials_for_that_session(isolated_app, transport):
    client, _ = isolated_app
    token = login(client)
    cookie = client.cookies.get(SESSION_COOKIE_NAME)
    headers = bearer(token) if transport == "bearer" else {}
    if transport == "bearer":
        client.cookies.clear()
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    client.cookies.clear()
    assert client.get("/api/v1/catalogue/products", headers=bearer(token)).status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, cookie)
    assert client.get("/api/v1/catalogue/products").status_code == 401
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204


def test_logout_does_not_revoke_a_different_login(isolated_app):
    client, _ = isolated_app
    first_token = login(client)
    second_token = login(client)
    client.cookies.clear()
    assert first_token != second_token
    assert client.post("/api/v1/auth/logout", headers=bearer(first_token)).status_code == 204
    assert client.get("/api/v1/catalogue/products", headers=bearer(first_token)).status_code == 401
    assert client.get("/api/v1/catalogue/products", headers=bearer(second_token)).status_code == 200


@pytest.mark.parametrize("expired_bearer", [False, True])
def test_logout_revokes_all_valid_sessions_submitted_in_the_request(isolated_app, expired_bearer):
    client, _ = isolated_app
    first_token = login(client)
    second_token = login(client)
    second_cookie = client.cookies.get(SESSION_COOKIE_NAME)
    submitted_token = first_token
    if expired_bearer:
        claims = jwt.decode(second_token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        claims["exp"] = int((utc_now() - timedelta(seconds=1)).timestamp())
        submitted_token = jwt.encode(claims, security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert client.post("/api/v1/auth/logout", headers=bearer(submitted_token)).status_code == 204
    client.cookies.clear()
    assert client.get("/api/v1/catalogue/products", headers=bearer(second_token)).status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, second_cookie)
    assert client.get("/api/v1/catalogue/products").status_code == 401
    client.cookies.clear()
    expected_first_status = 200 if expired_bearer else 401
    assert client.get("/api/v1/catalogue/products", headers=bearer(first_token)).status_code == expected_first_status


@pytest.mark.parametrize("transport", ["cookie", "bearer"])
def test_disabling_account_blocks_existing_session_and_login(isolated_app, transport):
    client, session_factory = isolated_app
    token = login(client)
    with session_factory() as db:
        user = db.scalar(select(UserDB).where(UserDB.username == "customer@jenga.com"))
        user.is_active = False
        db.commit()
    headers = bearer(token) if transport == "bearer" else {}
    if transport == "bearer":
        client.cookies.clear()
    assert client.get("/api/v1/catalogue/products", headers=headers).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "customer@jenga.com", "password": "customer123"},
    ).status_code == 401
    # Reactivating the account must not revive a session rejected while disabled.
    with session_factory() as db:
        user = db.scalar(select(UserDB).where(UserDB.username == "customer@jenga.com"))
        user.is_active = True
        db.commit()
    assert client.get("/api/v1/catalogue/products", headers=headers).status_code == 401


@pytest.mark.parametrize("change", ["legacy", "unknown_session", "wrong_role", "wrong_user", "expired"])
def test_invalid_bearer_cannot_fall_back_to_an_active_cookie(isolated_app, change):
    client, _ = isolated_app
    token = login(client)
    claims = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    if change == "legacy":
        del claims["sid"]
    elif change == "unknown_session":
        claims["sid"] = "0" * 64
    elif change == "wrong_role":
        claims["role"] = "engineer"
    elif change == "wrong_user":
        claims["sub"] = "engineer@jenga.com"
    else:
        claims["exp"] = int((utc_now() - timedelta(seconds=1)).timestamp())
    invalid = jwt.encode(claims, security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert client.get("/api/v1/catalogue/products", headers=bearer(invalid)).status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 200


def test_bearer_identity_wins_over_a_different_valid_cookie(isolated_app):
    client, _ = isolated_app
    customer_token = login(client, "customer")
    login(client, "engineer")
    result = client.get("/api/v1/auth/me", headers=bearer(customer_token))
    assert result.status_code == 200
    assert result.json()["role"] == "customer"


def test_database_role_change_invalidates_old_bearer(isolated_app):
    client, session_factory = isolated_app
    token = login(client)
    with session_factory() as db:
        user = db.scalar(select(UserDB).where(UserDB.username == "customer@jenga.com"))
        user.role = "engineer"
        db.commit()
    client.cookies.clear()
    assert client.get("/api/v1/catalogue/products", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("reference_field", ["conversation_id", "session_id"])
@pytest.mark.parametrize("state", ["foreign", "missing", "finished"])
def test_chat_checks_conversation_before_inference(isolated_app, monkeypatch, reference_field, state):
    client, session_factory = isolated_app
    token = login(client)
    conversation_id = "conv_does_not_exist"
    if state != "missing":
        conversation_id = client.post(
            "/api/v1/conversations", headers=bearer(token), json={"title": "Owned test"},
        ).json()["id"]
    if state == "foreign":
        token = login(client, "engineer")
    elif state == "finished":
        assert client.post(
            f"/api/v1/conversations/{conversation_id}/finish", headers=bearer(token),
        ).status_code == 204
    client.cookies.clear()

    def forbidden(*args):
        pytest.fail("Rejected conversations must never enter retrieval/inference")

    monkeypatch.setattr("app.api.chat.route_query", forbidden)
    result = client.post(
        "/api/v1/chat/query", headers=bearer(token),
        json={"query": "List models", reference_field: conversation_id},
    )
    assert result.status_code == (409 if state == "finished" else 404)
    with session_factory() as db:
        assert list(db.scalars(select(AuditLogDB))) == []


def test_first_chat_creates_owned_conversation_and_working_review_reference(isolated_app):
    client, session_factory = isolated_app
    token = login(client)
    client.cookies.clear()
    headers = bearer(token)
    first = client.post("/api/v1/chat/query", headers=headers, json={"query": "List models"})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert conversation_id.startswith("conv_")
    assert first.json()["tool_trace_id"] == conversation_id
    assert client.get(f"/api/v1/conversations/{conversation_id}", headers=headers).status_code == 200
    second = client.post(
        "/api/v1/chat/query", headers=headers,
        json={"query": "List models again", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    review = client.post(
        "/api/v1/reviews", headers=headers,
        json={"conversation_id": conversation_id, "reason": "Test report for an owned answer"},
    )
    assert review.status_code == 200
    with session_factory() as db:
        user = db.scalar(select(UserDB).where(UserDB.username == "customer@jenga.com"))
        conversation = db.get(ConversationDB, conversation_id)
        assert conversation.user_id == user.id
        stored_review = db.get(ReviewRequestDB, review.json()["id"])
        assert stored_review.conversation_id == conversation_id
        assert stored_review.user_id == user.id
        assert len(list(db.scalars(select(ConversationDB)))) == 1
        assert len(list(db.scalars(select(AuditLogDB)))) == 2
    foreign_token = login(client, "engineer")
    client.cookies.clear()
    assert client.post(
        "/api/v1/reviews", headers=bearer(foreign_token),
        json={"conversation_id": conversation_id, "reason": "Foreign report"},
    ).status_code == 404


@pytest.mark.parametrize("payload", [
    {}, {"query": "   "}, {"text": "\n\t"},
    {"query": "List models", "conversation_id": "conv_a", "session_id": "conv_b"},
])
def test_invalid_chat_request_is_rejected_before_creating_conversation(isolated_app, payload):
    client, session_factory = isolated_app
    token = login(client)
    result = client.post("/api/v1/chat/query", headers=bearer(token), json=payload)
    assert result.status_code == 422
    with session_factory() as db:
        assert list(db.scalars(select(ConversationDB))) == []


def test_owned_legacy_session_reference_stays_supported(isolated_app):
    client, _ = isolated_app
    token = login(client)
    conversation_id = client.post(
        "/api/v1/conversations", headers=bearer(token), json={},
    ).json()["id"]
    result = client.post(
        "/api/v1/chat/query", headers=bearer(token),
        json={"query": "List models", "session_id": conversation_id},
    )
    assert result.status_code == 200
    assert result.json()["conversation_id"] == conversation_id

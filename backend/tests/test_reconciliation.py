"""Regression checks for the local/upstream integration boundaries."""

import pytest
from fastapi import HTTPException

from app.services.ai import generate_grounded_answer
from app.services.media import ChatAttachment
from app.db.database import UserDB
from sqlalchemy import select
from test_image_identification import image_client, sign_in, upload


@pytest.mark.parametrize("role", ["customer", "engineer"])
def test_owned_comparison_history_survives_reload_and_rejects_revoked_token(image_client, role):
    client, _, _ = image_client
    headers = sign_in(client, role)
    response = client.post("/api/v1/chat/query", headers=headers, json={"query": "Compare JCG-1000 and JCS-50"})
    assert response.status_code == 200
    body = response.json()
    path = f"/api/v1/conversations/{body['conversation_id']}/messages"
    history = client.get(path, headers=headers)
    assert history.status_code == 200
    assistant = history.json()[-1]
    assert assistant["metadata"]["comparison"] == body["structured_results"]["comparison"]
    assert assistant["metadata"]["citations"] == body["citations"]
    foreign_headers = sign_in(client, "engineer" if role == "customer" else "customer")
    assert client.get(path, headers=foreign_headers).status_code == 404
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get(path, headers=headers).status_code == 401


@pytest.mark.parametrize("local_selected", [False, True])
def test_hosted_media_denied_before_loading_or_inference(image_client, monkeypatch, local_selected):
    client, _, _ = image_client
    headers = sign_in(client, "engineer")
    media_id = upload(client, headers).json()["id"]
    monkeypatch.setenv("ENABLE_HOSTED_MEDIA", "true")
    if local_selected:
        monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1")
    else:
        monkeypatch.delenv("LLM_BASE_URL", raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Hosted media must be rejected before loading or provider calls")

    monkeypatch.setattr("app.api.chat.load_chat_attachments", forbidden)
    response = client.post("/api/v1/chat/query", headers=headers, json={
        "query": "Inspect this", "media_ids": [media_id], "allow_external_processing": True,
    })
    assert response.status_code == 503
    expected = "local endpoint" if local_selected else "Restricted catalogue"
    assert expected in response.json()["detail"]


def test_default_media_profile_rejects_documents_and_compressed_audio(image_client, monkeypatch):
    client, _, _ = image_client
    headers = sign_in(client)
    monkeypatch.delenv("ENABLE_HOSTED_MEDIA", raising=False)
    for kind, name, mime, content in [
        ("document", "note.txt", "text/plain", b"Synthetic note"),
        ("audio", "voice.webm", "audio/webm", b"\x1aE\xdf\xa3voice"),
    ]:
        response = client.post(f"/api/v1/media?kind={kind}", headers=headers,
                               files={"file": (name, content, mime)})
        assert response.status_code == 415


def test_local_model_never_forwards_hosted_attachments(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LLM_MODEL", "test-local")
    monkeypatch.setenv("ENABLE_HOSTED_MEDIA", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def forbidden(*args, **kwargs):
        pytest.fail("Neither provider may receive attachments from the selected local text adapter")

    monkeypatch.setattr("app.services.ai.httpx.post", forbidden)
    with pytest.raises(HTTPException) as error:
        generate_grounded_answer("Inspect", "customer", [], attachments=[
            ChatAttachment(filename="synthetic.txt", content_type="text/plain", text="Synthetic input"),
        ])
    assert error.value.status_code == 503


def test_demoted_account_cannot_retrieve_engineer_message_history(image_client):
    client, sessions, _ = image_client
    engineer_headers = sign_in(client, "engineer")
    response = client.post("/api/v1/chat/query", headers=engineer_headers,
                           json={"query": "What are the catalogue prices?"})
    assert response.status_code == 200
    path = f"/api/v1/conversations/{response.json()['conversation_id']}/messages"
    assert client.get(path, headers=engineer_headers).json()
    with sessions() as db:
        user = db.scalar(select(UserDB).where(UserDB.username == "engineer@jenga.com"))
        user.role = "customer"
        db.commit()
    assert client.get(path, headers=engineer_headers).status_code == 401
    login = client.post("/api/v1/auth/login", json={
        "username": "engineer@jenga.com", "password": "engineer123",
    })
    assert login.status_code == 200
    client.cookies.clear()
    customer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    history = client.get(path, headers=customer_headers)
    assert history.status_code == 200
    assert history.json() == []

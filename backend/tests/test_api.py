"""Focused API tests for authentication, RBAC, and deterministic routing."""

from fastapi.testclient import TestClient

from app.main import app


def test_readiness_checks_database() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_root_health_supports_default_platform_probe() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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


def test_account_chat_reuses_conversation_and_keeps_history_private() -> None:
    with TestClient(app) as client:
        engineer_login = client.post(
            "/auth/login",
            json={"username": "engineer@jenga.com", "password": "engineer123"},
        )
        customer_login = client.post(
            "/auth/login",
            json={"username": "customer@jenga.com", "password": "customer123"},
        )
        client.cookies.clear()
        engineer_headers = {
            "Authorization": f"Bearer {engineer_login.json()['access_token']}"
        }
        customer_headers = {
            "Authorization": f"Bearer {customer_login.json()['access_token']}"
        }

        first = client.post(
            "/api/v1/conversations/current",
            headers=engineer_headers,
            json={},
        )
        second = client.post(
            "/api/v1/conversations/current",
            headers=engineer_headers,
            json={},
        )
        assert first.status_code == second.status_code == 200
        conversation_id = first.json()["id"]
        assert second.json()["id"] == conversation_id

        reply = client.post(
            "/api/v1/chat/query",
            headers=engineer_headers,
            json={
                "query": "What products are available?",
                "conversation_id": conversation_id,
            },
        )
        assert reply.status_code == 200
        assert reply.json()["conversation_id"] == conversation_id

        cross_account_chat = client.post(
            "/api/v1/chat/query",
            headers=customer_headers,
            json={
                "query": "Continue this conversation",
                "conversation_id": conversation_id,
            },
        )
        assert cross_account_chat.status_code == 404

        history = client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=engineer_headers,
        )
        assert history.status_code == 200
        recent_history = history.json()[-2:]
        assert [message["role"] for message in recent_history] == [
            "user",
            "assistant",
        ]
        assert recent_history[0]["content"] == "What products are available?"
        assert (
            recent_history[1]["metadata"]["tool_executed"]
            == reply.json()["tool_executed"]
        )

        private_history = client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=customer_headers,
        )
        assert private_history.status_code == 404


def test_chat_uploads_and_analyzes_owned_document(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_HOSTED_MEDIA", "true")
    observed: dict[str, object] = {}

    def fake_answer(query, role, products, *, attachments):
        observed["query"] = query
        observed["attachment_names"] = [attachment.filename for attachment in attachments]
        observed["attachment_text"] = attachments[0].text
        return "The uploaded datasheet describes a transformer."

    monkeypatch.setattr("app.services.chat.generate_grounded_answer", fake_answer)
    with TestClient(app) as client:
        engineer_login = client.post(
            "/auth/login",
            json={"username": "engineer@jenga.com", "password": "engineer123"},
        )
        customer_login = client.post(
            "/auth/login",
            json={"username": "customer@jenga.com", "password": "customer123"},
        )
        engineer_token = engineer_login.json()["access_token"]
        customer_token = customer_login.json()["access_token"]
        client.cookies.clear()

        upload = client.post(
            "/api/v1/media?kind=document",
            headers={"Authorization": f"Bearer {engineer_token}"},
            files={
                "file": (
                    "transformer.txt",
                    b"JCT-500 is a 500 kVA dry-type transformer.",
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 200
        media_id = upload.json()["id"]
        assert upload.json()["filename"] == "transformer.txt"

        conversation = client.post(
            "/api/v1/conversations/current",
            headers={"Authorization": f"Bearer {engineer_token}"},
            json={},
        ).json()
        missing_consent = client.post(
            "/api/v1/chat/query",
            headers={"Authorization": f"Bearer {engineer_token}"},
            json={
                "query": "Summarize this datasheet",
                "conversation_id": conversation["id"],
                "media_ids": [media_id],
            },
        )
        assert missing_consent.status_code == 428
        assert not observed

        response = client.post(
            "/api/v1/chat/query",
            headers={"Authorization": f"Bearer {engineer_token}"},
            json={
                "query": "Summarize this datasheet",
                "conversation_id": conversation["id"],
                "media_ids": [media_id],
                "allow_external_processing": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "The uploaded datasheet describes a transformer."
        assert observed == {
            "query": "Summarize this datasheet",
            "attachment_names": ["transformer.txt"],
            "attachment_text": "JCT-500 is a 500 kVA dry-type transformer.",
        }

        private_upload = client.post(
            "/api/v1/chat/query",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"media_ids": [media_id]},
        )
        assert private_upload.status_code == 404

        remaining_content = client.post(
            "/api/v1/chat/query",
            headers={"Authorization": f"Bearer {engineer_token}"},
            json={
                "conversation_id": conversation["id"],
                "media_ids": [media_id],
                "allow_external_processing": True,
            },
        )
        assert remaining_content.status_code == 404


def test_media_upload_rejects_mismatched_image_content() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "engineer@jenga.com", "password": "engineer123"},
        )
        response = client.post(
            "/api/v1/media?kind=image",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            files={"file": ("not-image.png", b"not a PNG", "image/png")},
        )

    assert response.status_code == 415


def test_chat_analyzes_image_and_transcribed_voice_note(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_HOSTED_MEDIA", "true")
    from io import BytesIO
    import base64
    from PIL import Image

    image_buffer = BytesIO()
    with Image.new("RGB", (16, 16), "white") as source:
        source.save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    observed: dict[str, object] = {}

    def fake_transcription(filename, content_type, content):
        assert filename == "voice.webm"
        assert content_type == "audio/webm"
        assert content.startswith(b"\x1aE\xdf\xa3")
        return "Read the model number on this equipment."

    def fake_answer(query, role, products, *, attachments):
        observed["query"] = query
        observed["image"] = attachments[0].image_data_url
        observed["voice_text"] = attachments[1].text
        return "The image and voice note were analyzed."

    monkeypatch.setattr("app.services.media.transcribe_audio", fake_transcription)
    monkeypatch.setattr("app.services.chat.generate_grounded_answer", fake_answer)
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"username": "engineer@jenga.com", "password": "engineer123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        client.cookies.clear()

        image = client.post(
            "/api/v1/media?kind=image",
            headers=headers,
            files={"file": ("equipment.png", image_bytes, "image/png")},
        )
        voice = client.post(
            "/api/v1/media?kind=audio",
            headers=headers,
            files={"file": ("voice.webm", b"\x1aE\xdf\xa3voice", "audio/webm")},
        )
        assert image.status_code == voice.status_code == 200
        conversation = client.post(
            "/api/v1/conversations/current",
            headers=headers,
            json={},
        ).json()

        response = client.post(
            "/api/v1/chat/query",
            headers=headers,
            json={
                "conversation_id": conversation["id"],
                "media_ids": [image.json()["id"], voice.json()["id"]],
                "allow_external_processing": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "The image and voice note were analyzed."
    assert observed == {
        "query": "Please analyze the attached file(s).",
        "image": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        "voice_text": "Read the model number on this equipment.",
    }


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

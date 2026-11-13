"""Tests for the optional OpenAI Responses API integration."""

import httpx
import pytest
from fastapi import HTTPException

from app.db.database import ProductDB
from app.services.ai import generate_grounded_answer, transcribe_audio
from app.services.media import ChatAttachment


def _product() -> ProductDB:
    return ProductDB(
        category="generator",
        name="Jenga Genset 1000",
        model_number="JCG-1000",
        specifications="1000 kVA diesel generator",
        price_ksh=12500000,
    )


def test_openai_response_returns_assistant_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    request_data: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "output": [
                    {"type": "reasoning"},
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "The catalog lists a 1000 kVA generator."}],
                    },
                ]
            }

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        request_data["url"] = url
        request_data.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.ai.httpx.post", fake_post)
    answer = generate_grounded_answer("Tell me about the generator", "customer", [_product()])

    assert answer == "The catalog lists a 1000 kVA generator."
    assert request_data["url"] == "https://api.openai.com/v1/responses"
    assert request_data["headers"] == {"Authorization": "Bearer test-key"}
    assert request_data["json"]["store"] is False
    assert "JCG-1000" in request_data["json"]["input"]


def test_ai_returns_none_when_key_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert generate_grounded_answer("Tell me about the generator", "customer", [_product()]) is None


def test_openai_connection_error_is_reported_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def raise_connection_error(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.services.ai.httpx.post", raise_connection_error)
    with pytest.raises(HTTPException) as error:
        generate_grounded_answer("Tell me about the generator", "customer", [_product()])

    assert error.value.status_code == 503


def test_openai_response_includes_image_and_document_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_HOSTED_MEDIA", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    request_data: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "The image shows equipment."}],
                    }
                ]
            }

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        request_data["url"] = url
        request_data.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.ai.httpx.post", fake_post)
    attachments = [
        ChatAttachment(
            filename="site.png",
            content_type="image/png",
            image_data_url="data:image/png;base64,dGVzdA==",
        ),
        ChatAttachment(
            filename="manual.pdf",
            content_type="application/pdf",
            file_data_url="data:application/pdf;base64,dGVzdA==",
        ),
    ]

    answer = generate_grounded_answer(
        "Describe these attachments",
        "engineer",
        [_product()],
        attachments=attachments,
    )

    assert answer == "The image shows equipment."
    assert request_data["url"] == "https://api.openai.com/v1/responses"
    content = request_data["json"]["input"][0]["content"]
    assert content[1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,dGVzdA==",
    }
    assert content[2] == {
        "type": "input_file",
        "filename": "manual.pdf",
        "file_data": "data:application/pdf;base64,dGVzdA==",
    }


def test_voice_note_is_transcribed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_HOSTED_MEDIA", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    request_data: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"text": "Please identify the transformer model."}

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        request_data["url"] = url
        request_data.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.ai.httpx.post", fake_post)

    transcript = transcribe_audio("voice.webm", "audio/webm", b"audio-bytes")

    assert transcript == "Please identify the transformer model."
    assert request_data["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert request_data["data"] == {"model": "gpt-4o-mini-transcribe"}

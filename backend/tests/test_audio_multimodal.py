"""Isolated real HTTP/storage boundaries; native ASR/OCR are explicitly mocked."""

from datetime import timedelta
import io
import wave

import pytest
from sqlalchemy import select

from ai.multimodal.asr import Transcript, AsrTimeoutError
import app.services.audio as audio
import app.services.identification as identification
from app.db.database import AuditLogDB, MediaDB, utc_now
from test_image_identification import image_client, sign_in, upload


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x00" * 3200)
    return output.getvalue()


def upload_audio(client, headers, content=None, mime="audio/wav"):
    return client.post("/api/v1/media?kind=audio", headers=headers,
                       files={"file": ("../../untrusted.wav", wav_bytes() if content is None else content, mime)})


@pytest.fixture
def media_app(image_client, monkeypatch, tmp_path):
    monkeypatch.setattr(audio, "MEDIA_STORAGE_DIR", tmp_path / "private_audio")
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)
    def unexpected(*args, **kwargs):
        pytest.fail("Native ASR must be explicitly mocked")
    monkeypatch.setattr(audio, "transcribe_audio", unexpected)
    return image_client


def mock_speech(monkeypatch, text="What does this alarm mean?"):
    monkeypatch.setenv("WHISPER_MODEL_PATH", "mock-model-path")
    monkeypatch.setattr(audio, "transcribe_audio", lambda *args, **kwargs: Transcript(text, "en", 0.1, "transcribed" if text else "no_speech"))


def test_audio_is_canonical_private_and_deleted(media_app):
    client, sessions, _ = media_app
    headers = sign_in(client)
    result = upload_audio(client, headers)
    assert result.status_code == 200
    media_id = result.json()["id"]
    with sessions() as db:
        assert db.get(MediaDB, media_id).filename == f"{media_id}.wav"
    response = client.get(f"/api/v1/media/{media_id}", headers=headers)
    assert response.content == wav_bytes()
    assert response.headers["cache-control"] == "private, no-store"
    assert audio.audio_path(media_id).is_file()
    assert client.delete(f"/api/v1/media/{media_id}", headers=headers).status_code == 204
    assert not audio.audio_path(media_id).exists()
    assert client.get(f"/api/v1/media/{media_id}", headers=headers).status_code == 404


@pytest.mark.parametrize("content,mime", [(b"bad", "audio/wav"), (b"", "audio/wav"), (b"browser codec", "audio/webm")])
def test_invalid_audio_not_persisted(media_app, content, mime):
    client, sessions, _ = media_app
    assert upload_audio(client, sign_in(client), content, mime).status_code == 415
    with sessions() as db:
        assert not list(db.scalars(select(MediaDB)))


def test_audio_ownership_expiry_and_auth_before_transcription(media_app):
    client, sessions, _ = media_app
    owner = sign_in(client)
    media_id = upload_audio(client, owner).json()["id"]
    other = sign_in(client, "engineer")
    for method, suffix in (("get", ""), ("delete", ""), ("post", "/transcribe")):
        assert getattr(client, method)(f"/api/v1/media/{media_id}{suffix}", headers=other).status_code == 404
    assert client.post(f"/api/v1/media/{media_id}/transcribe").status_code == 401
    with sessions() as db:
        db.get(MediaDB, media_id).created_at = utc_now() - timedelta(hours=2)
        db.commit()
    assert client.post(f"/api/v1/media/{media_id}/transcribe", headers=owner).status_code == 410


def test_missing_runtime_is_explicit_and_audited(media_app):
    client, sessions, _ = media_app
    headers = sign_in(client)
    media_id = upload_audio(client, headers).json()["id"]
    assert client.post(f"/api/v1/media/{media_id}/transcribe", headers=headers).status_code == 503
    with sessions() as db:
        assert db.scalar(select(AuditLogDB).where(AuditLogDB.tool_used == "transcribe_audio")).status == "failed"


def test_transcript_and_timeout_contract(media_app, monkeypatch):
    client, _, _ = media_app
    headers = sign_in(client)
    media_id = upload_audio(client, headers).json()["id"]
    mock_speech(monkeypatch)
    response = client.post(f"/api/v1/media/{media_id}/transcribe", headers=headers)
    assert response.status_code == 200
    assert response.json()["text"] == "What does this alarm mean?"
    def timeout(*args, **kwargs):
        raise AsrTimeoutError()
    monkeypatch.setattr(audio, "transcribe_audio", timeout)
    assert client.post(f"/api/v1/media/{media_id}/transcribe", headers=headers).status_code == 504


def test_voice_photo_request_preserves_inputs_and_has_no_fabricated_manual_answer(media_app, monkeypatch):
    client, _, _ = media_app
    headers = sign_in(client, "engineer")
    voice = upload_audio(client, headers).json()["id"]
    photo = upload(client, headers).json()["id"]
    mock_speech(monkeypatch)
    monkeypatch.setattr(identification, "read_nameplate", lambda _: "JCG-1000")
    response = client.post("/api/v1/chat/query", headers=headers, json={"media_ids": [voice, photo]})
    assert response.status_code == 200
    result = response.json()
    assert result["structured_results"]["model_number"] == "JCG-1000"
    assert result["structured_results"]["transcription"]["text"] == "What does this alarm mean?"
    assert result["structured_results"]["input_status"] == "evidence_unavailable"
    assert result["citations"] == []
    assert "check the manual and follow local regulations" in result["answer"]
    assert result["conversation_id"]


def test_all_media_preflight_before_either_engine(media_app, monkeypatch):
    client, _, _ = media_app
    owner = sign_in(client)
    voice = upload_audio(client, owner).json()["id"]
    other = sign_in(client, "engineer")
    photo = upload(client, other).json()["id"]
    response = client.post("/api/v1/chat/query", headers=owner, json={"media_ids": [voice, photo]})
    assert response.status_code == 404


@pytest.mark.parametrize("ocr,spoken,reason", [
    ("JCG-1000", "Explain JCS-50", "model_disagreement"),
    ("JCG-1000 JCS-50", "What is this?", "ambiguous_image"),
    ("UNKNOWN-1", "What is this?", "unidentified_image"),
    ("JCG-1000", "", "missing_question"),
])
def test_fusion_clarifies_instead_of_guessing(media_app, monkeypatch, ocr, spoken, reason):
    client, _, _ = media_app
    headers = sign_in(client)
    voice = upload_audio(client, headers).json()["id"]
    photo = upload(client, headers).json()["id"]
    mock_speech(monkeypatch, spoken)
    monkeypatch.setattr(identification, "read_nameplate", lambda _: ocr)
    result = client.post("/api/v1/chat/query", headers=headers, json={"media_ids": [voice, photo]})
    assert result.status_code == 200
    assert result.json()["structured_results"]["reason"] == reason
    assert result.json()["structured_results"]["input_status"] == "clarification_required"


def test_customer_cannot_match_private_model_through_fusion(media_app, monkeypatch):
    client, _, _ = media_app
    headers = sign_in(client)
    photo = upload(client, headers).json()["id"]
    monkeypatch.setattr(identification, "read_nameplate", lambda _: "PRIVATE-999")
    result = client.post("/api/v1/chat/query", headers=headers, json={"query": "What is this?", "media_ids": [photo]})
    assert result.status_code == 200
    assert "PRIVATE-999" not in result.text
    assert result.json()["structured_results"]["identification"]["candidates"] == []


def test_duplicate_media_rejected_before_native_work(media_app):
    client, _, _ = media_app
    headers = sign_in(client)
    voice = upload_audio(client, headers).json()["id"]
    result = client.post("/api/v1/chat/query", headers=headers, json={"media_ids": [voice, voice]})
    assert result.status_code == 422

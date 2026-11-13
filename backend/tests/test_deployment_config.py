"""Deployment configuration checks for Vercel, PrimeCloud, and Docker."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import BACKEND_ENV_FILE, _cors_origins, app, load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backend_env_file_is_loaded_without_overriding_platform_settings(
    monkeypatch, tmp_path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TEST_BACKEND_ENV_FILE_VALUE=from-file\n"
        "TEST_PLATFORM_ENV_VALUE=from-file\n"
    )
    monkeypatch.delenv("TEST_BACKEND_ENV_FILE_VALUE", raising=False)
    monkeypatch.setenv("TEST_PLATFORM_ENV_VALUE", "from-platform")

    assert load_dotenv(env_file, override=False)
    assert os.getenv("TEST_BACKEND_ENV_FILE_VALUE") == "from-file"
    assert os.getenv("TEST_PLATFORM_ENV_VALUE") == "from-platform"
    assert BACKEND_ENV_FILE == PROJECT_ROOT / "backend" / ".env"


def test_env_templates_are_available_but_real_env_files_are_ignored() -> None:
    gitignore = (PROJECT_ROOT / ".gitignore").read_text()

    assert (PROJECT_ROOT / ".env.example").is_file()
    assert (PROJECT_ROOT / "backend" / ".env.example").is_file()
    assert (PROJECT_ROOT / "backend" / ".env.production.example").is_file()
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore
    assert "!.env.*.example" in gitignore


def test_production_cors_requires_explicit_frontend_origins(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="CORS_ORIGINS must list"):
        _cors_origins()

    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="cannot use"):
        _cors_origins()


def test_cors_origins_are_normalized_and_local_defaults_are_available(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " https://copilot.vercel.app/ , https://copilot.example.com ",
    )
    assert _cors_origins() == [
        "https://copilot.vercel.app",
        "https://copilot.example.com",
    ]

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert _cors_origins() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_vercel_build_and_spa_fallback_are_configured() -> None:
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text())

    assert config["framework"] == "vite"
    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "dist"
    assert config["rewrites"] == [
        {
            "source": "/api/v1/:path*",
            "destination": "https://kpp.primecloud.cloud/api/v1/:path*",
        },
        {"source": "/(.*)", "destination": "/index.html"}
    ]


def test_backend_procfile_uses_platform_assigned_port() -> None:
    procfile = (PROJECT_ROOT / "Procfile").read_text()

    assert (
        "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
        in procfile
    )


def test_cors_preflight_allows_attachment_removal() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/media/example",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_split_hosting_is_the_only_deployment_target() -> None:
    docker_paths = (
        PROJECT_ROOT / "Dockerfile",
        PROJECT_ROOT / "backend" / "Dockerfile",
        PROJECT_ROOT / "docker-compose.yml",
        PROJECT_ROOT / ".dockerignore",
        PROJECT_ROOT / "deploy" / "nginx.conf",
        PROJECT_ROOT / "deploy" / "start.sh",
    )
    deployment = (PROJECT_ROOT / "DEPLOYMENT.md").read_text()

    assert all(not path.exists() for path in docker_paths)
    assert "Runtime: Python" in deployment
    assert "disable or delete" in deployment
    assert "previous Docker" in deployment

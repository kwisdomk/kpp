# Jenga Consultants Product Copilot

A prototype assistant for the engineers and customers of Jenga Consultants, a
fictional industrial-equipment seller. Company accounts and catalogue prices are
demo data. Equipment specifications need traceable source documents.

The repository contains a React frontend, a FastAPI backend, and AI source
validation tools. Text chat and catalogue tools are implemented. A backend
nameplate-OCR baseline has authenticated image handling and filtered catalogue
matching; its [contract and verification limits](docs/ocr_identification_contract.md)
are documented. Photo/audio submission, private canonical WAV storage and input
fusion are wired; [speech setup and integration limits](docs/asr_handoff.md)
are documented. Native speech inference, browser recording, approved source
retrieval and the complete cited multimodal answer flow remain unverified or unfinished.

The assistant provides decision support. It does not replace a manufacturer
manual or a qualified engineer.

## Run locally

The frontend is in `src/` at the repository root. The backend is in `backend/`.
Use Python 3.11 or newer and a Node.js version supported by the installed Vite
release.

From the repository root, create the Python environment and start the backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, install the frontend dependencies and set the API address:

```powershell
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
npm run dev
```

Open the URL printed by Vite. The API address above matches the backend command;
the frontend's current fallback address uses port 8080.

Health endpoints:

- `GET http://localhost:8000/api/v1/health` checks that the API is running.
- `GET http://localhost:8000/api/v1/ready` checks database connectivity.

The backend seeds demo accounts and products. Use them only for development and
demonstrations. Deployment requires a separate `JENGA_SECRET_KEY`; demo passwords
are not suitable for a public production service.

## Checks

AI source-validation tests use the Python standard library:

```powershell
python -B -m unittest discover -s ai/tests -v
```

Frontend checks:

```powershell
npm run lint
npm run build
```

These checks do not establish model quality or complete application readiness.

## Data and model status

The AI catalogue has 15 candidates across three categories. All remain
unapproved; the source manifest has 19 pending rows and zero approved assets.
Document URLs and hashes are recorded for 13 candidate slots. Rights and
technical review remain pending. See [DATA.md](DATA.md).

The backend supports an explicitly configured local model through `LLM_BASE_URL`
and `LLM_MODEL`; the existing hosted provider remains optional. Local mode never
falls back to the hosted provider. Setup and verification limits are in the
[local chat handoff](docs/LOCAL_CHAT_HANDOFF.md). Authorized document retrieval
and model revision, checksum and licence records remain incomplete. See the
[AI handoff](docs/AI_HANDOFF.md).

The [security note](docs/SECURITY.md) records session enforcement and conversation
checks, fresh-login requirements, regression evidence and remaining work.

## Deployment

[DEPLOYMENT.md](DEPLOYMENT.md) describes the combined Docker deployment for
PrimeCloud and local containers. Its hosted-model configuration describes the
current implementation, not approval to send private or restricted data.

### Deploying the full application to PrimeCloud

Deploy this repository as a **Docker application**, not as a Python-runtime
application. The root [`Dockerfile`](./Dockerfile) builds the frontend and
backend together and includes the Nginx configuration and startup script.
Selecting Python-runtime deployment runs the [`Procfile`](./Procfile) directly
and bypasses the repository's Nginx configuration, so the bundled Nginx
permission fix will not apply.

Use the repository root as the build context and `Dockerfile` as the Dockerfile.
Configure PrimeCloud to expose port `8080`, mount persistent storage at
`/app/data`, and use `/ready` as the health-check path. See
[`DEPLOYMENT.md`](./DEPLOYMENT.md) for the full setup and required production
environment variables.

## Team

Thanks to everyone contributing to this project:

- [@De-pilot7127](https://github.com/De-pilot7127) — frontend
- [@Hawamuriuki](https://github.com/Hawamuriuki) — frontend
- [@JavaTheHutt-K](https://github.com/JavaTheHutt-K) — backend
- [@kwisdomk](https://github.com/kwisdomk) — AI/ML

## Contributing

Read [AGENTS.md](AGENTS.md) before contributing. The
[implementation plan](project-plan.md) records requirements and
task IDs; section 19 records progress. Proposed paths and features in the plan
may differ from the current source tree.

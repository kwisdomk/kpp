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
Copy-Item backend/.env.example backend/.env
Copy-Item .env.example .env
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, install the frontend dependencies and set the API address:

```powershell
npm ci
npm run dev
```

Open the URL printed by Vite. The API address above matches the backend command;
the frontend's current fallback address uses port 8080.

## Backend

The FastAPI backend is in [`backend/`](./backend). It supports the modular `/api/v1`
routes described in the project plan, including authentication, sessions, catalogue
tools, conversations, media validation, chat, and human-review requests.
The account chat accepts up to two images, PDFs, DOCX, TXT, Markdown, CSV, or voice
notes per message (8 MiB each). Image/PDF analysis and voice transcription use the
configured OpenAI API; document text is extracted for NLP analysis. Configure
`OPENAI_API_KEY` to enable those attachment and voice features. Users must confirm
they are authorized to send attachments to the configured AI service; do not send
private or restricted information unless its use with that service is approved.
Uploaded bytes are deleted after successful processing or removal, and pending
uploads expire after 24 hours (64 MiB/20 files maximum per account).

Health endpoints:

- `GET http://localhost:8000/api/v1/health` checks that the API is running.
- `GET http://localhost:8000/api/v1/ready` checks database connectivity.

The backend seeds demo accounts and products. Use them only for development and
demonstrations. Deployment requires a separate `JENGA_SECRET_KEY`; demo passwords
are not suitable for a public production service.

The ignored `.env` files are local-only and must never be committed. Use
`backend/.env.production.example` as a checklist for PrimeCloud production
settings. Vercel and PrimeCloud do not receive ignored local files from Git;
configure production values in each provider's environment/secrets settings.

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

The reconciliation retains upstream account chat history and split hosting.
Photo and voice use the local path by default. Optional hosted attachment
analysis requires operator approval (`ENABLE_HOSTED_MEDIA=true`), no selected
local model endpoint and per-request consent; see
[deployment configuration](DEPLOYMENT.md#local-inference-and-media-selection).

## Deployment

[DEPLOYMENT.md](DEPLOYMENT.md) describes the Vercel frontend and PrimeCloud
Python backend deployment. Its hosted-model configuration describes the
current implementation, not approval to send private or restricted data.

### Deploying frontend to Vercel and backend to PrimeCloud

Deploy the Vite frontend to Vercel and the FastAPI backend to PrimeCloud as a
Python web application. Configure `VITE_API_BASE_URL` in Vercel and the exact
Vercel origin in PrimeCloud's `CORS_ORIGINS`. See
[`DEPLOYMENT.md`](./DEPLOYMENT.md) for runtime settings, database requirements,
health checks, and deploy order. The repository is configured for this
split deployment; no Docker/Nginx service configuration is included.

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

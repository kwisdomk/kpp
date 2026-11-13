# Jenga Consultants Product Copilot

A product assistant for the customers and engineers of **Jenga Consultants**, a fictional industrial-equipment seller. It brings product questions, catalogue prices and comparisons into one conversation interface, with access controlled by the backend.

Built for the **Zetech Alumni × Student Hackathon**, 12–13 November 2026, under **Challenge 3: Product Copilot**, Machine Learning & Data Science.

[Hosted prototype](https://jenga-ai-ebon.vercel.app/) · [Installation](#installation) · [How to use it](#how-to-use-it)

**Status:** a prototype with unfinished technical-source retrieval and multimodal evaluation. Company records and the seeded catalogue are synthetic demo data. The assistant supports decisions; it does not replace manufacturer documentation or a qualified engineer.

## Purpose and users

Product information is scattered across catalogues and manuals, while customers and engineers need different levels of access. This project explores a shared assistant for both roles:

| User | Purpose |
| --- | --- |
| Customer | Explore equipment, check catalogue prices and compare available products. |
| Engineer | Ask technical questions and use equipment-identification and service-support workflows as they become supported by reviewed sources. |

The intended contribution to **SDG 9: Industry, Innovation and Infrastructure** is easier access to equipment information. Real-world impact has not been measured.

## Features and technology

- **React, TypeScript and Vite:** workspace, sign-in, chat, catalogue browsing and account-bound conversations.
- **FastAPI and Python:** authentication, session expiry, catalogue access, tools and human-review requests.
- **SQLAlchemy:** SQLite for local development, with MySQL support for hosting.
- **Catalogue tools:** code-based prices and structured comparisons.
- **Local inference:** a configurable LM Studio or compatible model connection, plus Tesseract OCR and whisper.cpp speech adapters.
- **Data tooling:** source manifests, validation tools and automated tests.

The backend determines the trusted role and filters catalogue access before retrieval. Local model errors do not trigger an automatic hosted fallback. An optional hosted attachment-processing profile is documented separately below.

## Prerequisites

- Git.
- **Python 3.11**, matching `.python-version`, and pip.
- **Node.js 22.12 or newer** and npm, compatible with the installed Vite version.
- For generated local answers: LM Studio or a compatible model server, and a downloaded model that fits the machine's available memory.
- For local image identification: Tesseract with English language data.
- For local speech: whisper.cpp and a compatible speech-model file.

The catalogue and deterministic tools can run without a language model. Python dependency installation does not install native tools or model weights. Check available RAM and VRAM before loading a model.

## Installation

The commands below use **PowerShell on Windows**. Run them from the repository root unless stated otherwise.

```powershell
git clone https://github.com/kwisdomk/kpp.git
Set-Location kpp

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For an existing checkout, enter that folder instead of cloning again. If the `py` launcher is unavailable, use `python -m venv .venv` after confirming the Python version.

Create the environment files only if they do not already exist:

```powershell
if (!(Test-Path backend/.env)) {
    Copy-Item backend/.env.example backend/.env
}
if (!(Test-Path .env)) {
    Copy-Item .env.example .env
}
```

| File | Purpose |
| --- | --- |
| `backend/.env` | Database, session secret, model connection and media settings. The backend loads this file at startup. |
| Root `.env` | Frontend configuration. Vite exposes `VITE_*` values to the browser, so they must never contain secrets. |

Replace the `JENGA_SECRET_KEY` placeholder in `backend/.env` with a long random value. Keep the default SQLite connection for a local demo. Both environment files are ignored by Git.

### Connect a local model

Start LM Studio's server and load your chosen model. In **`backend/.env`**, set:

```dotenv
LLM_BASE_URL=http://127.0.0.1:1234/v1
LLM_MODEL=replace-with-the-exact-served-model-id
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=180
LLM_MAX_TOKENS=1024
ENABLE_HOSTED_MEDIA=false
```

Use the exact model identifier served by the model server. If it requires authentication, set `LLM_API_KEY` to its key; otherwise leave that value empty. Include `/v1` in the URL. Restart the backend after changing model settings.

The root `.env` should contain:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

With no local endpoint or hosted key configured, chat uses a limited catalogue fallback rather than generated answers. See [local chat setup](docs/LOCAL_CHAT_HANDOFF.md) for details.

## Start the app

**Terminal 1 — backend**, with the Python environment activated:

```powershell
$env:PYTHONPATH = ".;backend"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Startup creates database tables and seeds development accounts and the synthetic catalogue.

**Terminal 2 — frontend**, from the repository root:

```powershell
npm ci
npm run dev -- --host localhost --port 5173
```

Open **http://localhost:5173**. Keep the frontend, backend and local model server running while using generated chat.

## How to use it

1. **Sign in.** The seed defines `customer@jenga.com` and `engineer@jenga.com`. Use the development credentials defined in the [account seed](backend/app/db/database.py); existing databases may have different credentials. These accounts are for demonstrations only.
2. **Browse Products.** Check which products your account can access. Displayed prices and specifications belong to the synthetic catalogue.
3. **Open Chat Assistant.** Try `What are the catalogue prices?` for deterministic pricing or `Compare JCG-1000 and JCT-500` for a structured comparison. General questions use the configured model when available.
4. **Inspect the response.** Check its warnings, tool label and available citations. Catalogue-row citations are not manufacturer-manual citations. Confidence labels are not measured accuracy.
5. **Try media after setup.** Attach a clear nameplate photo or a short voice question. The interface allows up to two attachments, each up to 8 MiB. Local fusion accepts at most one image and one audio recording.
6. **Sign out** when finished. The backend revokes the submitted session.

For consequential engineering questions, verify the source, **check the manual and follow local regulations**, and involve a qualified engineer. Review-request submission exists; a complete reviewer-resolution workflow still needs verification.

### Image, voice and document processing

Local processing is the default. Configure `TESSERACT_CMD`, `WHISPER_CPP_CMD` and `WHISPER_MODEL_PATH` in `backend/.env` after installing the tools. Browser audio is converted to PCM16 mono 16 kHz WAV for the local path. If setting `MEDIA_STORAGE_DIR`, use a private directory outside public/static folders.

PDF, DOCX, text, Markdown and CSV attachments require the optional hosted profile: `OPENAI_API_KEY`, `ENABLE_HOSTED_MEDIA=true`, no selected `LLM_BASE_URL`, and consent for each request. The backend also checks whether the context is permitted for hosted processing. Do not send private or restricted material without approval.

See [media policy and retention](DEPLOYMENT.md#local-inference-and-media-selection), [OCR setup](docs/ocr_identification_contract.md) and [speech setup](docs/asr_handoff.md) for requirements and current limits.

## Checks and troubleshooting

Check the API and database from another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ready
```

Expected statuses are `ok` and `ready`. Interactive API documentation is at **http://127.0.0.1:8000/docs**. Send a chat message separately to verify the model connection.

| Symptom | Check |
| --- | --- |
| Sign-in or catalogue cannot reach the backend | Backend terminal, port 8000 and frontend `VITE_API_BASE_URL`. |
| `Local AI service request failed` | Model server logs, exact model ID and `LLM_API_KEY`. |
| AI timeout or incomplete answer | Model readiness, available memory and time/token limits. |
| OCR or speech unavailable | Native executable paths, English language data and speech-model file. |
| Documents unavailable | Approved document retrieval is unfinished; the upload controls also depend on the selected processing profile. |

AI component checks, with the Python environment activated:

```powershell
python -B -m unittest discover -s ai/tests -v
```

Run backend tests with `PYTHONPATH` set as in the startup instructions. This command selects a separate test database and disables real provider/model settings before loading the app:

```powershell
python -B -c "import os, pytest; os.environ.update(DATABASE_URL='sqlite:///./test_jenga.db', LLM_BASE_URL='', OPENAI_API_KEY='', ENABLE_HOSTED_MEDIA='false'); raise SystemExit(pytest.main(['backend/tests', '-q']))"
```

Tests use mocked model/native boundaries and do not measure real OCR, speech or answer quality. Recorded results and verification limits are in the [reconciliation handoff](docs/reconciliation_handoff.md).

Frontend checks:

```powershell
node --test tests/frontend_error_states.test.mjs
npm run lint
npm run build
```

## Current limitations

- The source catalogue has **15 candidates across three categories**, with **19 pending manifest entries and zero approved source assets**. Rights and technical review are pending. See [DATA.md](DATA.md).
- Approved manual retrieval, page-grounded answers and the complete cited image/voice workflow are unfinished or unverified.
- Measured multimodal accuracy, the required benchmark and adversarial evaluation, model provenance and the one-command knowledge-base build/evaluation remain incomplete.
- Successful tests or model calls do not establish production readiness. Synthetic catalogue data is not a binding quotation or verified manufacturer evidence.

The [execution ledger](project-plan.md) and [security note](docs/SECURITY.md) record detailed progress and remaining work.

## Licenses and evaluation

No repository-wide code license file is present. Individual source materials
have their own terms: the BMS C1 sample retains its CC BY-SA 4.0 notice, while
rights for the commercial candidate documents remain pending. Public access to
a document does not establish permission to process, quote or redistribute it.
See [DATA.md](DATA.md) for source-level records.

The reconciliation handoff records local backend and AI regression tests with
mocked model/native boundaries. The 60-question benchmark, held-out image
accuracy, speech WER and adversarial before/after evaluation have not been
established. See [verification and limits](docs/reconciliation_handoff.md#verification).

## Repository guide

| Path | Contents |
| --- | --- |
| `src/`, `public/` | Frontend and public assets |
| `backend/` | API, authentication, database, tools and backend tests |
| `ai/` | Source validation, taxonomy and multimodal components with tests |
| `data/` | Candidate catalogue and source manifests |
| `docs/`, `reports/` | Contracts, setup details, security notes and recorded evidence |
| `project-plan.md` | Technical plan and execution ledger |

## Deployment

The hosted architecture uses **Vercel for the frontend** and **PrimeCloud for FastAPI**. Production frontend requests use the `/api/v1` rewrite in `vercel.json`. Configure environment variables in each provider; ignored local files are not uploaded through Git.

A remote backend cannot reach a model on your laptop through its own `127.0.0.1`. Follow [DEPLOYMENT.md](DEPLOYMENT.md) for database, origin, secret and connectivity requirements.

## Team and acknowledgements

Thanks to everyone contributing to this project:

- [@De-pilot7127](https://github.com/De-pilot7127) — frontend
- [@Hawamuriuki](https://github.com/Hawamuriuki) — frontend
- [@JavaTheHutt-K](https://github.com/JavaTheHutt-K) — backend
- [@kwisdomk](https://github.com/kwisdomk) — AI/ML

AI coding assistants, including ChatGPT/Codex and GitHub Copilot, supported development and documentation. Runtime generation uses the configured local model or optional hosted provider. Model/source records and outstanding provenance checks are documented in [DATA.md](DATA.md) and the [AI handoff](docs/AI_HANDOFF.md).

## Contributing

Read [AGENTS.md](AGENTS.md) and the [project plan](project-plan.md) before making changes. Coordinate shared interfaces and tie claims to source evidence, code and recorded results.

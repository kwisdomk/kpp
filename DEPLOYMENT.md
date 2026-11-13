# Deployment

The supported production setup is a Vercel-hosted Vite frontend and a
PrimeCloud-hosted FastAPI backend. This repository intentionally has no
Docker/Nginx deployment configuration, so PrimeCloud should not detect or start
the old combined web container.

## Vercel frontend

Create a Vercel project connected to this GitHub repository and configure:

- Root directory: repository root
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

`vercel.json` sends `/api/v1/*` requests to
`https://kpp.primecloud.cloud/api/v1/*` before applying the SPA fallback. The
browser therefore calls a same-origin API path and does not need
`VITE_API_BASE_URL`. Update the rewrite destination if the backend domain
changes. Never put database or AI-provider secrets in `VITE_*` variables
because they are embedded in browser assets.

## PrimeCloud backend

Create a **Python web application** from this repository and configure:

- Runtime: Python, using `.python-version` (`3.11.9`)
- Root/build directory: repository root
- Install requirements from the repository root:
  `python -m pip install -r requirements.txt`
- Start command: use the root `Procfile`:
  `web: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`
- Health/readiness path: `/ready`

PrimeCloud must provide `PORT`; Uvicorn binds to `0.0.0.0` and uses that
assigned port. `/health` checks process liveness, while `/ready` also checks
database connectivity and should be used for the platform health check.

Configure these PrimeCloud variables/secrets. A placeholder template is
available at `backend/.env.production.example`; local `.env` files are not
uploaded from Git. Set production values in PrimeCloud's environment/secrets
configuration:

```text
APP_ENV=production
DATABASE_URL=mysql+pymysql://<user>:<password>@<mysql-host>:3306/<database>
CORS_ORIGINS=https://<your-vercel-project>.vercel.app
JENGA_SECRET_KEY=<long-random-production-secret>
OPENAI_API_KEY=<optional-provider-secret>
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

Add your Vercel custom domain as another comma-separated exact origin in
`CORS_ORIGINS`. Do not use `*` in production. Add a Vercel Preview origin only
if that specific preview deployment needs to call the production backend.
The backend accepts the bearer authorization header and permits the API's
GET, POST, and DELETE methods across configured origins.

`DATABASE_URL` must use the private PrimeCloud MySQL hostname and database
credentials. URL-encode special characters in the username or password.
Alternatively, the backend supports the documented `MYSQL_HOST`, `MYSQL_PORT`,
`MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` variables. Keep database
credentials, `JENGA_SECRET_KEY`, and `OPENAI_API_KEY` only in PrimeCloud's
secret manager. `OPENAI_API_KEY` is optional for text fallback and required
for configured hosted AI and attachment/transcription features.

## Deploy order and existing PrimeCloud services

1. Deploy the backend and database on PrimeCloud. Verify
   `https://<backend-domain>/ready` returns `{"status":"ready"}`.
2. Verify `vercel.json` points `/api/v1/*` at the active backend domain.
3. Set the exact Vercel production origin in PrimeCloud's `CORS_ORIGINS`.
4. Deploy/redeploy the Vercel frontend and test login, catalogue loading, chat,
   and attachment removal.
5. Once the Python service is healthy, disable or delete the previous Docker
   service in the PrimeCloud dashboard so it cannot compete for the same
   domain, port, or health-check configuration.

This repository removes the Docker/Nginx files, but it cannot remove an
already-created PrimeCloud service instance. If PrimeCloud does not allow
changing the existing service to the Python runtime, create a Python service
from the latest `main` branch, verify it is healthy, then disable or delete the
old Docker service in PrimeCloud.

For local backend development, copy `backend/.env.example` to `backend/.env`.
The backend loads that file when present and does not override environment
variables provided by the shell or hosting platform. Real `.env` files are
excluded by `.gitignore`; commit only the `.env.example` templates.

## Troubleshooting 502 responses

Check the backend directly before changing frontend code:

- `/health` returns `{"status":"ok"}` when the API process is reachable.
- `/ready` returns `{"status":"ready"}` when the API and database are reachable.
- If either direct backend endpoint returns a Cloudflare 502, inspect the
  PrimeCloud service's deployment/runtime logs and domain routing. Confirm the
  service is running the Python `Procfile`, binds to the platform-provided
  `PORT` on `0.0.0.0`, and uses `/ready` as its health check. A repository change
  cannot repair an unavailable origin or incorrect PrimeCloud domain mapping.
- If the backend health endpoints work but the Vercel `/api/v1/health` URL
  returns the frontend HTML, redeploy Vercel from a branch containing the API
  rewrite in `vercel.json`.

# PrimeCloud Docker deployment

The production image contains both application surfaces in one container:

- Nginx serves the Vite frontend.
- FastAPI runs internally on `127.0.0.1:8000` through a non-privileged startup script.
- Nginx proxies `/api/*`, `/health`, and `/ready` to FastAPI.
- Nginx runs as the non-root `appuser`, sends its startup/error logs to stderr before loading the config, writes access logs to stdout, stores its PID directly in `/tmp`, and uses sticky, world-writable subdirectories for temporary files so runtime UID remapping does not block writes.
- The image includes the standard-library `ai/` ingestion validators and `data/` review assets; the build verifies the source manifest and BMS C1 snapshot before publishing the image.
- Only products already in the backend database are exposed to the UI and chat. Proposed catalogue entries with pending evidence or approval are not automatically imported or priced.
- The frontend product browser reads `/api/v1/catalogue/products`; it no longer displays a separate hard-coded product list. Chat requests use the backend `/api/v1/chat/query` contract.
- PrimeCloud MySQL is used through the `DATABASE_URL` environment variable.

This avoids privileged process management and removes the need for a separate backend service hostname while keeping the
frontend and backend on one PrimeCloud domain.

## Local container validation

The OCR/image boundary, shared catalogue grants and error contract are documented
in [docs/ocr_identification_contract.md](docs/ocr_identification_contract.md).
The Dockerfile now includes Tesseract plus English data; that Docker build has
not been exercised in this checkpoint. Sanitized images belong in the persistent
private `/app/data/uploads` directory, never the frontend/public directory.
Windows backend startup requires `TESSERACT_CMD` set to the verified executable
path in that note. Restart and log in again after the session-binding changes.

### Optional local text model

The backend can use LM Studio's OpenAI-compatible Chat Completions endpoint.
For a backend running directly on the model host, set:

```powershell
$env:LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LLM_MODEL = "qwen3.5-4b-claude-4.6-opus-reasoning-distilled"
```

Use the exact model identifier from the server. Set `LLM_API_KEY` only if that
server requires authentication. `LLM_TIMEOUT_SECONDS` defaults to 180 and
`LLM_MAX_TOKENS` to 1024; incomplete or reasoning-only answers return an error.
Configuring `LLM_BASE_URL` selects this endpoint exclusively, even when a hosted
key exists. A failed local request never falls back to the hosted provider.
Without `LLM_BASE_URL`, the existing optional OpenAI configuration is unchanged.

For Docker Desktop on Windows, the host address is normally
`http://host.docker.internal:1234/v1`; the server must accept connections from
the container. Container loopback refers to the container itself. A PrimeCloud
container cannot reach a laptop through `127.0.0.1`; hosted deployment requires
an explicitly reachable, appropriately protected model service. This patch does
not expose the local model server or configure a public tunnel.

Catalogue APIs, including legacy aliases, require authentication. Current product
rows are shared synthetic demo data. There is no per-product visibility schema
yet; do not add restricted documents or internal costs to these rows. Returned
`product:ID` citations identify supplied catalogue context, not approved manual
pages or independent claim verification. Cross-role API review is required.

From the repository root:

```powershell
docker compose up --build
```

Open `http://localhost:8081`. The backend health endpoint is available through
`http://localhost:8081/health`. Stop the stack with:

```powershell
docker compose down
```

The named `app-data` volume preserves the SQLite database across restarts. Use
`docker compose down -v` only when intentionally deleting local data.

## PrimeCloud deployment

Create one **Docker** application from the GitHub repository with:

- Build context: repository root
- Dockerfile: `Dockerfile`
- Container port: `8080`
- Persistent disk mount: `/app/data`

Do not configure this full-stack deployment as a Python-runtime application.
The root `Procfile` starts Uvicorn directly and does not start the bundled
Nginx or load `deploy/nginx.conf`; in that mode, changing this repository's
Nginx files cannot change the platform-managed Nginx logs or permissions. If
PrimeCloud currently has this service configured with a Python builder, switch
the application to Docker and rebuild from the repository root Dockerfile.

Set these PrimeCloud environment variables/secrets. Use the connection string
provided by the PrimeCloud MySQL service:

```text
DATABASE_URL=mysql+pymysql://<user>:<password>@<mysql-host>:3306/<database>
CORS_ORIGINS=*
JENGA_SECRET_KEY=<long-random-production-secret>
OPENAI_API_KEY=<OpenAI-secret-api-key>
OPENAI_MODEL=gpt-4.1-mini
PORT=8080
```

Alternatively, if PrimeCloud exposes separate MySQL variables, set
`MYSQL_HOST` (or `MYSQLHOST`), `MYSQL_PORT` (or `MYSQLPORT`; optional and
defaults to `3306`), `MYSQL_USER` (or `MYSQLUSER`), `MYSQL_PASSWORD` (or
`MYSQLPASSWORD`), and `MYSQL_DATABASE` (or `MYSQLDATABASE`). `DATABASE_URL`
takes precedence over `MYSQL_URL`, which takes precedence over separate
variables. If PrimeCloud provides `MYSQLPORT` as `3306/<database>`, the app
uses the numeric portion as the port and the suffix as the database name
unless `MYSQL_DATABASE`/`MYSQLDATABASE` is explicitly set.
The app does not load `DB_HOST`, `DB_PORT`, `DB_NAME`, or `DB_PASSWORD`; use
the `MYSQL_*` names above or provide `DATABASE_URL`. If a hostname in the
effective URL cannot resolve, verify the database service is running and
linked to this application on PrimeCloud's private network. The app does not
replace or guess database hostnames.
`MYSQL_HOST` must be a hostname or IP address only. If PrimeCloud gives a
combined host such as `host:3306/database`, that form is also accepted; do not
include credentials in the host variable.

The frontend is built with `VITE_API_BASE_URL=/api/v1`, so browser requests
remain on the same PrimeCloud domain. No backend URL or cross-application
hostname is required.

Do not commit production secrets. Set JWT/session secrets, database settings,
and provider credentials in PrimeCloud's secret manager.

The application also accepts a `mysql://...` URL and automatically uses the
PyMySQL SQLAlchemy driver. The local Docker Compose setup continues to use
SQLite for development unless `DATABASE_URL` is overridden.

The backend tests the MySQL connection before creating tables and retries
transient SQLAlchemy connection failures up to three times during startup.
If all attempts fail, startup still fails with safe diagnostics rather than
reporting the database as ready. The
`/ready` endpoint and Docker health check also verify database connectivity.
Production mode exits at startup with a clear error if no database settings
are supplied, instead of silently creating a local SQLite database. The
database tables and seed users/products are created automatically after
connection succeeds.

The backend uses OpenAI's Responses API for general product questions when
`OPENAI_API_KEY` is configured. Add the key as a PrimeCloud secret; never put
it in frontend variables, source files, or Git. `OPENAI_MODEL` is optional and
defaults to `gpt-4.1-mini`. Price lookups remain database-backed, engineer
safety queries keep their existing deterministic response, and customer
access checks run before any AI request. If the key is absent, general chat
uses the existing catalog-only fallback.

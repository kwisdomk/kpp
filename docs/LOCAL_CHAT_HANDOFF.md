# Local text chat patch - 13 November 2026

Status: applied and tested in Q:\kpp on feature/local-e2e-contracts at base
c1804e9; uncommitted, not pushed, merged or deployed. Work scope: B-08 chat
adapter (§7.4; B-07 in §14) and partial B-05 catalogue authentication.
Neither task nor G2 is claimed complete. Frontend dependency restoration and
chat response display follow-up are complete; browser verification is blocked
by the unavailable browser access host.

Later backend session/conversation enforcement and its 79-test result are
recorded in [SECURITY.md](SECURITY.md). Older token behavior described below
predates that change; newly required session binding means users must log in
again. The two delegated tasks have since been reviewed; the latest catalogue
ACL/image/OCR boundary and verification are in
[the OCR contract](ocr_identification_contract.md). Frontend authentication still
needs separate integration work.

## Source and changes

Backend implementation baseline matches main@c1804e9. The temporary source was
exported from local HEAD@1db776e, with the changed backend tests and deployment
files restored from GitHub c1804e9. Unrelated frontend files in this copy are not
a deployment candidate. The patch applied cleanly to the current checkout;
pre-existing documentation and schema edits were preserved.

- app/services/ai.py: optional LLM_BASE_URL/LLM_MODEL chat adapter, separate local
  key, bounded configuration, no automatic hosted fallback, final-text checks.
- app/services/chat.py and app/api/chat.py: local_assistant trace label,
  product:ID context references and database-generated excerpts.
- app/api/catalog.py: authentication on catalogue and legacy aliases; comparison
  field allowlist prevents arbitrary ORM attribute requests.
- tests/test_api.py and tests/test_local_chat.py: authenticated catalogue and
  local routing, role context, key isolation, failure and malformed-output tests.
- docker-compose.yml and DEPLOYMENT.md: optional local connection settings and
  host/container/cloud addressing requirements. No database schema changes.

Local endpoint contract follows https://lmstudio.ai/docs/developer/openai-compat/chat-completions.

## Integration verification in Q:\kpp

- `git apply --check C:/Users/wisdo/AppData/Local/Temp/kpp-local-chat.patch`
  and `git apply` succeeded; `git diff --check` passed.
- Backend: **41 passed in 6.75 s**, using bundled Python 3.12, existing venv
  packages and an isolated temporary SQLite database. Exact invocation:

  ```powershell
  & 'C:\Users\wisdo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -c "import os, sys, tempfile; sys.path.append(r'Q:\kpp\.venv\Lib\site-packages'); sys.path.insert(0, r'Q:\kpp\backend'); run_dir = tempfile.TemporaryDirectory(prefix='kpp-patch-tests-'); os.environ['DATABASE_URL'] = 'sqlite:///' + run_dir.name.replace(chr(92), '/') + '/tests.db'; os.environ.pop('LLM_BASE_URL', None); os.environ.pop('OPENAI_API_KEY', None); import pytest; raise SystemExit(pytest.main(['backend/tests', '-q', '-p', 'no:cacheprovider']))"
  ```

  Tests exited 0. Temporary-directory cleanup then reported a Windows SQLite
  file lock; the test database was removed after the Python process exited.
  For future runs, dispose `app.db.database.engine` before temporary cleanup.
- Bundled Python `-B -m unittest discover -s ai/tests -q`: **43 passed in
  2.024 s**.
- `npm run build`: **failed**, TS2307 at `src/App.tsx:23`: installed
  `lucide-react` module/types missing. It is already declared in package.json;
  no frontend source, dependency manifest or lockfile was changed by this patch.
- Both-role FastAPI tests used mocked inference. Live model inference, browser
  behavior, Docker and public deployment were not rechecked during integration.

## Frontend and live HTTP follow-up

- Scope: F-07/F-09/F-10 and B-08 integration. `src/App.tsx` now renders the
  conversation, backend warnings/confidence, expandable source IDs/excerpts and
  tool label in both chat views. Previously the dedicated Chat Assistant page
  hid all returned messages. It now shows pending/error states and disables
  duplicate/empty sends. `src/App.css` adds bounded message scrolling and source/
  warning styles. No backend contract was changed by this follow-up.
- `npm install --ignore-scripts --no-audit --no-fund --package-lock=false
  --prefer-offline --fetch-retries=0 --fetch-timeout=20000` failed with ERESOLVE
  (`vite@undefined`). Registry checks confirmed the declared Vite and lucide
  versions. `npm ci --ignore-scripts --no-audit --no-fund --fetch-retries=0
  --fetch-timeout=20000` then succeeded: **171 packages installed**. The existing
  package.json and package-lock.json were preserved.
- `npm run lint`: **passed**. The first `npm run build` after restoration ran
  out of memory while inference was active. Observed available RAM was 221 MiB,
  available commit 523 MiB (97% physical memory load).
- After inference finished and the temporary backend stopped, this scoped build
  succeeded (TypeScript + Vite 8.3.8; 2,085 modules; Vite build 5.06 s):

  ```powershell
  $saved_node_options = $env:NODE_OPTIONS
  $saved_rayon_threads = $env:RAYON_NUM_THREADS
  try {
    $env:NODE_OPTIONS = '--max-old-space-size=384 --v8-pool-size=1'
    $env:RAYON_NUM_THREADS = '1'
    npm run build
  } finally {
    $env:NODE_OPTIONS = $saved_node_options
    $env:RAYON_NUM_THREADS = $saved_rayon_threads
  }
  ```

- Live LM Studio discovery confirmed the existing Qwen instance was loaded;
  no model was loaded/unloaded or configuration changed. A temporary Uvicorn
  server used the current checkout, an isolated seeded SQLite DB, explicit
  `LLM_BASE_URL=http://127.0.0.1:1234/v1` and the observed
  `LLM_MODEL=qwen3.5-4b-claude-4.6-opus-reasoning-distilled`; hosted credentials
  were removed from that process. No .env file was changed.
- Real `httpx.Client` -> `http://127.0.0.1:8080/api/v1` -> backend -> local Qwen
  smoke sequence: health 200; anonymous catalogue 401; both seeded role logins
  and catalogues 200. The query was: "Which equipment model numbers are listed?
  Answer in one short sentence using catalogue references."
- Customer chat: **200 in 22.88 s**; engineer chat: **200 in 22.96 s**. Both
  returned JCT-500, JCG-1000 and JCS-50, `local_assistant`, three product-row
  references/excerpts, and the synthetic-demo warning. Customer internal-margin
  query returned `access_control` with no citations. These are two smoke
  requests, not a benchmark or proof of per-resource authorization. The server
  was stopped and its temporary database removed afterward.
- Browser discovery failed twice: **"The browser access host is unavailable"**;
  native computer-use pipe was also unavailable. No visual browser pass,
  screenshot, keyboard/mobile check or end-to-end UI result is claimed.
- F/B/A review requested for the displayed citation semantics and integration.
  Local code changes remain uncommitted. The separate README acknowledgements
  commit `a0fe9ab` appeared during this work and was preserved.

## Earlier temporary-copy results

- Backend: 41 passed in 6.74 s (`pytest backend/tests -q -p no:cacheprovider`).
- AI: 43 passed in 2.168 s (`python -B -m unittest discover -s ai/tests -q`).
- Execution used bundled Python 3.12 and appended the readable existing
  Q:\kpp\.venv\Lib\site-packages to sys.path. The normal project Python
  executable was inaccessible. No new dependency was installed.
- Real FastAPI TestClient -> authentication -> chat route -> local LM Studio
  Qwen inference -> JSON response, with no mocked model: customer HTTP 200 in
  58,646.974 ms; engineer HTTP 200 in 25,624.963 ms. Both returned JCG-1000,
  JCT-500 and JCS-50, three product references/excerpts, and synthetic-data warning.
- These are two smoke requests, not latency or quality benchmark results.

## Remaining limits and owner handoff

Review requested from B/A for provider and authorization behavior and from F for
the local_assistant label and citation display. No approval is recorded here.
Catalogue authentication now precedes endpoint execution. All current rows are
shared synthetic demo data: per-row ACLs, restricted-document retrieval,
manufacturer-page citations and answer-level grounding validation remain absent.
The returned citation list identifies supplied context, not which claims passed
independent validation. Model provenance/licence approval is still pending.
No browser, Docker build, public deployment or hosted provider was exercised.

Pre-existing Q:\kpp changes, including the project-plan.md rename and pending
schema contracts, were preserved. Integration is recorded in project-plan.md
§19. Review request: B/A should review provider selection and authentication;
F should review product:ID references/excerpts and the local_assistant label.
No owner approval is claimed. Next checkpoint: restore browser access and verify
both-role browser text flows; agree per-resource authorization and demonstrate
one approved document-backed answer. G2 remains incomplete.

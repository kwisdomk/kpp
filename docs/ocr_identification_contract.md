# Image identification contract

Status: implemented locally; F/A contract and DB cross-review requested before
merge. Scope: B-05/B-07 and A-05 (§7.4/§9.7). This is a nameplate-code OCR
baseline, not a completed multimodal flow or recognition accuracy evaluation.

## Requests and identity

All routes also exist without the `/api/v1` prefix. Authentication uses the
server-validated cookie or session-bound bearer described in [SECURITY.md](SECURITY.md).
No client/model role, visibility list or candidate IDs determine authorization.

| Request | Behavior |
|---|---|
| `POST /api/v1/media?kind=image` | Multipart `file`; return existing `id`, `kind`, `content_type`, `size_bytes` fields |
| `GET /api/v1/media/{id}` | Return only the uploader's active sanitized image; private/no-store and nosniff |
| `POST /api/v1/media/{id}/identify` | No body required; authorize image, select authorized catalogue pool, run local OCR, match codes |
| `DELETE /api/v1/media/{id}` | Remove uploader-owned file and mark inactive; expired images can also be deleted |

Image upload verifies both declared MIME and decoded JPEG/PNG/WebP bytes,
rejects invalid/truncated/animated images, and enforces 8 MiB input/output,
4,000,000 decoded pixels and 4096 pixels per edge. EXIF orientation is applied;
only RGB pixels are re-encoded to PNG, with input metadata removed. Total request
bytes are capped at 8 MiB + 64 KiB multipart overhead, including streamed bodies,
before unbounded multipart spooling. The Nginx API proxy cap is 9 MiB so it can
pass a permitted multipart request to the stricter application limit. Decode/OCR share one nonblocking processing
slot per backend process; busy requests return 429. Run one worker on Athena.
Transparent pixels are composited onto white before RGB encoding, so invisible
source colors are not exposed to OCR as visible text.

Files use server-generated IDs under `MEDIA_STORAGE_DIR` (default repository
`data/uploads/`; Docker uses `/app/data/uploads`), excluded from Git/build context.
Filenames from the request never select a storage path. Access expires after
60 minutes. Explicit deletion removes bytes; an automatic expired-file cleanup
job and per-user disk quota are still outstanding. Do not describe this as a
complete retention/rate-limiting solution. Canonical audio storage is now covered
by the [speech handoff](asr_handoff.md).

## Catalogue access contract

The additive `product_access` table has `product_id` (FK/primary key) and
`access_level` (`public` or `engineer`). Missing/unknown grants deny access.
Customers retrieve public rows; engineers retrieve public and engineer rows.
The SQL join/predicate runs before product materialization and before OCR.
The same predicate covers list/detail/legacy catalogue routes, price, compare,
chat context and product-row citation excerpts. It does not implement future
document/vector ACLs that do not yet exist.
The optional hosted chat path refuses engineer-only context with 503; that
context requires the explicitly configured local endpoint. Public-only optional
hosted behavior is preserved. User access is not treated as permission to export
restricted rows to a hosted provider.
This guard covers the legacy hosted branch. `LLM_BASE_URL` remains trusted server
configuration and must point to the approved Athena service; URL validation
does not independently establish a provider's physical location.

Startup creates the new table without altering existing columns. Its initial
upgrade explicitly grants public access only to the three known synthetic demo
codes JCG-1000/JCT-500/JCS-50. Unknown existing products remain unclassified.
Existing grants are preserved; deleting a grant is not undone on restart.
New seeded demo rows receive their explicit grants. SQLite upgrade behavior is
tested; deployed MySQL migration/runtime behavior has not been exercised.
New test/data products must receive deliberate grants; access is not a default.

The existing `ai/multimodal/nameplate_ocr.py` byte-input helper is retained.
Backend IDs remain integers; its internal string references map only to the
already authorized ORM pool. Text never adds a candidate, changes a role or
calls an LLM/tool. Matching normalizes case, spacing and common model-code punctuation and preserves
alphanumeric boundaries. OCR substitutions such as O/0 are not silently guessed.

## Response

The typed source is
[`backend/app/schemas/identification.py`](../backend/app/schemas/identification.py).

| `status` | Candidates | Required next behavior |
|---|---|---|
| `identified` | Exactly one | Show matched catalogue code and ask equipment confirmation |
| `ambiguous` | Multiple, at most 10 returned | Ask which candidate matches; never select automatically |
| `unidentified` | Empty | Ask for a clearer/cropped nameplate or manual model entry |

Fields: `media_id`, `status`, `reason`, `candidates`, `candidates_truncated`,
`requires_confirmation`, `warnings`, `ocr_engine`, `tool_trace_id`, `latency_ms`.
Each candidate contains integer `product_id`, `model_number`, `name`, `category`,
`source_id=product:ID` and `match_method=normalized_model_code`.
`reason` is one of `one_model_match`, `multiple_model_matches`, `no_match`,
`no_text`. No raw OCR text or unmeasured confidence percentage is returned.
The API always requires equipment confirmation, even though the existing helper's
internal flag only indicates matching ambiguity. References identify catalogue
rows, not approved manual pages or physical equipment identity.

Errors: 401 authentication; 404 absent/foreign/inactive media or inaccessible
product; 410 expired/missing owned image; 413 limits; 415 invalid/mismatched
image; 429 busy; 503 missing OCR/storage; 504 OCR timeout; 502 OCR execution/output
failure. Missing OCR is an error, not a successful `unidentified` result.
OCR attempts record success/failure in the existing audit table without raw image
or OCR contents. This is not a complete per-tool trace viewer.

`/chat/query` now accepts at most one owned photo and one owned audio recording.
It preflights every attachment before native processing, prepares identification
and transcript inputs and asks clarification on model disagreement. The frontend
wiring is implemented; browser recording and native speech remain unverified.
See the [speech integration follow-up](asr_handoff.md#protected-audio-and-combined-input-follow-up).
Approved technical retrieval is still unavailable; media answers do not invent
manual citations or procedures.

## Runtime setup and verification

Pillow 13.0.0 is installed and declared (`Pillow>=13,<14`, MIT-CMU). Native OCR
uses Tesseract plus English traineddata (Apache-2.0), not `pytesseract`, GPU or a
hosted model. The Dockerfile installs Alpine `tesseract-ocr` and
`tesseract-ocr-data-eng`; Docker build/deployment are not verified here.

Windows package installation was approved and completed through winget
`UB-Mannheim.TesseractOCR` version `5.4.0.20240606`. Winget verified the installer
SHA-256. The installer ignored the requested project-local location and used
`C:\Program Files\Tesseract-OCR`; that actual location was checked with
`--version` and `--list-langs` (`eng`, `osd`). No installer/weights are committed.
Set this in the backend terminal before starting the documented app:

```powershell
$env:TESSERACT_CMD = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

The adapter accepts only a positive timeout up to 20 seconds, fixed English/PSM 6,
one OpenMP thread and bounded output. It never uses a shell. Local `.env` files
were not changed. The existing loaded Qwen model was not loaded/unloaded or used
by OCR. There is no automatic engine/provider fallback.

Native route smoke evidence is recorded once in
[`reports/ocr_boundary_smoke.json`](../reports/ocr_boundary_smoke.json): six real
requests across both roles and all three result states, using three clean
synthetic images. This is not held-out accuracy or the 30-image dataset.

Final verification: **120 backend tests passed in 31.24 s**, including the
reviewed catalogue-tool tests, session regressions and image/ACL cases;
**55 AI tests passed in 2.615 s**. Backend tests use isolated SQLite databases
and mocked OCR/provider failures; the six native route smokes are separate.
`npm run lint` and the documented low-memory `npm run build` passed independently
after reviewing Agent 1's changes (Vite build 3.52 s). `git diff --check` passed.
Agent 2's tool tests needed explicit public grants and active mock users for the
new ACL contract; missing-product and unauthenticated comparison cases were
also added. These are regression checks, not an AI benchmark.

Exact final Python check from the repository root:

```powershell
& 'C:\Users\wisdo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -u -c "import os,sys,tempfile,unittest;sys.path.append(r'Q:\kpp\.venv\Lib\site-packages');sys.path.insert(0,r'Q:\kpp\backend');run_dir=tempfile.TemporaryDirectory(prefix='kpp-ocr-boundary-final-');os.environ['DATABASE_URL']='sqlite:///'+run_dir.name.replace(chr(92),'/')+'/suite.db';os.environ.pop('LLM_BASE_URL',None);os.environ.pop('OPENAI_API_KEY',None);import pytest;result=pytest.main(['backend/tests','-q','-p','no:cacheprovider','--tb=short','--maxfail=1','--basetemp',run_dir.name+'/pytest']);from app.db.database import engine;engine.dispose();run_dir.cleanup();suite=unittest.defaultTestLoader.discover('ai/tests');ai_result=unittest.TextTestRunner(verbosity=1).run(suite) if result==0 else None;raise SystemExit(result if result else (0 if ai_result.wasSuccessful() else 1))"
```

F review requested for the result states, confirmation UX and HTTP errors; A
review requested for the retained helper, candidate mapping and held-out design.
The new table/bootstrap and pre-materialization predicate also require a second
backend review before merge. No shared-contract approval is claimed. Branch:
`feature/local-e2e-contracts`, HEAD `a0fe9ab`; implementation remains uncommitted.

Sources consulted: [Pillow image security](https://pillow.readthedocs.io/en/stable/handbook/security.html),
[Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html),
[CLI](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage),
[winget installer manifest](https://github.com/microsoft/winget-pkgs/blob/master/manifests/u/UB-Mannheim/TesseractOCR/5.4.0.20240606/UB-Mannheim.TesseractOCR.installer.yaml).

Remaining: B/F/A response/ACL review and browser upload/recording verification,
approved catalogue/documents, actual labeled held-out image evaluation, part
recognition, native ASR and full multimodal answer evaluation, expired-file cleanup,
resource quotas and deployment.

## Transparency and data-readiness follow-up

On 13 November 2026, a synthetic 900x200 RGBA image with Arial-64 `JCG-1000`
text reproduced a sanitizer defect. With all text/background alpha values zero,
the image was visually blank, but RGB conversion exposed its stored colors and
native OCR returned `JCG-1000`. White-background compositing now returns empty
OCR text; the opaque text control still returns `JCG-1000`. These are development
regressions, not held-out accuracy.

Focused `test_image_identification.py` verification passed **34 tests in 23.78 s**,
using the isolated pytest runner above with only that file selected. New cases
cover zero/partial/full alpha and palette transparency. Native before/after
probes used the installed Tesseract and checked free memory first. Frontend lint
and the scoped low-memory build passed (Vite 5.16 s); diff checks passed. Earlier
full-suite numbers are historical and were not rerun for this focused change.

The static green Online/Secure Session badge was replaced with neutral
`Status unknown / Connection not checked`. Live connectivity/session detection
remains pending.

The user confirmed that no field images or KB are ready; data-definition answers
are being prepared. The supplied PDF was reviewed read-only. Before import,
agree external Jenga ID to integer DB ID mapping and `model` to `model_number`
mapping; keep unit/serial identity separate. Technical facts require sources;
fictional commercial data can be seeded synthetic records. The definition's
explicit supplier/assignment permissions are more granular than the current
two-level catalogue grants. No generator, schema or PDF was changed here.

Next: an approved source-backed product slice and ingest mapping, then image
UI/confirmation and independent labeled development/held-out photos. Further
OCR algorithm tuning waits for representative images. Full challenge data and
benchmark minimums remain required.

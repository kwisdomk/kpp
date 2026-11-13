# Session and conversation security

Status checked against repository `main@2675ac9` on 13 November 2026. The session
work below was merged through PR #4; the original 79-test result is an earlier
local checkpoint. Later reconciliation evidence is in the
[reconciliation handoff](https://github.com/kwisdomk/kpp/blob/main/docs/reconciliation_handoff.md). Deployed version and
production security have not been verified by this documentation review.

This is a record of tested controls and open work, not a security certification
or a claim that G2/G5 are complete. Source-document and vector access controls
remain incomplete. See the [OCR contract](https://github.com/kwisdomk/kpp/blob/main/docs/ocr_identification_contract.md).

## Enforced behavior

- Login rejects inactive accounts and unsupported database roles.
- Each newly issued JWT contains a server-generated `sid` referencing the hash
  of its stored opaque session token. The raw cookie token is not in the JWT.
  Bearer access requires that stored session to be active, unexpired and within
  the role's idle limit. Its current user and role must match the token claims.
- Cookie and bearer access share the same session lifecycle checks. An invalid
  bearer cannot fall back to a valid cookie for a protected resource. When two
  valid credentials differ, the explicit bearer determines the request identity.
- Logout revokes the valid session(s) represented by the submitted credentials
  and clears the cookie. An active cookie can still be revoked when a submitted
  bearer is expired. Other logins not submitted in the request remain active.
- `/auth/me` supports the same cookie/bearer authentication as protected routes
  and returns the existing `id`, `username` and trusted `role` fields.
- Before retrieval/inference, chat rejects unknown/foreign conversations with
  404 and finished conversations with 409. A first chat without a conversation
  reference creates and commits an owned conversation, making its returned ID
  usable by the existing review submission endpoint.
- Empty/whitespace questions and conflicting conversation references return 422
  before creating a conversation or calling inference.

## Compatibility and cross-role review

In the original session patch, no response fields, DB tables or migrations changed.
Later reconciliation added account chat history. Existing JWTs without the
new session binding are rejected: users must log in again. `session_id` remains
an accepted legacy conversation reference; it must identify an existing owned,
active conversation. If both reference fields are sent, they must match.

The current frontend calls `/auth/me` to restore the trusted role, clears local
state and attempts server logout. The reconciliation added owner-bound message
history and protection against a demoted customer reading earlier engineer
history. Cross-role owner reviews were requested; no approval is recorded in the
reconciliation handoff. Browser and deployment behavior still need verification.

## Verification

The reconciliation handoff records a later **162-test backend suite** with
isolated SQLite and mocked provider/native boundaries, plus **79 AI tests**.
Those historical results do not establish live model, browser or deployment
behavior. See [commands and limits](https://github.com/kwisdomk/kpp/blob/main/docs/reconciliation_handoff.md#verification).
The earlier session-specific run follows for traceability.

`backend/tests/test_session_conversation_security.py` adds **38 regression cases**
with per-test temporary SQLite databases and blocked provider calls. The initial
run was blocked by permissions on pytest's default temporary directory; it did
not exercise application behavior. Explicit isolated `--basetemp` fixed the
test setup. The final run passed **79 tests in 21.64 s**: the 38 new cases and
41 pre-existing backend tests. The parallel agent's catalogue-tool test file was
not included or reviewed.

Exact final command from Q:\kpp, using bundled Python and existing packages:

```powershell
& 'C:\Users\wisdo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -u -c "import os,sys,tempfile;sys.path.append(r'Q:\kpp\.venv\Lib\site-packages');sys.path.insert(0,r'Q:\kpp\backend'); run_dir=tempfile.TemporaryDirectory(prefix='kpp-session-regression-');os.environ['DATABASE_URL']='sqlite:///'+run_dir.name.replace(chr(92),'/')+'/suite.db';os.environ.pop('LLM_BASE_URL',None);os.environ.pop('OPENAI_API_KEY',None);import pytest;paths=['backend/tests/test_api.py','backend/tests/test_ai.py','backend/tests/test_database_config.py','backend/tests/test_database_startup.py','backend/tests/test_deployment_config.py','backend/tests/test_local_chat.py','backend/tests/test_session_conversation_security.py'];result=pytest.main(paths+['-q','-p','no:cacheprovider','--tb=short','--maxfail=1','--basetemp',run_dir.name+'/pytest']);from app.db.database import engine;engine.dispose();run_dir.cleanup();raise SystemExit(result)"
```

Tests cover both roles/transports, expiry, logout and credential replay, disabled
accounts, invalid token/session/role binding, cross-user and finished chat,
owned review submission, and request validation before retrieval/inference.
No live model, browser or deployed service was exercised in this security run.

## Remaining work

- Verify frontend identity restoration, logout and expiry UX in a real browser.
- Catalogue grants now filter rows before lookup, as documented in the OCR
  contract. Approved restricted documents and document/vector ACLs remain absent.
- Known demo credentials and development signing-secret defaults remain. Cookie
  Secure/CSRF/CORS configuration, rate limiting and production deployment need
  separate hardening and verification.
- Images have bounded decode, metadata removal, owner-bound access and an OCR
  endpoint. Audio validation, ASR adapters, fusion and account upload quotas are
  implemented. Native accuracy and browser media journeys remain unverified;
  automatic local disk reclamation remains incomplete. See
  [media policy](https://github.com/kwisdomk/kpp/blob/main/DEPLOYMENT.md#local-inference-and-media-selection).
- Claim/numeric/citation validation, robust adversarial testing, complete failed-
  tool audit logging and calibrated confidence are absent. The review endpoint
  can receive an owned chat reference, but reviewer resolution/correction and
  UI handoff are not complete. Account-bound messages are stored in the database;
  their production behavior needs verification.
- The 60-item AI benchmark, model/source approvals and browser/deployment checks
  remain outstanding. Passing these regressions is not a security certification.

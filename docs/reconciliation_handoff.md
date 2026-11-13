# Local reconciliation handoff

13 November 2026. This is a local review branch, not a deployment or release.

## Checkout and commits

- Branch: `feature/backend-local-reconciliation`
- Checkout: `Q:\kpp\tmp\reconcile-worktree`
- Original checkout: `Q:\kpp`, still on `feature/local-e2e-contracts`.
  Its existing source changes were preserved; do not apply this branch's patch
  wholesale over that dirty tree or run a blind pull there.
- Local snapshots: `0b277f2` backend/AI, `d7b3f77` frontend,
  `bafea83` documentation and canonical plan rename.
- Reconciliation merge: `8657a40`, including `main@0d8cb73`.
- API proxy fix: `253d8ce`, cherry-picked from `602479e` on
  `origin/fix/vercel-api-proxy`, preserving its authorship.
- Production same-origin selection: `d24a802`, cherry-picked from the newly
  fetched `0ea6ebd` on that branch. Production ignores the development URL
  override and uses the API rewrite. The intervening `eba9b5b` mixes GET retries
  and product imagery and stays separate; its generic errors need reconciliation
  with this branch's typed authentication/recovery errors before integration.
- `origin/feature/frontend-copilot-visuals@c46c484` remains separate.
  It has not been merged or represented as verified by this checkpoint.

No push, PR, merge into `main`/`dev`, or deployment was performed. Continue from
this isolated checkout for review and browser testing.

## Integration decisions

The split Vercel frontend / Python PrimeCloud backend, env templates, health
probes, product illustrations and account history from main are retained.
Docker/Nginx files stay removed, matching main's hosting decision. The Vercel
API rewrite targets the domain recorded by the upstream proxy-fix branch and
precedes the SPA fallback. Static checks do not establish that domain's runtime
health, deployment version or permissions.

Local trusted sessions, catalogue ACLs, source-filtered response citations,
comparison tables, frontend identity recovery and OCR/ASR adapters are retained.
Sign Out attempts server revocation, clears protected state and aborts in-flight
chat requests. Persisted comparisons/citations survive history reload. Customer
history is withheld before message retrieval when server-written audits show an
engineer or unclassified conversation; this covers role demotion.

Photo/voice default to local processing. The optional hosted profile requires
operator opt-in, no selected local endpoint and explicit request consent.
Restricted catalogue context is rejected before hosted attachment loading or
speech inference. Missing local engines do not cause a hosted fallback.
See [DEPLOYMENT.md](../DEPLOYMENT.md#local-inference-and-media-selection).

The experimental `backend/app/schemas/contracts.py`, generation drafts, input
PDF, standalone Token Lab probes, real env files and temporary runtime files
remain in the original checkout and are excluded from these commits. Its
agreement claims must not substitute for B/A review.

## Verification

Commands and the isolated Python runner are recorded in
[project-plan.md section 19](../project-plan.md#19-execution-ledger--live-state-to-update-collaboratively).

- Combined backend suite: **162 passed in 91.44 s** before the two-file proxy
  cherry-pick. Includes upstream tests and seven integration regressions.
- After the proxy-configuration cherry-pick, deployment configuration tests:
  **8 passed in 9.29 s**. The later same-origin commit changes frontend source
  only; the final frontend build check is recorded in section 19.
- AI unittest discovery: **79 passed in 5.568 s**.
- Frontend recovery tests: **8 passed**; lint and production build passed.
  Final Vite phase after the same-origin fix: **8.80 s**, with the scoped
  low-memory settings in section 19. Building with a development API override
  on a reserved `.invalid` domain left that hostname out of all emitted JS.
- Diff whitespace check passed. Snapshot hashes confirmed 74 original files
  unchanged. Tracked-file checks found no credential-pattern matches, real env
  files, model weights, databases or PDFs. Pattern checks are not a secret audit.

These are isolated tests, not executed-browser, native-model, hosted-provider,
PrimeCloud/MySQL or Vercel runtime verification. Source approvals, canonical
mapping, model provenance and held-out evaluation remain incomplete. Generic
safety routing does not establish manufacturer evidence or a completed human
review/resolution process.

## Review and next work

B owner: review session/history ACLs, database table startup and hosted gates.
F owner: review combined account chat, identity transitions, both-role media,
comparison display and logout failure feedback. A owner: review local/hosted
selection, evidence provenance and media ambiguity handling. These reviews are
requested; no owner approval is recorded.

Next verify the customer and engineer text journeys in the browser, then role
tampering, logout replay and cross-account access. Configure verified native
dependencies and check free memory before attempting real OCR/ASR or local model
inference. Review the separate visuals branch independently. Re-fetch before any
future publication; do not push or merge until the intended target is agreed.

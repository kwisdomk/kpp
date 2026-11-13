# A-01 / A-02: AI/Data/Evaluation Handoff

OWNER: AGENT-A / KWAIX

TASK: A-01 (Catalogue Sourcing) & A-02 (Ingestion Preparation) [Section 9.7 Task IDs]

MERGED: [PR #1](https://github.com/kwisdomk/kpp/pull/1) into `main` at
`1db776e` on 13 November 2026, 00:54 EAT.

Merge records the code and evidence in the shared branch. Rights, technical
review, model approval and the B/A contracts remain pending.

STATUS: A-01 evidence recorded; rights and human technical review pending; A-02 preparation in progress

---

## 1. Source and ingestion handoff

```text
TASK: A-01 | A-02
OWNER: AGENT-A (KWAIX)
MERGE COMMIT: main@1db776e (PR #1; source branch feature/ai-catalogue-sources)
CHANGED FILES:
  - .gitignore (added .env, .env.*, model-weight and data-index exclusions)
  - data/catalogue/products.csv (15 candidates; exact document URLs where verified; verified: false)
  - data/manifests/source_candidates.json (15 candidates with document hash/locator and pending rights)
  - data/manifests/sources.csv (13 pending commercial document links plus 6 BMS chapters)
  - reports/catalogue_sourcing_research.md (evidence and rights review)
  - reports/catalogue_source_review.json (machine-readable slot review)
  - reports/catalogue_review.md (status and test evidence)
  - reports/{source_validation.json,catalogue_validation.json} (generated checks)
  - reports/{hardware_baseline.json,hardware_baseline.md}
  - DATA.md (candidate count, evidence and rights status)
  - ai/ingestion/normalize_specs.py (source/specification linking and catalogue validation)
  - ai/tests/test_normalize_specs.py (specification validation tests)
  - project-plan.md (section 19 ledger updated)
  - docs/AI_HANDOFF.md (this handoff)
CONTRACT CHANGES: none to backend/frontend APIs or DB tables; test adapters within ai/ only
TEST COMMAND(S) AND REAL RESULT:
  - python -B -m unittest discover -s ai/tests -v: 43 PASSED in 3.641 s
  - python -B -m ai.ingestion.manifest --require-coverage --report reports/source_validation.json: Exit 1 (expected; 19 pending rows, 0 verified assets)
  - python -B -m ai.ingestion.normalize_specs --catalogue data/catalogue/products.csv --require-coverage --report reports/catalogue_validation.json: Exit 1 (expected; 15 rows, 0 verified, 2 missing source links)
NEW DATA / MODEL / LICENSE REFERENCES:
  - 15 candidate models recorded; 13 have a checked official document URL plus SHA-256; page locators recorded where inspected
  - Kipor KDE6700TA and Cummins C55D5 still need official document URL and hash
  - Libre Solar BMS C1 manual (CC BY-SA 4.0, commit 7c2dcc1c4f26) retained as pending sample
  - Commercial processing, quotation and redistribution permissions: pending_review for all 15
SECURITY, SAFETY OR BENCHMARK IMPACT:
  - .env safely excluded from Git
  - Gold benchmark answers strictly separated from retrieval corpus
  - All 15 candidates flagged verified: false; no commercial PDFs committed
  - No human review, technical approval or rights approval is claimed
BLOCKER(S):
  - B contract alignment: integer vs string product IDs, spec table structure (JSON vs relational spec_values), and pre-retrieval AuthContext
  - Human review of processing, quotation and redistribution rights
  - Human technical review of candidate specifications and safety content
  - Athena host identity not independently confirmed; 8 GB visible RAM requires sequential model loading
NEXT DEPENDENT OWNER / TASK:
  - AGENT-B: Review ID and specification contracts; publish pre-retrieval AuthContext
  - AGENT-A: Verify Kipor/Cummins documents and advance A-02 page/chunk ingestion
LEDGER UPDATE (section 19): Recorded below and in master plan
```

---

## 2. Research Details: 15 Candidate Slots

All slots preserve existing identifiers (`JC-PMP-001..005`, `JC-GEN-001..005`,
`JC-INV-001..005`). The values below are candidate summaries, not approved
catalogue facts. Document URLs, SHA-256 values and blockers are in
`data/manifests/source_candidates.json`.

### Industrial Pumps (`industrial_pumps`)

1. **JC-PMP-001**: Dayliff DDP 60 (0.37 kW, 240 V, max head 35 m, max flow 3.0 m³/h, IP44, 5.3 kg) — [datasheet p. 1](https://www.dayliff.com/media/com_hikashop/upload/safe/ddp60.pdf)
2. **JC-PMP-002**: Dayliff DSD 3/18 (1.1 kW, 240 V, nominal flow 3.0 m³/h, max head 129 m, IP68; mass 11 kg pending technical confirmation) — [datasheet p. 2](https://www.dayliff.com/media/com_hikashop/upload/safe/dsd-datasheet.pdf)
3. **JC-PMP-003**: Dayliff DB 4/30 (0.77–0.82 kW, 240 V, max head 30 m, max flow 4.0 m³/h, IP54, 11.5 kg) — [datasheet p. 4](https://www.dayliff.com/media/com_hikashop/upload/safe/db_685346571.pdf)
4. **JC-PMP-004**: Dayliff DDJ 750 (0.75 kW, 240 V, suction lift 9 m, IP44, 17 kg) — [ddj.pdf](https://www.dayliff.com/products/product/download/file_id-7339); complete PDF still required
5. **JC-PMP-005**: Pedrollo CP 158 (0.75 kW, 230 V, head 25–36 m, flow 0.6–5.4 m³/h, IPX4; mass 12.4 kg 1-ph / 12.3 kg 3-ph) — [datasheet pp. 2–3](https://www.pedrollo.com/wp-content/uploads/schede-tecniche/EN/CP_EN-datasheet_50Hz.pdf)

### Power Generators (`power_generators`)

6. **JC-GEN-001**: Honda EU22i (1.8 kW rated / 2.2 kW max, 230 V, tank 3.6 L, 53–62 dB(A), 21.1 kg) — [owner's manual pp. 55–56](https://cf.hondappsv.com/files/OM/OM000567HME/00X36-Z44-G010_EU22iT_HME_en.pdf)
7. **JC-GEN-002**: Honda EG6500CX (5.0 kVA rated / 5.5 kVA max, 220 V, tank 24 L, 70–74 dB(A), 87 kg) — [owner's manual pp. 42–43](https://cf.hondappsv.com/files/OM/OM001285MEX/4MZ306031_web.pdf)
8. **JC-GEN-003**: Kipor KDE6700TA (4.5 kVA rated / 5.0 kVA max, 230 V, tank 15 L, 72 dB(A), 170 kg) — official document URL/hash pending
9. **JC-GEN-004**: FG Wilson P22-1 (20 kVA prime / 22 kVA standby, 400 V 3-ph, 5.4 L/h) — [datasheet pp. 1–3](https://fgwilson.ie/wp-content/uploads/2022/11/P22-1.pdf)
10. **JC-GEN-005**: Cummins C55D5 (50 kVA prime / 55 kVA standby, 400 V 3-ph, 11.4 L/h, 922 kg open) — official document URL/hash pending

### Solar Inverters (`solar_inverters`)

11. **JC-INV-001**: Victron MultiPlus-II 48/3000/35-32 (2.4 kW / 3,000 VA, 38–66 V DC, 95% efficiency, 35 A charger, IP22, 19 kg) — [datasheet p. 2](https://www.victronenergy.com/upload/documents/Datasheet-MultiPlus-II-inverter-charger-EN-.pdf)
12. **JC-INV-002**: Victron MultiPlus-II 48/5000/70-50 (4.0 kW / 5,000 VA, 38–66 V DC, 96% efficiency, 70 A charger, IP22, 30 kg) — same datasheet, p. 2
13. **JC-INV-003**: Growatt SPF 5000 ES (5.0 kW, 120–430 V MPPT, 48 V battery, 93% efficiency, IP20, 12 kg) — [datasheet p. 2](https://us.growatt.com/upload/file/SPF_3000-5000_ES_Datasheet_EN_202405.pdf)
14. **JC-INV-004**: Deye SUN-5K-SG03LP1-EU (5.0 kW AC, 150–425 V MPPT, 2 MPPTs, 40–60 V battery, 97.6% efficiency, IP65, 20.5 kg) — [datasheet](https://www.deyeinverter.com/deyeinverter/2024/10/21/datasheet_sun-3.6-6k-sg03lp1_241021_en.pdf); page locator pending
15. **JC-INV-005**: Huawei SUN2000-10KTL-M1 (10.0 kW AC, 140–980 V DC, 470–850 V full MPPT, 2 MPPTs, 98.6% efficiency, IP65, 17 kg) — [datasheet p. 2](https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/datasheet/SUN2000-3-10KTL-M1.pdf)

---

## 3. Backend/Security Requests Pending Agreement

1. **Product ID Format:** Agree on primary key and reference IDs (`JC-PMP-001` vs auto-increment integer `ProductDB.id`).
2. **Specification Schema:** Determine whether specifications will be stored in `ProductDB.specifications` (JSON string) or a normalized `spec_values` relational table. The manifest uses richer field names than the ingestion schema; mapping is unresolved.
3. **Pre-Retrieval Authorization:** Expose a server-derived `AuthContext` to filter retrieval candidates before similarity scoring or full-text query execution.
4. **Rights Review:** Review processing, quotation and redistribution separately. Public download access is not a reuse licence; commercial PDFs must stay outside Git until permission is recorded.

---

## 4. Cross-Role Integration Check - 13 November 2026

### 4.1 GitHub activity before merge

`origin/main` moved from `c6ed220` to `41a45c6` (9 commits) after this branch
was cut. At this check, PR #1 was open and **mergeable `clean`**. No
GitHub Actions workflow runs were configured. At `2026-11-12T21:41Z` the PR was
marked ready for review (`draft: false`) and a review was requested; the
Copilot reviewer could not run ("insufficient remaining quota"), so there is
**no human approval or review yet**. Ready-for-review is not approval.

- `acfcc72` role-aware product dashboard and conversation route;
- `50bba37` to `c359209` PrimeCloud/Docker/MySQL deployment fixes;
- `59bd655` OpenAI Responses API integration in backend chat;
- `41a45c6` removes the duplicate topbar sign-out and keeps the sidebar control
  (frontend only; no conflict with this branch).

Git metadata lists `kibuikevin@zetech.ac.ke` on the main commits and
`Hawa Muriuki` on the initial frontend commit. That is not proof of formal
role ownership. The team still needs to record its three delivery roles and
lead explicitly.

### 4.2 Local model server (observed 13 November 2026)

The local LM Studio endpoint was reachable at
`http://127.0.0.1:1234/v1`:

| Model | Type | Quantization | State | Context |
|---|---|---|---|---|
| `qwen3.5-4b-claude-4.6-opus-reasoning-distilled` | VLM | Q4_K_S | loaded | 111,104 loaded / 262,144 max |
| `google/gemma-4-12b-qat` | VLM | Q4_0 | not loaded | 262,144 max |
| `text-embedding-nomic-embed-text-v1.5` | embeddings | Q4_K_M | loaded | 2,048 max |

The loaded Qwen variant advertises `tool_use`. A warm chat probe returned `OK`
in **9,873 ms** with 144 completion tokens; it emitted `reasoning_content`
before `content`, and low `max_tokens` values produced an empty answer with
`finish_reason: length`. The embedding probe returned **768 dimensions** in
**18,837 ms**. GPU memory was 5,209 MiB used / 793 MiB free of 6,144 MiB.

This confirms connectivity and basic inference only. It is not a latency
benchmark, does not identify the host as Athena, and does not approve the
model. The loaded Qwen is a community reasoning-distilled variant, not the base
Qwen3.5-4B checkpoint named in the plan. The current backend on main calls
`https://api.openai.com/v1/responses` when `OPENAI_API_KEY` is set; it does not
call this local endpoint.

### 4.3 Status by delivery role

The application has two authenticated roles (`engineer`, `customer`). The
project has three delivery roles (`F`, `B`, `A`). This table covers delivery
roles.

| Role | Observed work | Assessment | Next action |
|---|---|---|---|
| **F - Frontend** | Role-aware dashboard, login screen and role switcher (`acfcc72`); seeded demo credentials and role stored in `localStorage`; comparison and recommendations still partly hardcoded. | Backend still treats the token/database role as authoritative, so the client role is not a server grant. But `localStorage` role, a role fallback without login, and credentials in source conflict with the documented frontend rules. | Read the role from `/auth/me`; remove the fallback role selector; keep demo credentials in seed/env configuration, not UI source; replace hardcoded comparison rows with API data. |
| **B - Backend/Security** | JWT/session authentication, database role cross-check, owner-bound conversations, MySQL/Docker deployment, optional OpenAI chat. | Catalogue endpoints have no `get_current_user` dependency or role predicate, `lookup_products` returns every row, and the OpenAI path sends catalogue text to an external provider. The integer `ProductDB.id` and JSON `specifications` choices are still unagreed with A. | Use an authorised local OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`), add pre-retrieval visibility predicates and auth dependencies to catalogue/search paths, and settle the ID/specification contract before A integration. |
| **A - AI/Data/Evaluation** | 15 catalogue candidates, 19 pending source rows, 13 verified document URLs/hashes, 43 passing tests, DSD mass correction, local model server check. | Evidence is traceable and unapproved values remain pending. Actual local models differ from the plan (`nomic` 768-dim embedding instead of BGE-small; reasoning-distilled Qwen variant). No production specification file or retrieval adapter is approved. | Record model revision/checksum/licence, test the local adapter with authorised candidate filtering, map catalogue slots to B's integer IDs, and keep benchmark/metric claims unset until measured. |

### 4.4 Recommended order

1. **B** replaces the external OpenAI call with the local OpenAI-compatible
   endpoint and adds role predicates before catalogue retrieval.
2. **F** derives role from the server session, removes client-side role
   authority and hardcoded demo passwords, and connects comparison/source
   panels to real APIs.
3. **A** records model provenance and adapts the catalogue mapping after B
   confirms the ID and specification contracts.
4. PR #1 is merged at `1db776e`. Continue from current `main` on a new task
   branch. Its scope includes AI ingestion code, tests, data and documentation;
   merging it does not approve pending sources or shared contracts.

# Data sources

A-01 is IN PROGRESS: **15 candidate products across 3 categories; 0 approved
products; 0 verified sources**.

The image-identification baseline currently matches the backend's three synthetic
demo catalogue rows. Its generated nameplate smoke images do not add approved
equipment data or satisfy the labeled/held-out image minimum. See
[the OCR contract](docs/ocr_identification_contract.md).

`data/catalogue/products.csv` maps the 15 slots `JC-PMP-001..005`,
`JC-GEN-001..005` and `JC-INV-001..005`; every row has `verified: false`.
`data/manifests/source_candidates.json` records the candidate specifications,
official URLs, SHA-256 values, page locators, rights status and blockers.
`reports/catalogue_sourcing_research.md` is the human-readable evidence record.

Thirteen slots have an official document URL that returned HTTP 200 and a
recorded SHA-256. This checks the fetched response, not source approval;
Kipor KDE6700TA and Cummins C55D5 still need an official document URL and hash.
Six BMS C1 manual chapters remain pending ingestion sample records; see
`reports/source_review.md`. There is no approved production
`specifications.csv` yet.

Required totals: 3 categories, 15 real equipment products, 30 labeled images,
15 labeled audio queries and 60 checked benchmark cases
(20 engineer / 20 customer / 10 multimodal / 10 adversarial).

## Validate the source manifest

Python 3.11+, standard library only. Run from the repository root:

```powershell
python -B -m unittest discover -s ai/tests -v
python -B -m ai.ingestion.manifest --require-coverage --report reports/source_validation.json
python -B -m ai.ingestion.normalize_specs --require-coverage --report reports/catalogue_validation.json
```

The coverage commands exit 1 until the product/category minimums are met.
Without `--require-coverage`, an empty manifest can pass format checks while
reporting `coverage_ready: false`. Media labels and benchmark cases require
separate evaluation.

The specification check validates recorded reviews and relationships; it does
not prove source rights or technical correctness. All 15 candidates remain
pending, so the catalogue report also lists `no specifications yet` until a
reviewed specification file is agreed with Backend/Security.

## Record a source

Use the columns in master plan section 6.1. The additional `local_path` column
locates the file beneath `--asset-root` (repository root by default). It is local
validation metadata; B must review it before backend integration.

A verified row needs complete provenance, a reviewer, a valid access date,
page count and a local file matching its SHA-256. Use `cleaning_steps=none` when
no cleaning was needed. Pending and rejected rows do not count. Counts use
distinct document-backed product/category IDs; shared file hashes get a warning.

The reviewer checks usage rights, license scope, attribution and technical
accuracy. The validator checks the record and file hash. For web documents,
record one logical page, preserve section anchors and label the extraction method
as HTML; do not cite that logical page as a PDF page number.

## Rights status

The 15 commercial candidates record `processing`, `quotation` and
`redistribution` as `pending_review`. These permissions are separate:
processing covers local parsing/indexing, quotation covers short cited excerpts,
and redistribution covers publishing full documents. Public download access does
not establish any of them.

Keep commercial PDFs outside Git. `data/manifests/sources.csv` records the
checked URL, SHA-256, page count and HTTP Last-Modified date; the documents
themselves were fetched to a temporary private directory for hashing and were
not committed. Preserve attribution, license and modification notices for files
that may be shared.

The BMS C1 text sample includes its original CC BY-SA 4.0 notice and a separate
attribution file. Manufacturer specifications require source and technical review;
company records, prices, inventory and suppliers will be explicitly synthetic.
Temporary test fixtures use `MOCK-*` IDs and never enter the catalogue or
retrieval corpus.

Backend schema, source permissions and media access are pending review in
`docs/AI_HANDOFF.md`. Results: `reports/source_manifest_validation.md`.

## Preview the saved manual

```powershell
python -B -m ai.ingestion.source_preview --snapshot data/manifests/bms_c1_snapshot.json --output data/processed/bms_c1_sections.json
```

The command checks file sizes, Git blob hashes and SHA-256 before extracting
sections. Output retains source text, revision, URL and line ranges for review.
It does not approve sources or build a retrieval index. PDF page fields remain
null until a pinned PDF has been mapped. Product/category IDs await B review.

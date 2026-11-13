# First source sample

12 November 2026. Task A-01; AI/Data owner KWAIX.

## Source and license

Saved the **Libre Solar BMS C1 User Manual**, by Martin Jäger / Libre Solar, at
commit `7c2dcc1c4f266ce2a977c386ddaa4319f1ed1095`.

- [Pinned manual](https://github.com/LibreSolar/bms-c1/tree/7c2dcc1c4f266ce2a977c386ddaa4319f1ed1095/manual)
- [Explicit document license notice](https://github.com/LibreSolar/bms-c1/blob/7c2dcc1c4f266ce2a977c386ddaa4319f1ed1095/manual/1-introduction.md#license): CC BY-SA 4.0.
- [License terms](https://creativecommons.org/licenses/by-sa/4.0/).

The saved copy contains six Markdown chapters and the author/title metadata.
Original source text, license notice and disclaimers are unchanged. Images have
not been downloaded. Attribution is included beside the files. Document-derived
excerpts retain the source license; application code is separate.

The earlier MPPT 1210 HUS candidate remains unresolved: its pinned repository
license is CERN-OHL-W-2.0, while the manual has an unversioned CC-BY-SA badge.
It has not been copied into the dataset.

## Check and reproduce

Python 3.14.7 was used via
`%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`.
Commands below run from the project root with that interpreter:

```powershell
python -m unittest discover -s ai/tests -v
python -m ai.ingestion.source_preview --snapshot data/manifests/bms_c1_snapshot.json --output data/processed/bms_c1_sections.json
python -m ai.ingestion.manifest --require-coverage --report reports/source_validation.json
```

| Check | Actual result |
|---|---|
| Source bytes | 7/7 file sizes and Git blob hashes match upstream; SHA-256 recorded |
| Unit and CLI tests | 43 passed, 3.641 s (current suite) |
| Section preview | 40 sections; original text and one-based line ranges preserved |
| Source manifest | 6 pending chapter records; valid CSV; coverage command exits 1 |
| Approved catalogue coverage | 0 products, 0 categories |

The preview is for review and has no backend connection. Every excerpt has a
source file, revision, URL and line range. `page` is null: the saved Markdown
has not been mapped to a pinned PDF. Headings inside fenced code remain code.
Unknown/TBD specification values remain as written in the source.

## Backend and review status

Rechecked GitHub at `0a94377951733ce69e457933f99de2e06a53d821`.
`database.py`, `api/media.py` and `schemas/chat.py` match the earlier reviewed
`0728f265` snapshot. Product IDs, normalized source/spec records, source permissions
and media persistence still need B review. Backend files remain absent locally.

The sample is **pending** catalogue suitability and human technical QA. Product
and category IDs are deliberately unassigned. The battery-management category
is not a final selection. These source files do not count toward the 15-product
minimum and have not entered a retrieval index or benchmark.

No backend API, DB, authorization or benchmark contract changed. New snapshot and
preview metadata are local review formats. Source/citation integration review
remains requested in `docs/AI_HANDOFF.md`.

Next: choose suitable source-backed catalogue models with the team, review the
saved chapters, then agree product/source IDs and ACL before A-02 normalization.
The current branch is `feature/ai-catalogue-sources`; no backend or retrieval
integration has been performed.

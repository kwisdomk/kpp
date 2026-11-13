# Source manifest validation

12 November 2026, Africa/Nairobi. Current branch: `feature/ai-catalogue-sources`.

Python: `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`
(version 3.14.7). Standard library only.

| Command using this interpreter | Result |
|---|---|
| `-B -m unittest discover -s ai/tests -v` | 43 passed, 0 failures/errors; 3.641 s |
| `-B -m ai.ingestion.manifest --require-coverage --report reports/source_validation.json` | Exit 1: valid CSV, 19 pending rows, 0 verified assets, 0/15 products, 0/3 categories |

Review reproduced four defects before fixing them:

- `--report` could replace the input CSV.
- `cleaning_steps=none` rejected a valid unchanged source.
- URL checks accepted spaces, embedded newlines and invalid ports.
- An invalid row could assign a product category and reject a later valid row.

Regression tests cover each defect. Other tests cover file hashes, paths,
malformed CSV, review metadata, dates, duplicate IDs and coverage counts. The CLI
runs in a subprocess test. All source fixtures are temporary and synthetic.

Naming: `REQUIRED_COLUMNS`, `OPTIONAL_COLUMNS`, `VALIDATION_STATUSES`,
`_is_http_url`, `valid_sources`, `_source_row`, `_validate_rows`. Manifest/API field
names are unchanged. This report replaces `ai_foundation_validation.md`.

The current run supersedes the earlier 18-test and 14-test results. Backend
tests were not run in this review. A-01 remains IN PROGRESS pending rights and
technical review; no retrieval or model-quality metrics exist.

The manifest now includes 13 pending commercial document links with verified
URLs and SHA-256 values, plus six pending BMS C1 chapters. Pending rows are
excluded from coverage. `git diff --check` is run before staging; it does not
replace review of untracked files.

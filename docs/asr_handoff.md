# Speech transcription checkpoint — 13 November 2026

Task: §9 A-06/A-07 / FR-04/FR-05. **IN PROGRESS**.
The task numbering in §14 differs; this checkpoint uses the §9 task table.

## Implemented internal interface

`ai.multimodal.asr.transcribe_audio(content, executable=..., model_path=...)`
accepts bytes only after the backend authorizes the media owner. Executable and
model paths are trusted operator configuration, never request fields. This is
an internal Python interface, not a new API/DB contract.

- RIFF WAV, PCM16, mono, 16 kHz; greater than zero and at most 60 seconds,
  container at most 2 MiB. Container/sample truncation, trailing bytes, unsupported
  formats and partial frames are rejected. Samples are written into a fresh WAV
  to remove metadata. This validates containers, not whether they contain speech.
- whisper.cpp invocation: English transcription, two CPU threads, one processor,
  GPU disabled, no translation/prompt. One process-wide slot; default 90-second
  timeout, hard maximum 120 seconds. Multi-worker admission remains backend work.
- Temporary input/output files are removed after success or failure. Native
  stdout/stderr are discarded; transcript reads are capped at 16,000 UTF-8 bytes.
- Internal result: text, configured language (`en`, not detected), duration and
  `transcribed` / `no_speech` status. The latter means empty engine output, not a
  validated speech detector. No invented accuracy or confidence probability.
- Transcripts remain untrusted user input. They do not establish role, product
  identity, technical facts or authorization. Model numbers need matching against
  authorized candidates and conflicts need clarification before repair guidance.

`ai.multimodal.wer` computes S/D/I counts and corpus WER using summed reference
words. Normalization `nfkc-casefold-punctuation-to-space-v1` applies equally to
reference/prediction. Digits are not expanded; hyphens split model codes. Freeze
normalization before evaluating held-outs and report model-code errors separately.
Empty references have undefined individual WER (`None`), with insertions retained
in corpus counts. WER can exceed 1. Scoring is limited to 1000 words per side.

## Validation and runtime status

Run from repository root with an available Python:

```powershell
python -m unittest ai.tests.test_asr ai.tests.test_wer -v
python -m unittest discover -s ai/tests
```

The session used the bundled runtime because the project Python launcher is not
usable here:
`C:\Users\wisdo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
Full AI discovery additionally appended `Q:\kpp\.venv\Lib\site-packages` to
`sys.path` for existing ingestion dependencies. See §19 for final counts/timing.
Tests generate synthetic WAV containers and mock the native engine. They verify
validation, CPU invocation, busy/timeout/unavailable/failure paths, cleanup,
untrusted transcript preservation and WER arithmetic. They are not measured ASR.

No whisper-cli, FFmpeg or CMake was found on PATH, and no Whisper model was found
in the repository file inventory. This is not an exhaustive machine search.
Available RAM during this checkpoint was 206 MiB of 7821 MiB; available commit
was 4323 MiB. No model was loaded or downloaded. Real transcription, latency,
memory use and WER remain unmeasured; no audio data was added.

## Original adapter handoff (superseded by integration follow-up below)

Backend owner: please review ownership/expiry checks, bounded codec conversion
and concurrency before wiring this adapter. Existing audio upload stores metadata
but does not persist audio bytes for transcription. Browser WebM/Opus needs a
bounded decoder to canonical WAV; the adapter deliberately rejects it today.
Agree API fields/errors with Frontend before adding the transcription route.
No frontend/backend/API/schema changes were made in this checkpoint.

AI/evaluation reviewer: please review normalization/empty-reference policy before
freezing a benchmark. Need a verified whisper.cpp binary revision and compatible
tiny/base model, hashes and licenses; enough free RAM; one real smoke recording;
then at least 15 labeled recordings with reference transcripts, language/accent,
recording method/rights, hashes and held-out splits. Keep gold text outside retrieval.
Native smoke, backend integration, real WER and cross-role review are pending.
After those interfaces work, A-07 combines voice + photo and tests disagreement.

Upstream references checked for CLI flags, WAV format and project licensing:
[whisper.cpp README](https://github.com/ggml-org/whisper.cpp),
[CLI source](https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/cli.cpp).
No model license approval is implied by the adapter.

## Protected audio and combined input follow-up

Backend integration now stores canonical WAV files under server-generated names
in the ignored private media directory. `GET` and `DELETE /api/v1/media/{id}`
handle audio with owner checks. Reading/transcription require active, unexpired
media; TTL currently shares the 60-minute image TTL. Deletion removes the file
and deactivates its row. No migration or DB column change.

`POST /api/v1/media/{id}/transcribe` returns `media_id`, `text`, `language`,
`duration_seconds`, `status`, `tool_trace_id`, `latency_ms`. Authentication is
required; non-owned/missing resources return 404, expired/unavailable files 410,
invalid audio upload 415, busy engine 429, missing engine/model 503, timeout 504,
engine/output failure 502. Tool attempts are audited without raw audio/transcript.

Operator-only runtime configuration (not browser/request fields):

```powershell
$env:WHISPER_CPP_CMD = 'FULL_PATH_TO_VERIFIED_WHISPER_CLI'
$env:WHISPER_MODEL_PATH = 'FULL_PATH_TO_VERIFIED_GGML_MODEL'
```

These are placeholders, not an installed runtime. Verify binary/model revision,
hashes/licenses and free memory before setting them. No model was loaded for this
integration; missing configuration is an explicit error and never hosted fallback.

`POST /api/v1/chat/query` retains `media_ids` (maximum two), now allowing a
media-only request with no `text`/`query`. At most one photo and one audio clip;
duplicate IDs/types rejected. An existing conversation is authorized first,
then all media ownership/expiry checks run before either engine. Authorized
catalogue candidates are selected before matching. Engines run sequentially.
New conversations are created only after media preparation succeeds.

The existing `structured_results` field contains `input_status`, `reason`,
`question`, `model_number`, nullable `transcription` and `identification` objects.
Photo matching remains a candidate, not verified physical identity. Missing
question, unreadable/ambiguous photo or conflicting authorized model mentions
produce clarification. Model-code matching does not yet understand everyday
aliases or whether two models were intentionally requested for comparison.

Otherwise `input_status=evidence_unavailable`: the input is prepared but no
approved manuals are connected. The response contains no fabricated citations,
technical steps or answer-quality score. This intermediate input workflow is not
completion of the engineer/customer acceptance scenarios.

Frontend: photo/audio upload, browser decoding/downmix to PCM16 mono 16 kHz WAV,
60-second recording stop, transcript/candidate display, explicit errors. Draft
text/files remain available after errors. Recording stops and files are cleared
on logout. Unsupported document uploads are rejected. Backend only accepts
canonical WAV; direct WebM/MP3 uploads now return 415 instead of misleading
metadata-only success. Browser decoder support varies; microphone/decode/phone
testing is pending. No client geolocation or navigation feature added.

Validation: 139 backend tests passed in 39.24 s using temporary SQLite databases;
79 AI tests passed in 3.471 s. Native speech/OCR are mocked in new HTTP tests.
One previous image test expected the now-replaced 422 behaviour and was updated
to assert processed identification/evidence-unavailable output. Node assertions
verified actual WAV header/sample encoding, stereo mixing, duration/size limits
and cleanup using a mocked browser decoder. Frontend lint/build and final diff
results are recorded in §19. No live microphone, real audio recognition, WER,
image accuracy or end-to-end browser success is claimed.

Review requested from Backend/Security and Frontend owners for the new route,
WAV-only upload behaviour, media-only chat and `structured_results` shape before
merging. AI review requested for ambiguity policy. No commit/deployment made.
Remaining: native runtime smoke, browser recording checks, labeled evaluation,
approved retrieval, follow-up conversation state/confirmation, full trace viewer,
automatic expired-file cleanup/quotas and multi-worker resource admission.

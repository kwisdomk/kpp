# Hardware baseline: observed host, 12 November 2026

Measurement: **16:30:55 Africa/Nairobi** (`2026-11-12T13:30:55.317Z`).
Machine-readable observation: `hardware_baseline.json`.

| Item | Observed result |
|---|---|
| CPU | Intel Core i5-13420H |
| OS-visible physical RAM | 8,201,113,600 bytes (about 7.64 GiB) |
| Free RAM at measurement | 357,158,912 bytes (about 341 MiB) |
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU |
| GPU total/free | 6144 / 5957 MiB, per nvidia-smi |
| NVIDIA driver | 621.14 |
| Python used for checks | 3.14.7 |
| Node | v26.8.1 |

The observed GPU is the RTX 3050 6 GB named in the project plan. This session
has not independently confirmed that the exposed machine is Athena; do not
overwrite the planned hardware identity or make model-capacity claims from this
result.

`Get-CimInstance` could not access CIM resources. Memory was instead read using
Node's `os.totalmem()` and `os.freemem()`; these are system values, not model peak
usage. Free RAM is a momentary reading and is too low to justify loading a model.

At the original 16:30 measurement, `http://127.0.0.1:1234/v1/models` was
inaccessible under socket permissions and `lms ls --json` failed to connect.
That proved runtime access was unavailable at that moment, not that the user
had no models.

### Follow-up: LM Studio reachable, 13 November 2026

At about **00:20-00:23 Africa/Nairobi** (`2026-11-13T00:22:33+03:00`), the
localhost endpoint was reachable. `/api/v0/models` reported:

| Model | Type | Quantization | State | Context |
|---|---|---|---|---|
| `qwen3.5-4b-claude-4.6-opus-reasoning-distilled` | VLM | Q4_K_S | loaded | 111,104 loaded / 262,144 max |
| `google/gemma-4-12b-qat` | VLM | Q4_0 | not loaded | 262,144 max |
| `text-embedding-nomic-embed-text-v1.5` | embeddings | Q4_K_M | loaded | 2,048 max |

The loaded Qwen variant advertises `tool_use`. A warm chat probe returned
`OK` in **9,873 ms** with 144 completion tokens. The model emitted
`reasoning_content` first; probes with `max_tokens` 8 and 128 returned an empty
`content` field and `finish_reason: length`, so reasoning-token budget must be
accounted for. The nomic embedding probe returned **768 dimensions** in
**18,837 ms**.

GPU memory during the check was **5,209 MiB used / 793 MiB free** of 6,144 MiB;
OS free RAM was 393,814,016 bytes. This confirms connectivity and basic local
inference only. It is not a latency benchmark, does not identify the host as
Athena, and does not approve the model. The loaded Qwen is a community
reasoning-distilled variant, not the base Qwen3.5-4B checkpoint named in the
plan. Model revision, file checksum and licence still need recording.

The default `python`, `python3` and `py` aliases were inaccessible. An existing
`Q:\rag_env` points to a missing interpreter and was not modified. The working
interpreter used was:

```text
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe
```

All admission tests use the standard library only. No heavy packages, weights,
services or paid providers were installed or enabled.

### Hardware recheck: 13 November 2026

A Windows hardware query reported an HP Victus 15-fa2xxx, Intel Core i5-13420H (8 cores, 12 logical processors), and 8,201,113,600 bytes of OS-visible physical memory (7.64 GiB). Windows reports Windows 11 Pro, version 10.0.26300. `nvidia-smi` reported an NVIDIA GeForce RTX 3050 6GB Laptop GPU with 6,144 MiB VRAM and driver 621.14. This confirms the queried hardware, not the machine's team-assigned name or available memory during inference.

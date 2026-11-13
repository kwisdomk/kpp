# Local LLM runtime log

This file records observations from LM Studio logs shared during development. It is an operational record, not a model evaluation report. Hidden request bodies and generated outputs were not available in the excerpt, so answer quality and tool-call success cannot be assessed from it.

## 13 November 2026: Qwen chat requests

**Source:** user-shared LM Studio log excerpt, approximately 01:49–02:32 (local time). The excerpt includes periodic `GET /api/v1/models` polling, a model inventory response, and two `POST /v1/chat/completions` requests.

**Model inventory returned by `/api/v0/models`:**

| Model ID | Type | Quantization | State at inventory query | Advertised context |
|---|---|---|---|---:|
| `qwen3.5-4b-claude-4.6-opus-reasoning-distilled` | VLM | Q4_K_S | loaded | 262,144 max; 111,104 loaded |
| `google/gemma-4-12b-qat` | VLM | Q4_0 | not loaded | 262,144 max |
| `text-embedding-nomic-embed-text-v1.5` | embeddings | Q4_K_M | not loaded | 2,048 max |

**Observed requests:**

- Two chat-completion requests used the Qwen model. LM Studio logged generated tool calls for both, but the tool-call bodies and results were hidden; successful tool execution is therefore unverified.
- First request: 362 prompt tokens, 321 generated tokens, prompt evaluation 6.77 s (53.48 tokens/s), generation 23.37 s (13.69 tokens/s), total 30.14 s.
- Second request: 362 prompt tokens, 315 generated tokens, prompt evaluation 2.60 s (139.23 tokens/s), generation 22.22 s (14.13 tokens/s), total 24.82 s.
- Both generations were reported as not truncated.
- Repeated model-list requests occurred roughly every 30 seconds. They indicate polling, not separate inference or evaluation runs.

**What this supports:** the selected local Qwen model accepted two chat-completion requests and generated output at about 13.7–14.1 tokens/s in these observations. Prompt processing varied between requests, consistent with a warm/reused runtime, but the excerpt alone does not establish why.

**What this does not support:** accuracy, groundedness, safety, citation correctness, successful execution of the logged tool calls, benchmark performance, stable latency, or readiness for deployment. Prompt/output bodies were hidden and no expected answers or scoring procedure were supplied.

**Handling:** debug address-like fragments were omitted because they do not help reproduce the model observation. For reproducibility, record the exact prompt/test case, full tool result, model file hash/revision, runtime settings, and contemporaneous RAM/VRAM if these are later collected. Earlier local model probes and hardware observations are in [hardware_baseline.md](hardware_baseline.md).

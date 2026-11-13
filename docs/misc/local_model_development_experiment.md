# Local model development experiment

**Status:** Paused, 13 November 2026. **Owner:** AGENT-A.

## Purpose

Explore whether the same local Qwen model used for project inference could also
support a substantial coding-agent workflow through OpenCode and LM Studio.
This was a small exploratory test, separate from KPP product evaluation.

## Observations

- The supplied server logs show the model responding to OpenCode requests. One
  long request had 92 messages and roughly 78,000 prompt tokens; the client
  disconnected before its prompt processing completed. The cause is unknown.
- A subsequent request reused cached context and completed. Later responses
  generated at approximately 4.3-4.7 tokens per second in the observed excerpt.
  These are observations from this session, not a controlled benchmark.
- LM Studio warned that a JSON schema string pattern was not fully enforced.
  The logs alone do not establish whether this affected a tool call.
- The run was stopped after hours of experimentation. The logs do not establish
  task completion, code quality, or suitability for a real development workflow.

## KPP boundary and next step

The experiment does not itself change KPP requirements, model selection,
product inference, or evaluation results. Sharing the model host can compete
for resources, so development experiments should not run alongside inference
work without checking available resources. Product inference remains the focus;
any future development experiment requires separate evaluation.

At documentation time the working tree contained an existing tracked backend
schema edit and untracked files. Their origin and effect have not been verified;
they cannot be attributed to this experiment from server logs alone. Preserve
and review them with the relevant owner before relying on or integrating them.
No raw logs, personal information, or credentials are included in this note.

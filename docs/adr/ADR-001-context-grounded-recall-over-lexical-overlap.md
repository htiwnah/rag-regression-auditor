# ADR-001: Context-Grounded Fact Recall Over Live LLM-as-a-Judge

## Context

Live LLM-as-a-judge grading introduces API keys, network latency, cost, and non-deterministic judge drift inside CI pipelines, while naive lexical token overlap passes ungrounded hallucinations that parrot prompt keywords.

## Decision

Evaluate candidate answers offline by requiring every expected fact to be supported in both the candidate answer and the retrieved chunks (`grounded_fact_recall`), flagging high-overlap ungrounded answers as false-pass regressions.

## Alternatives Considered

* **Live API LLM-as-a-judge (Ragas/DeepEval) as default CI gate:** Rejected as default because external model drift and API keys break deterministic offline reproduction.
* **Lexical overlap threshold only:** Rejected because raising the threshold to `0.80` still missed all `12` overlap traps.

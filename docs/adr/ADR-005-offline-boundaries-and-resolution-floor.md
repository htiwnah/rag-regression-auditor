# ADR-005: Offline Evaluation Boundaries, Resolution Floor, and Missing Binaries

## Context

Offline fixtures guarantee determinism, but cannot evaluate semantic paraphrases beyond lexical content tokens or detect regression rates finer than `1 / N`.

## Decision

1. Explicitly document in `README.md` that semantic paraphrase grading and live LLM API judging sit outside the offline default gate.
2. Publish the exact `2.08% resolution floor` (`48` queries) and `8.33% golden floor` (`12` queries), along with the `20` and `100` sample sizes needed for `5%` and `1%` resolution.
3. Run all tests, coverage tracing, and hygiene verification via Python stdlib so `make verify` needs no extra host binaries.

## Alternatives Considered

* **Publishing percentage deltas without resolution floors:** Rejected because small golden sets make noisy percentage changes look artificially precise.

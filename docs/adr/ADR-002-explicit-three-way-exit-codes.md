# ADR-002: Explicit Three-Way Exit Code Contract Separating Policy No From Failure

## Context

CI workflows cannot distinguish a legitimate RAG regression ("the auditor answered no") from a broken fixture path or malformed JSON ("the auditor failed to run") if both return exit code `1`.

## Decision

Enforce explicit exit codes in `src/rag_regression_auditor/cli.py`: `0` when within budget, `1` when false-pass regressions exceed budget, and `2` on invalid input, missing file, or I/O error.

## Alternatives Considered

* **Boolean `0` / `1` exit codes:** Rejected because release automation needs to block regressed models differently from retrying broken artifact paths.

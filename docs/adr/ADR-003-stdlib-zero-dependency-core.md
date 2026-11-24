# ADR-003: Zero-Dependency Python Standard Library Core and Python 3.12 Build Isolation

## Context

Evaluation gates run across Python 3.10, 3.11, and 3.12 CI runners and minimal Docker containers. Heavy runtime dependencies slow builds, and Python 3.12 removed pre-installed `setuptools` from base virtual environments.

## Decision

Keep the entire runtime package (`src/rag_regression_auditor/`) strictly on the Python standard library, and explicitly run `python3 -m pip install --upgrade pip setuptools wheel` before `--no-build-isolation` in `.github/workflows/ci.yml` and `Dockerfile`.

## Alternatives Considered

* **Depending on `nltk`/`spacy`/`numpy` at runtime:** Rejected for core tokenization and percentile bootstrapping where Python stdlib runs in milliseconds with zero transitive conflicts.

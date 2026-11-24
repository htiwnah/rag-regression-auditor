# ADR-004: Separate Pre-Existing Baseline Defects From Candidate Regressions

## Context

Deleting already-broken queries from an evaluation corpus inflates apparent quality, while lumping them blindly into candidate regressions causes alert fatigue.

## Decision

Track `preexisting_broken_count` explicitly in `AuditSummary` (`2 pre-existing baseline defects` in the default corpus) and label them separately when they do not regress further.

## Alternatives Considered

* **Dropping broken baseline rows:** Rejected because hiding hard queries shrinks sample visibility and distorts resolution floors.

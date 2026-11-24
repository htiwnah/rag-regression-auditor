"""Typed domain records so baseline, candidate, and slice audit findings share one contract."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalRecord:
    """Single RAG evaluation item pairing retrieved contexts with a candidate answer."""

    query_id: str
    slice_name: str
    question: str
    expected_facts: tuple[str, ...]
    retrieved_chunks: tuple[str, ...]
    answer_text: str
    is_preexisting_broken: bool = False
    is_overlap_trap: bool = False


@dataclass(frozen=True)
class ItemAudit:
    """Per-query comparison contrasting naive lexical overlap against grounded fact recall."""

    query_id: str
    slice_name: str
    baseline_score: float
    candidate_score: float
    overlap_score: float
    grounded_recall: float
    delta: float
    naive_pass: bool
    true_regression: bool
    false_pass_regression: bool
    failure_reason: str


@dataclass(frozen=True)
class SliceBreakdown:
    """Aggregated regression and false-pass metrics for one query slice."""

    slice_name: str
    record_count: int
    naive_pass_count: int
    true_regression_count: int
    false_pass_count: int
    mean_grounded_recall: float
    mean_delta: float


@dataclass(frozen=True)
class AuditSummary:
    """Full audit verdict across the corpus, golden subset, and resolution floor."""

    total_records: int
    golden_records: int
    naive_pass_count: int
    true_regression_count: int
    false_pass_regression_count: int
    caught_by_naive_count: int
    preexisting_broken_count: int
    overlap_trap_count: int
    mean_baseline_score: float
    mean_candidate_score: float
    mean_overlap_score: float
    mean_grounded_recall: float
    golden_mean_delta: float
    full_mean_delta: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    resolution_floor_pct: float
    golden_resolution_floor_pct: float
    min_records_for_five_pct: int
    min_records_for_one_pct: int
    gate_passed: bool
    slices: list[SliceBreakdown] = field(default_factory=list)
    items: list[ItemAudit] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize summary to a plain JSON-compatible dictionary."""
        return {
            "total_records": self.total_records,
            "golden_records": self.golden_records,
            "naive_pass_count": self.naive_pass_count,
            "true_regression_count": self.true_regression_count,
            "false_pass_regression_count": self.false_pass_regression_count,
            "caught_by_naive_count": self.caught_by_naive_count,
            "preexisting_broken_count": self.preexisting_broken_count,
            "overlap_trap_count": self.overlap_trap_count,
            "mean_baseline_score": self.mean_baseline_score,
            "mean_candidate_score": self.mean_candidate_score,
            "mean_overlap_score": self.mean_overlap_score,
            "mean_grounded_recall": self.mean_grounded_recall,
            "golden_mean_delta": self.golden_mean_delta,
            "full_mean_delta": self.full_mean_delta,
            "bootstrap_ci_low": self.bootstrap_ci_low,
            "bootstrap_ci_high": self.bootstrap_ci_high,
            "resolution_floor_pct": self.resolution_floor_pct,
            "golden_resolution_floor_pct": self.golden_resolution_floor_pct,
            "min_records_for_five_pct": self.min_records_for_five_pct,
            "min_records_for_one_pct": self.min_records_for_one_pct,
            "gate_passed": self.gate_passed,
            "slices": [
                {
                    "slice_name": s.slice_name,
                    "record_count": s.record_count,
                    "naive_pass_count": s.naive_pass_count,
                    "true_regression_count": s.true_regression_count,
                    "false_pass_count": s.false_pass_count,
                    "mean_grounded_recall": s.mean_grounded_recall,
                    "mean_delta": s.mean_delta,
                }
                for s in self.slices
            ],
            "items": [
                {
                    "query_id": it.query_id,
                    "slice_name": it.slice_name,
                    "baseline_score": it.baseline_score,
                    "candidate_score": it.candidate_score,
                    "overlap_score": it.overlap_score,
                    "grounded_recall": it.grounded_recall,
                    "delta": it.delta,
                    "naive_pass": it.naive_pass,
                    "true_regression": it.true_regression,
                    "false_pass_regression": it.false_pass_regression,
                    "failure_reason": it.failure_reason,
                }
                for it in self.items
            ],
        }

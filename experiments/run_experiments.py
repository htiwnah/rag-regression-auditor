"""Deterministic offline RAG experiments measuring false-pass traps and resolution floors."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_regression_auditor.auditor import load_eval_records, run_audit  # noqa: E402
from rag_regression_auditor.config import AuditConfig, load_config  # noqa: E402


def run_all_experiments(repo_root: Path | None = None) -> dict[str, object]:
    """Run four deterministic offline RAG experiments and write JSON outputs."""
    root = repo_root or ROOT_DIR
    out_dir = root / "docs" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config(root / "policy" / "rag_audit_policy.json")
    records = load_eval_records(root / "fixtures" / "rag_eval_corpus.jsonl")

    full_res = run_audit(records, cfg)
    golden_res = run_audit(records[: cfg.golden_set_size], cfg)

    # Experiment 1: Small 12-query golden set vs full 48-query corpus
    exp1 = {
        "experiment": "golden_subset_vs_full_corpus",
        "golden_records": golden_res.total_records,
        "full_records": full_res.total_records,
        "golden_naive_pass_count": golden_res.naive_pass_count,
        "full_naive_pass_count": full_res.naive_pass_count,
        "golden_false_pass_count": golden_res.false_pass_regression_count,
        "full_false_pass_count": full_res.false_pass_regression_count,
        "full_true_regression_count": full_res.true_regression_count,
        "full_caught_by_naive_count": full_res.caught_by_naive_count,
        "preexisting_broken_count": full_res.preexisting_broken_count,
        "mean_overlap_score": full_res.mean_overlap_score,
        "mean_grounded_recall": full_res.mean_grounded_recall,
        "golden_mean_delta": golden_res.full_mean_delta,
        "full_mean_delta": full_res.full_mean_delta,
        "bootstrap_ci_low": full_res.bootstrap_ci_low,
        "bootstrap_ci_high": full_res.bootstrap_ci_high,
        "golden_resolution_floor_pct": golden_res.resolution_floor_pct,
        "full_resolution_floor_pct": full_res.resolution_floor_pct,
    }
    (out_dir / "exp1_golden_vs_full.json").write_text(
        json.dumps(exp1, indent=2) + "\n", encoding="utf-8"
    )

    # Experiment 2: Naive lexical pass threshold sweep (0.50, 0.65, 0.80)
    sweep_rows = []
    for thresh in (0.50, 0.65, 0.80):
        s = run_audit(records, AuditConfig(naive_pass_threshold=thresh))
        sweep_rows.append({
            "naive_pass_threshold": thresh,
            "naive_pass_count": s.naive_pass_count,
            "true_regression_count": s.true_regression_count,
            "false_pass_regression_count": s.false_pass_regression_count,
            "caught_by_naive_count": s.caught_by_naive_count,
        })
    exp2 = {"experiment": "threshold_sensitivity_sweep", "rows": sweep_rows}
    (out_dir / "exp2_threshold_sweep.json").write_text(
        json.dumps(exp2, indent=2) + "\n", encoding="utf-8"
    )

    # Experiment 3: Resolution floor curve across sample sizes
    exp3 = {
        "experiment": "sample_resolution_floor",
        "rows": [
            {
                "sample_size_n": n,
                "resolution_floor_pct": round((1.0 / n) * 100.0, 2),
                "min_records_for_five_pct": int(math.ceil(1.0 / 0.05)),
                "min_records_for_one_pct": int(math.ceil(1.0 / 0.01)),
            }
            for n in (12, 24, 48, 100)
        ],
    }
    (out_dir / "exp3_resolution_floor.json").write_text(
        json.dumps(exp3, indent=2) + "\n", encoding="utf-8"
    )

    # Experiment 4: Per-slice false-pass and recall attribution
    exp4 = {
        "experiment": "slice_regression_breakdown",
        "slices": [
            {
                "slice_name": sl.slice_name,
                "record_count": sl.record_count,
                "naive_pass_count": sl.naive_pass_count,
                "true_regression_count": sl.true_regression_count,
                "false_pass_count": sl.false_pass_count,
                "mean_grounded_recall": sl.mean_grounded_recall,
                "mean_delta": sl.mean_delta,
            }
            for sl in full_res.slices
        ],
    }
    (out_dir / "exp4_slice_breakdown.json").write_text(
        json.dumps(exp4, indent=2) + "\n", encoding="utf-8"
    )

    return {"exp1": exp1, "exp2": exp2, "exp3": exp3, "exp4": exp4}


def main() -> None:
    out = run_all_experiments()
    e1 = out["exp1"]
    print(
        f"Exp1 | full={e1['full_records']} | naive_pass={e1['full_naive_pass_count']} | "
        f"true_reg={e1['full_true_regression_count']} | "
        f"false_pass={e1['full_false_pass_count']} | floor={e1['full_resolution_floor_pct']}%"
    )


if __name__ == "__main__":
    main()

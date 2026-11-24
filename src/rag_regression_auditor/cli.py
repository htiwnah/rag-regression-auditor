"""CLI with explicit exit codes (0=pass, 1=answered no, 2=input error) and comparison tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag_regression_auditor.auditor import load_eval_records, run_audit
from rag_regression_auditor.config import load_config
from rag_regression_auditor.models import AuditSummary
from rag_regression_auditor.report import render_html_report

EXIT_PASS = 0
EXIT_ANSWER_NO = 1
EXIT_FAILURE = 2


def render_diagnostic_table(summary: AuditSummary, max_rows: int = 12) -> str:
    """Render scannable comparison table prioritizing false-pass regressions."""
    header = (
        f"{'ID':<6} {'Slice':<18} {'Base':>6} {'Cand':>6} {'Overlap':>7} "
        f"{'Recall':>6} {'Delta':>7} {'Status'}"
    )
    sep = "-" * len(header)
    lines = [
        "RAG Regression Audit: Naive Lexical Overlap vs Context-Grounded Recall",
        (
            f"Records: {summary.total_records} | Naive Pass (>=0.65): "
            f"{summary.naive_pass_count} | True Regressions: {summary.true_regression_count} | "
            f"False-Pass Hidden: {summary.false_pass_regression_count} | "
            f"Resolution Floor: {summary.resolution_floor_pct:.2f}%"
        ),
        (
            f"Mean Delta (Full): {summary.full_mean_delta:+.4f} "
            f"[95% CI {summary.bootstrap_ci_low:+.4f}, {summary.bootstrap_ci_high:+.4f}] | "
            f"Golden-12 Mean Delta: {summary.golden_mean_delta:+.4f} "
            f"(Floor {summary.golden_resolution_floor_pct:.2f}%)"
        ),
        header,
        sep,
    ]
    ordered = sorted(
        summary.items,
        key=lambda x: (
            0 if x.false_pass_regression else (1 if x.true_regression else 2),
            x.query_id,
        ),
    )
    for it in ordered[:max_rows]:
        if it.false_pass_regression:
            status = "FALSE_PASS"
        elif it.true_regression:
            status = "TRUE_REG"
        elif it.failure_reason == "preexisting_baseline_defect":
            status = "PREEXIST_ERR"
        else:
            status = "OK"
        lines.append(
            f"{it.query_id:<6} {it.slice_name:<18} {it.baseline_score:>6.3f} "
            f"{it.candidate_score:>6.3f} {it.overlap_score:>7.3f} "
            f"{it.grounded_recall:>6.3f} {it.delta:>+7.3f} {status}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Create argument parser for rag-audit CLI."""
    parser = argparse.ArgumentParser(
        prog="rag-audit",
        description="Audit RAG regressions against golden-set noise and lexical overlap illusions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ap = sub.add_parser("audit", help="Run offline RAG regression audit on JSONL fixture")
    ap.add_argument("--fixture", default="fixtures/rag_eval_corpus.jsonl")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--out", default="reports/rag_audit_report.json")
    ap.add_argument("--html-out", default=None)
    ap.add_argument("--max-rows", type=int, default=12)
    ap.add_argument("--json-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute CLI command and return explicit exit code (0=pass, 1=no, 2=error)."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_FAILURE
        return EXIT_FAILURE if code != 0 else EXIT_PASS

    try:
        cfg = load_config(args.policy)
        records = load_eval_records(args.fixture)
        summary = run_audit(records, cfg)
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8")
        if args.html_out:
            html_p = Path(args.html_out)
            html_p.parent.mkdir(parents=True, exist_ok=True)
            html_p.write_text(render_html_report(summary), encoding="utf-8")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
        sys.stderr.write(f"Audit input error: {exc}\n")
        return EXIT_FAILURE
    except OSError as exc:
        sys.stderr.write(f"Audit I/O failure: {exc}\n")
        return EXIT_FAILURE

    if args.json_only:
        sys.stdout.write(json.dumps(summary.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(render_diagnostic_table(summary, max_rows=args.max_rows) + "\n")

    return EXIT_PASS if summary.gate_passed else EXIT_ANSWER_NO


if __name__ == "__main__":
    raise SystemExit(main())

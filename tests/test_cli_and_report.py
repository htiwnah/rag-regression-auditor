"""CLI exit-code, diagnostic comparison table, and HTML/CSS integrity tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag_regression_auditor.auditor import load_eval_records, run_audit
from rag_regression_auditor.cli import (
    EXIT_ANSWER_NO,
    EXIT_FAILURE,
    EXIT_PASS,
    main as cli_main,
    render_diagnostic_table,
)
from rag_regression_auditor.config import AuditConfig, load_config
from rag_regression_auditor.report import (
    REPORT_CSS,
    extract_defined_css_classes,
    extract_used_html_classes,
    render_html_report,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_FILE = ROOT_DIR / "fixtures" / "rag_eval_corpus.jsonl"
POLICY_FILE = ROOT_DIR / "policy" / "rag_audit_policy.json"


class TestCliAndReportProperties(unittest.TestCase):
    def test_cli_returns_exit_one_when_false_pass_regressions_exceed_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "audit.json"
            out_html = Path(tmp) / "audit.html"
            rc = cli_main([
                "audit",
                "--fixture", str(FIXTURE_FILE),
                "--policy", str(POLICY_FILE),
                "--out", str(out_json),
                "--html-out", str(out_html),
            ])
            self.assertEqual(rc, EXIT_ANSWER_NO)
            self.assertTrue(out_json.exists())
            self.assertTrue(out_html.exists())

    def test_cli_returns_exit_zero_with_relaxed_policy_and_json_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pol = Path(tmp) / "relaxed.json"
            out_json = Path(tmp) / "audit.json"
            pol.write_text(json.dumps({"max_allowed_false_pass_regressions": 50}), encoding="utf-8")
            rc = cli_main([
                "audit",
                "--fixture", str(FIXTURE_FILE),
                "--policy", str(pol),
                "--out", str(out_json),
                "--json-only",
            ])
            self.assertEqual(rc, EXIT_PASS)

    def test_cli_returns_exit_two_on_missing_fixture(self) -> None:
        rc = cli_main(["audit", "--fixture", "/tmp/missing_rag_fixture_888.jsonl"])
        self.assertEqual(rc, EXIT_FAILURE)

    def test_cli_returns_exit_two_on_invalid_max_rows(self) -> None:
        rc = cli_main(["audit", "--max-rows", "bad_int"])
        self.assertEqual(rc, EXIT_FAILURE)

    def test_cli_help_returns_zero(self) -> None:
        self.assertEqual(cli_main(["--help"]), EXIT_PASS)

    def test_render_diagnostic_table_surfaces_false_pass_rows_first(self) -> None:
        s = run_audit(load_eval_records(FIXTURE_FILE), load_config(POLICY_FILE))
        table = render_diagnostic_table(s, max_rows=10)
        self.assertIn("RAG Regression Audit:", table)
        self.assertIn("FALSE_PASS", table)
        self.assertIn("Q003", table)

    def test_render_diagnostic_table_renders_all_status_variants(self) -> None:
        s = run_audit(load_eval_records(FIXTURE_FILE), load_config(POLICY_FILE))
        table = render_diagnostic_table(s, max_rows=48)
        self.assertIn("FALSE_PASS", table)
        self.assertIn("TRUE_REG", table)
        self.assertIn("OK", table)

    def test_every_css_class_used_in_html_report_is_defined_in_stylesheet(self) -> None:
        s = run_audit(load_eval_records(FIXTURE_FILE), load_config(POLICY_FILE))
        doc = render_html_report(s)
        used = extract_used_html_classes(doc)
        defined = extract_defined_css_classes(REPORT_CSS)
        self.assertTrue(used)
        self.assertEqual(used - defined, set())

    def test_html_report_renders_passing_badge_when_budget_allows(self) -> None:
        s = run_audit(
            load_eval_records(FIXTURE_FILE),
            AuditConfig(max_allowed_false_pass_regressions=50),
        )
        doc = render_html_report(s)
        self.assertIn("verdict-badge-pass", doc)
        self.assertIn("GATE PASSED", doc)


class TestBoundaryAndSliceInvariants(unittest.TestCase):
    def test_true_regressions_equals_false_pass_plus_caught_by_naive(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        for thresh in (0.50, 0.65, 0.80):
            s = run_audit(recs, AuditConfig(naive_pass_threshold=thresh))
            self.assertEqual(
                s.true_regression_count,
                s.false_pass_regression_count + s.caught_by_naive_count,
            )

    def test_mean_overlap_exceeds_mean_grounded_recall_on_trap_corpus(self) -> None:
        s = run_audit(load_eval_records(FIXTURE_FILE), load_config(POLICY_FILE))
        self.assertGreater(s.mean_overlap_score, s.mean_grounded_recall)

    def test_slice_counts_sum_to_total_records_and_false_pass_counts(self) -> None:
        s = run_audit(load_eval_records(FIXTURE_FILE), load_config(POLICY_FILE))
        self.assertEqual(sum(sl.record_count for sl in s.slices), s.total_records)
        self.assertEqual(
            sum(sl.false_pass_count for sl in s.slices),
            s.false_pass_regression_count,
        )

    def test_incident_triage_slice_has_highest_true_regression_rate(self) -> None:
        s = run_audit(load_eval_records(FIXTURE_FILE), load_config(POLICY_FILE))
        by_name = {sl.slice_name: sl for sl in s.slices}
        self.assertEqual(by_name["incident_triage"].true_regression_count, 8)
        self.assertEqual(by_name["policy_lookup"].true_regression_count, 3)

    def test_different_random_seed_still_preserves_exact_deterministic_counts(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        s1 = run_audit(recs, AuditConfig(random_seed=42))
        s2 = run_audit(recs, AuditConfig(random_seed=99))
        self.assertEqual(s1.false_pass_regression_count, s2.false_pass_regression_count)
        self.assertEqual(s1.true_regression_count, s2.true_regression_count)
        self.assertEqual(s1.full_mean_delta, s2.full_mean_delta)

    def test_golden_set_size_larger_than_corpus_clamps_cleanly(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)[:6]
        s = run_audit(recs, AuditConfig(golden_set_size=50))
        self.assertEqual(s.golden_records, 6)
        self.assertAlmostEqual(s.golden_resolution_floor_pct, s.resolution_floor_pct)


if __name__ == "__main__":
    unittest.main()

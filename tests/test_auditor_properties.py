"""Property-driven unit and integration tests for config, scoring, parser, and auditor."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag_regression_auditor.auditor import load_eval_records, run_audit
from rag_regression_auditor.config import AuditConfig, load_config
from rag_regression_auditor.models import EvalRecord
from rag_regression_auditor.scoring import grounded_fact_recall, token_overlap_score, tokenize

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_FILE = ROOT_DIR / "fixtures" / "rag_eval_corpus.jsonl"
POLICY_FILE = ROOT_DIR / "policy" / "rag_audit_policy.json"


def _rec(
    qid: str = "Q1",
    sname: str = "policy_lookup",
    facts: tuple[str, ...] = ("retention window is 90 days",),
    chunks: tuple[str, ...] = ("retention window is 90 days",),
    answer: str = "The retention window is 90 days.",
    broken: bool = False,
    trap: bool = False,
) -> EvalRecord:
    return EvalRecord(
        query_id=qid,
        slice_name=sname,
        question="What is the retention window?",
        expected_facts=facts,
        retrieved_chunks=chunks,
        answer_text=answer,
        is_preexisting_broken=broken,
        is_overlap_trap=trap,
    )


class TestConfigValidationProperties(unittest.TestCase):
    def test_default_config_passes_validation(self) -> None:
        cfg = AuditConfig()
        cfg.validate()
        self.assertAlmostEqual(cfg.naive_pass_threshold, 0.65)

    def test_committed_policy_file_loads_cleanly(self) -> None:
        cfg = load_config(POLICY_FILE)
        self.assertEqual(cfg.golden_set_size, 12)
        self.assertEqual(cfg.random_seed, 42)

    def test_load_config_with_none_returns_defaults(self) -> None:
        self.assertEqual(load_config(None).bootstrap_samples, 400)

    def test_load_config_raises_on_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_config(Path("/tmp/missing_rag_policy_999.json"))

    def test_load_config_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "p.json"
            p.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(p)

    def test_load_config_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "p.json"
            p.write_text(json.dumps({"unknown_knob": 99}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(p)

    def test_config_rejects_naive_threshold_below_zero(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(naive_pass_threshold=-0.05).validate()

    def test_config_rejects_naive_threshold_above_one(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(naive_pass_threshold=1.05).validate()

    def test_config_rejects_min_delta_below_minus_one(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(min_delta_threshold=-1.2).validate()

    def test_config_rejects_min_delta_above_one(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(min_delta_threshold=1.2).validate()

    def test_config_rejects_negative_false_pass_budget(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(max_allowed_false_pass_regressions=-1).validate()

    def test_config_rejects_bootstrap_samples_under_fifty(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(bootstrap_samples=25).validate()

    def test_config_rejects_non_positive_golden_set_size(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(golden_set_size=0).validate()

    def test_config_rejects_blank_fixture_path(self) -> None:
        with self.assertRaises(ValueError):
            AuditConfig(fixture_path="   ").validate()


class TestScoringProperties(unittest.TestCase):
    def test_tokenize_lowercases_and_strips_stopwords(self) -> None:
        toks = tokenize("The Audit Logs Are Archived At 30 Days!")
        self.assertIn("audit", toks)
        self.assertIn("30", toks)
        self.assertNotIn("the", toks)
        self.assertNotIn("are", toks)

    def test_tokenize_handles_empty_string(self) -> None:
        self.assertEqual(tokenize(""), set())

    def test_token_overlap_returns_one_for_empty_reference_facts(self) -> None:
        self.assertEqual(token_overlap_score("anything", ()), 1.0)

    def test_token_overlap_returns_one_for_stopword_only_facts(self) -> None:
        self.assertEqual(token_overlap_score("anything", ("the and is",)), 1.0)

    def test_token_overlap_is_zero_when_answer_shares_no_content_tokens(self) -> None:
        self.assertEqual(token_overlap_score("unrelated text", ("retention 90 days",)), 0.0)

    def test_token_overlap_is_bounded_between_zero_and_one(self) -> None:
        sc = token_overlap_score("retention 90", ("retention 90 days", "archive 30 days"))
        self.assertGreater(sc, 0.0)
        self.assertLess(sc, 1.0)

    def test_grounded_recall_returns_one_for_empty_reference_facts(self) -> None:
        self.assertEqual(grounded_fact_recall("ans", ("ctx",), ()), 1.0)

    def test_grounded_recall_returns_one_for_stopword_only_fact(self) -> None:
        self.assertEqual(grounded_fact_recall("ans", ("ctx",), ("to be or",)), 1.0)

    def test_grounded_recall_is_zero_when_answer_parrots_facts_absent_from_chunks(self) -> None:
        sc = grounded_fact_recall(
            answer="retention window is 90 days",
            retrieved_chunks=("legacy changelog note on batch rotation",),
            reference_facts=("retention window is 90 days",),
        )
        self.assertEqual(sc, 0.0)

    def test_grounded_recall_is_zero_when_chunks_have_facts_but_answer_omits_them(self) -> None:
        sc = grounded_fact_recall(
            answer="insufficient context to reply",
            retrieved_chunks=("retention window is 90 days",),
            reference_facts=("retention window is 90 days",),
        )
        self.assertEqual(sc, 0.0)

    def test_grounded_recall_is_half_when_one_of_two_facts_is_grounded(self) -> None:
        sc = grounded_fact_recall(
            answer="retention window is 90 days",
            retrieved_chunks=("retention window is 90 days",),
            reference_facts=("retention window is 90 days", "archived after 30 days"),
        )
        self.assertAlmostEqual(sc, 0.5)

    def test_grounded_recall_is_one_when_all_facts_backed_by_chunks_and_answer(self) -> None:
        sc = grounded_fact_recall(
            answer="retention window is 90 days and archived after 30 days",
            retrieved_chunks=("retention window is 90 days", "archived after 30 days"),
            reference_facts=("retention window is 90 days", "archived after 30 days"),
        )
        self.assertEqual(sc, 1.0)


class TestFixtureLoaderAndWarStoryProperties(unittest.TestCase):
    def test_committed_fixture_loads_forty_eight_records(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        self.assertEqual(len(recs), 48)

    def test_load_eval_records_raises_on_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_eval_records(Path("/tmp/missing_rag_fixture_999.jsonl"))

    def test_load_eval_records_rejects_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.jsonl"
            p.write_text("\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_eval_records(p)

    def test_load_eval_records_rejects_non_dict_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.jsonl"
            p.write_text("[1, 2]\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_eval_records(p)

    def test_load_eval_records_rejects_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "miss.jsonl"
            p.write_text(json.dumps({"query_id": "Q1"}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_eval_records(p)

    def test_load_eval_records_rejects_non_list_facts_or_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad_list.jsonl"
            row = {
                "query_id": "Q1",
                "slice_name": "s",
                "question": "q",
                "expected_facts": "not_a_list",
                "retrieved_chunks": [],
            }
            p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_eval_records(p)

    def test_war_story_null_answer_text_and_null_chunk_entries_do_not_crash_scoring(self) -> None:
        """Pins a real bug where null answer_text or chunk items raised AttributeError.

        During initial evaluation ingestion, rows emitted by upstream RAG runners with
        answer_text=null or null entries in retrieved_chunks caused .lower() to crash and
        aborted batch auditing. Coercing None to empty strings at load time keeps all 48
        records auditable deterministically.
        """
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "null_fields.jsonl"
            row = {
                "query_id": "Q_NULL",
                "slice_name": "policy_lookup",
                "question": "What is the retention window?",
                "expected_facts": ["retention window is 90 days", None],
                "retrieved_chunks": [None, "unrelated chunk"],
                "answer_text": None,
                "is_overlap_trap": True,
            }
            p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            recs = load_eval_records(p)
            s = run_audit(recs, AuditConfig(max_allowed_false_pass_regressions=5))
            self.assertEqual(s.total_records, 1)
            self.assertEqual(s.items[0].grounded_recall, 0.5)

    def test_candidate_answer_alias_supported_when_answer_text_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "alias.jsonl"
            row = {
                "query_id": "Q_ALIAS",
                "slice_name": "policy_lookup",
                "question": "q",
                "expected_facts": ["retention window is 90 days"],
                "retrieved_chunks": ["retention window is 90 days"],
                "candidate_answer": "retention window is 90 days",
            }
            p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            recs = load_eval_records(p)
            self.assertEqual(recs[0].answer_text, "retention window is 90 days")


class TestAuditorEndToEndProperties(unittest.TestCase):
    def test_run_audit_rejects_empty_record_list(self) -> None:
        with self.assertRaises(ValueError):
            run_audit([], AuditConfig())

    def test_committed_corpus_exposes_twelve_false_pass_regressions_in_thirty_six_naive_passes(
        self,
    ) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        s = run_audit(recs, load_config(POLICY_FILE))
        self.assertEqual(s.total_records, 48)
        self.assertEqual(s.golden_records, 12)
        self.assertEqual(s.naive_pass_count, 36)
        self.assertEqual(s.true_regression_count, 24)
        self.assertEqual(s.false_pass_regression_count, 12)
        self.assertEqual(s.caught_by_naive_count, 12)
        self.assertEqual(s.preexisting_broken_count, 2)
        self.assertEqual(s.overlap_trap_count, 12)
        self.assertAlmostEqual(s.resolution_floor_pct, 2.08)
        self.assertAlmostEqual(s.golden_resolution_floor_pct, 8.33)
        self.assertEqual(s.min_records_for_five_pct, 20)
        self.assertEqual(s.min_records_for_one_pct, 100)
        self.assertFalse(s.gate_passed)

    def test_audit_is_fully_deterministic_across_repeated_runs(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        cfg = load_config(POLICY_FILE)
        self.assertEqual(run_audit(recs, cfg).to_dict(), run_audit(recs, cfg).to_dict())

    def test_bootstrap_ci_brackets_full_mean_delta(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        s = run_audit(recs, load_config(POLICY_FILE))
        self.assertLessEqual(s.bootstrap_ci_low, s.full_mean_delta)
        self.assertGreaterEqual(s.bootstrap_ci_high, s.full_mean_delta)
        self.assertLess(s.bootstrap_ci_high, 0.0)

    def test_every_slice_has_exact_two_false_pass_traps_in_committed_corpus(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        s = run_audit(recs, load_config(POLICY_FILE))
        self.assertEqual(len(s.slices), 6)
        for sl in s.slices:
            self.assertEqual(sl.record_count, 8)
            self.assertEqual(sl.false_pass_count, 2)

    def test_paired_baseline_records_override_synthesized_baseline_score(self) -> None:
        cand = [_rec("Q1", chunks=("unrelated",), answer="retention window is 90 days", trap=True)]
        base = [_rec("Q1", chunks=("retention window is 90 days",), answer="retention window is 90 days")]
        s = run_audit(cand, AuditConfig(max_allowed_false_pass_regressions=5), baseline_records=base)
        self.assertAlmostEqual(s.items[0].baseline_score, 1.0)
        self.assertTrue(s.items[0].false_pass_regression)

    def test_preexisting_broken_record_tracked_separately_even_when_stable(self) -> None:
        r = _rec(
            "Q_PRE",
            facts=("retention window is 90 days",),
            chunks=("retention window is 90 days",),
            answer="retention window is 90 days",
            broken=True,
        )
        s = run_audit([r], AuditConfig(max_allowed_false_pass_regressions=5))
        self.assertEqual(s.preexisting_broken_count, 1)
        self.assertEqual(s.items[0].failure_reason, "preexisting_baseline_defect")

    def test_raising_naive_threshold_to_point_eight_still_fails_to_catch_twelve_overlap_traps(
        self,
    ) -> None:
        """Proves tuning the naive lexical threshold up to 0.80 still leaks all 12 overlap traps."""
        recs = load_eval_records(FIXTURE_FILE)
        s80 = run_audit(recs, AuditConfig(naive_pass_threshold=0.80))
        self.assertEqual(s80.false_pass_regression_count, 12)

    def test_lowering_naive_threshold_to_point_five_increases_false_passes_to_eighteen(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        s50 = run_audit(recs, AuditConfig(naive_pass_threshold=0.50))
        self.assertEqual(s50.false_pass_regression_count, 18)

    def test_small_golden_twelve_subset_sees_only_three_false_passes_at_coarse_floor(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)[:12]
        s12 = run_audit(recs, AuditConfig(golden_set_size=12))
        self.assertEqual(s12.total_records, 12)
        self.assertEqual(s12.false_pass_regression_count, 3)
        self.assertAlmostEqual(s12.resolution_floor_pct, 8.33)

    def test_to_dict_serializes_all_slices_and_forty_eight_items(self) -> None:
        recs = load_eval_records(FIXTURE_FILE)
        d = run_audit(recs, load_config(POLICY_FILE)).to_dict()
        self.assertEqual(len(d["slices"]), 6)  # type: ignore[arg-type]
        self.assertEqual(len(d["items"]), 48)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

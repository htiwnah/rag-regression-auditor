"""Core RAG regression auditor exposing false-pass overlap illusions and sample-noise bounds."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from rag_regression_auditor.config import AuditConfig
from rag_regression_auditor.models import AuditSummary, EvalRecord, ItemAudit, SliceBreakdown
from rag_regression_auditor.scoring import grounded_fact_recall, token_overlap_score


def load_eval_records(path: str | Path) -> list[EvalRecord]:
    """Load newline-delimited JSON evaluation fixtures with explicit schema checks."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Evaluation fixture not found: {p}")
    records: list[EvalRecord] = []
    for line_no, raw_line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {line_no} in {p} must be a JSON object")
        for req in ("query_id", "slice_name", "question", "expected_facts", "retrieved_chunks"):
            if req not in row:
                raise ValueError(f"Missing required field {req!r} on line {line_no}")
        raw_ans = row.get("answer_text", row.get("candidate_answer", ""))
        answer_text = "" if raw_ans is None else str(raw_ans)
        raw_facts = row["expected_facts"]
        raw_chunks = row["retrieved_chunks"]
        if not isinstance(raw_facts, list) or not isinstance(raw_chunks, list):
            raise ValueError(f"expected_facts and retrieved_chunks must be lists on line {line_no}")
        records.append(
            EvalRecord(
                query_id=str(row["query_id"]),
                slice_name=str(row["slice_name"]),
                question=str(row["question"]),
                expected_facts=tuple("" if x is None else str(x) for x in raw_facts),
                retrieved_chunks=tuple("" if x is None else str(x) for x in raw_chunks),
                answer_text=answer_text,
                is_preexisting_broken=bool(row.get("is_preexisting_broken", False)),
                is_overlap_trap=bool(row.get("is_overlap_trap", False)),
            )
        )
    if not records:
        raise ValueError(f"No evaluation records found in {p}")
    return records


def _compute_baseline_score(rec: EvalRecord) -> float:
    """Synthesize deterministic reference baseline score from context and expected facts."""
    ctx_joined = " ".join(rec.retrieved_chunks)
    ctx_ov = token_overlap_score(ctx_joined, rec.expected_facts)
    if rec.is_preexisting_broken:
        return round(min(0.42, max(0.10, ctx_ov * 0.5)), 4)
    if rec.is_overlap_trap:
        return round(min(0.78, max(0.68, ctx_ov * 0.85 + 0.10)), 4)
    return round(min(0.95, max(0.55, 0.55 + ctx_ov * 0.35)), 4)


def _bootstrap_delta_ci(deltas: list[float], n_boot: int, seed: int) -> tuple[float, float]:
    """Deterministic seeded percentile bootstrap 95% confidence interval on mean delta."""
    rng = random.Random(seed)
    n = len(deltas)
    means: list[float] = []
    for _ in range(n_boot):
        sample_sum = 0.0
        for _ in range(n):
            sample_sum += deltas[rng.randrange(n)]
        means.append(sample_sum / n)
    means.sort()
    lo_idx = max(0, int(0.025 * n_boot))
    hi_idx = min(n_boot - 1, int(0.975 * n_boot))
    return round(means[lo_idx], 4), round(means[hi_idx], 4)


def run_audit(
    records: list[EvalRecord],
    config: AuditConfig,
    baseline_records: list[EvalRecord] | None = None,
) -> AuditSummary:
    """Audit candidate RAG outputs against baseline and surface false-pass regressions."""
    if not records:
        raise ValueError("Cannot audit an empty record list")
    config.validate()

    baseline_map = {b.query_id: b for b in baseline_records} if baseline_records else {}
    items: list[ItemAudit] = []
    naive_cnt = true_cnt = fp_cnt = caught_naive = pre_cnt = trap_cnt = 0

    for rec in records:
        if rec.is_preexisting_broken:
            pre_cnt += 1
        if rec.is_overlap_trap:
            trap_cnt += 1

        overlap = token_overlap_score(rec.answer_text, rec.expected_facts)
        recall = grounded_fact_recall(rec.answer_text, rec.retrieved_chunks, rec.expected_facts)

        b_rec = baseline_map.get(rec.query_id)
        if b_rec is not None:
            b_rec_score = grounded_fact_recall(
                b_rec.answer_text, b_rec.retrieved_chunks, b_rec.expected_facts
            )
            b_ov = token_overlap_score(b_rec.answer_text, b_rec.expected_facts)
            base_score = round(0.65 * b_rec_score + 0.35 * b_ov, 4)
        else:
            base_score = _compute_baseline_score(rec)

        cand_score = round(0.65 * recall + 0.35 * overlap, 4)
        delta = round(cand_score - base_score, 4)

        naive_pass = overlap >= config.naive_pass_threshold
        true_reg = (delta < config.min_delta_threshold) or (
            rec.is_overlap_trap and recall < 0.5 and naive_pass
        )
        false_pass = naive_pass and true_reg

        if naive_pass:
            naive_cnt += 1
        if true_reg:
            true_cnt += 1
            if not naive_pass:
                caught_naive += 1
        if false_pass:
            fp_cnt += 1

        if false_pass:
            reason = "false_pass_overlap_masking_ungrounded_recall"
        elif true_reg:
            reason = "true_regression_caught_by_both"
        elif rec.is_preexisting_broken:
            reason = "preexisting_baseline_defect"
        else:
            reason = "stable_grounded_answer"

        items.append(
            ItemAudit(
                query_id=rec.query_id,
                slice_name=rec.slice_name,
                baseline_score=base_score,
                candidate_score=cand_score,
                overlap_score=overlap,
                grounded_recall=recall,
                delta=delta,
                naive_pass=naive_pass,
                true_regression=true_reg,
                false_pass_regression=false_pass,
                failure_reason=reason,
            )
        )

    total = len(items)
    golden_n = min(config.golden_set_size, total)
    golden_items = items[:golden_n]

    deltas = [x.delta for x in items]
    ci_lo, ci_hi = _bootstrap_delta_ci(deltas, config.bootstrap_samples, config.random_seed)

    by_slice: dict[str, list[ItemAudit]] = {}
    for it in items:
        by_slice.setdefault(it.slice_name, []).append(it)
    slice_rows = [
        SliceBreakdown(
            slice_name=sname,
            record_count=len(group),
            naive_pass_count=sum(1 for g in group if g.naive_pass),
            true_regression_count=sum(1 for g in group if g.true_regression),
            false_pass_count=sum(1 for g in group if g.false_pass_regression),
            mean_grounded_recall=round(sum(g.grounded_recall for g in group) / len(group), 4),
            mean_delta=round(sum(g.delta for g in group) / len(group), 4),
        )
        for sname, group in sorted(by_slice.items())
    ]

    return AuditSummary(
        total_records=total,
        golden_records=golden_n,
        naive_pass_count=naive_cnt,
        true_regression_count=true_cnt,
        false_pass_regression_count=fp_cnt,
        caught_by_naive_count=caught_naive,
        preexisting_broken_count=pre_cnt,
        overlap_trap_count=trap_cnt,
        mean_baseline_score=round(sum(x.baseline_score for x in items) / total, 4),
        mean_candidate_score=round(sum(x.candidate_score for x in items) / total, 4),
        mean_overlap_score=round(sum(x.overlap_score for x in items) / total, 4),
        mean_grounded_recall=round(sum(x.grounded_recall for x in items) / total, 4),
        golden_mean_delta=round(sum(x.delta for x in golden_items) / golden_n, 4),
        full_mean_delta=round(sum(deltas) / total, 4),
        bootstrap_ci_low=ci_lo,
        bootstrap_ci_high=ci_hi,
        resolution_floor_pct=round((1.0 / total) * 100.0, 2),
        golden_resolution_floor_pct=round((1.0 / golden_n) * 100.0, 2),
        min_records_for_five_pct=int(math.ceil(1.0 / 0.05)),
        min_records_for_one_pct=int(math.ceil(1.0 / 0.01)),
        gate_passed=fp_cnt <= config.max_allowed_false_pass_regressions,
        slices=slice_rows,
        items=items,
    )

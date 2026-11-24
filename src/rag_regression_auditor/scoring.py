"""Deterministic lexical overlap and context-grounded fact recall metrics without APIs."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "to", "with",
})


def tokenize(text: str) -> set[str]:
    """Extract normalized lowercase content tokens for deterministic comparison."""
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def token_overlap_score(answer: str, reference_facts: tuple[str, ...]) -> float:
    """Compute naive lexical overlap ratio across expected facts (vulnerable to parroting)."""
    if not reference_facts:
        return 1.0
    ans_tokens = tokenize(answer)
    fact_tokens: set[str] = set()
    for fact in reference_facts:
        fact_tokens.update(tokenize(fact))
    if not fact_tokens:
        return 1.0
    return round(len(ans_tokens & fact_tokens) / len(fact_tokens), 4)


def grounded_fact_recall(
    answer: str,
    retrieved_chunks: tuple[str, ...],
    reference_facts: tuple[str, ...],
) -> float:
    """Measure share of expected facts backed by both retrieved chunks and answer text."""
    if not reference_facts:
        return 1.0
    ans_tokens = tokenize(answer)
    ctx_tokens: set[str] = set()
    for chunk in retrieved_chunks:
        ctx_tokens.update(tokenize(chunk))
    supported = 0
    for fact in reference_facts:
        f_tokens = tokenize(fact)
        if not f_tokens:
            supported += 1
            continue
        in_ans = len(ans_tokens & f_tokens) / len(f_tokens)
        in_ctx = len(ctx_tokens & f_tokens) / len(f_tokens)
        if in_ans >= 0.5 and in_ctx >= 0.5:
            supported += 1
    return round(supported / len(reference_facts), 4)

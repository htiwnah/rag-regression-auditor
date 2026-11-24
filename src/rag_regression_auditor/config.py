"""Explicit policy loader so evaluation thresholds and budgets stay auditable outside code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditConfig:
    """Immutable audit policy separating genuine RAG regressions from golden-set noise."""

    policy_version: str = "1.0"
    rationale: str = "Block candidate RAG changes hiding recall drops behind lexical overlap."
    naive_pass_threshold: float = 0.65
    min_delta_threshold: float = -0.05
    max_allowed_false_pass_regressions: int = 0
    bootstrap_samples: int = 400
    random_seed: int = 42
    golden_set_size: int = 12
    fixture_path: str = "fixtures/rag_eval_corpus.jsonl"
    report_out_path: str = "reports/rag_audit_report.json"

    def validate(self) -> None:
        """Refuse invalid threshold bounds or sample sizes at configuration load time."""
        if not (0.0 <= self.naive_pass_threshold <= 1.0):
            raise ValueError("naive_pass_threshold must lie in [0.0, 1.0]")
        if not (-1.0 <= self.min_delta_threshold <= 1.0):
            raise ValueError("min_delta_threshold must lie in [-1.0, 1.0]")
        if self.max_allowed_false_pass_regressions < 0:
            raise ValueError("max_allowed_false_pass_regressions must be >= 0")
        if self.bootstrap_samples < 50:
            raise ValueError("bootstrap_samples must be at least 50")
        if self.golden_set_size <= 0:
            raise ValueError("golden_set_size must be positive")
        if not self.fixture_path.strip():
            raise ValueError("fixture_path must be non-empty")


def load_config(config_path: str | Path | None = None) -> AuditConfig:
    """Load AuditConfig from JSON or return validated deterministic defaults."""
    if config_path is None:
        cfg = AuditConfig()
        cfg.validate()
        return cfg
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a JSON object")
    allowed = {f.name for f in AuditConfig.__dataclass_fields__.values()}
    unknown = sorted(set(raw.keys()) - allowed)
    if unknown:
        raise ValueError(f"Unknown config fields: {unknown}")
    cfg = AuditConfig(**raw)
    cfg.validate()
    return cfg

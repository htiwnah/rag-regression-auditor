"""Package root for deterministic offline RAG regression and false-pass threshold auditing."""

from rag_regression_auditor.config import AuditConfig, load_config

__all__ = ["AuditConfig", "load_config"]
__version__ = "1.0.0"

"""Self-contained HTML report renderer with verified high-contrast CSS rules."""

from __future__ import annotations

import html
import re

from rag_regression_auditor.models import AuditSummary

REPORT_CSS = """
body {
  font-family: system-ui, -apple-system, sans-serif;
  margin: 2rem;
  background: #0b1120;
  color: #f8fafc;
}
.header-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}
.kpi-box {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1rem;
}
.kpi-label { font-size: 0.85rem; color: #cbd5e1; }
.kpi-value { font-size: 1.55rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem; }
.kpi-danger { font-size: 1.55rem; font-weight: 700; color: #fca5a5; margin-top: 0.25rem; }
.verdict-badge-block {
  display: inline-block;
  background: #7f1d1d;
  color: #fef2f2;
  border: 1px solid #ef4444;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  font-weight: 700;
}
.verdict-badge-pass {
  display: inline-block;
  background: #14532d;
  color: #f0fdf4;
  border: 1px solid #22c55e;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  font-weight: 700;
}
.section-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}
.audit-table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.9rem; }
.audit-table th, .audit-table td {
  text-align: left;
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid #334155;
}
.pill-fp {
  background: #7f1d1d;
  color: #fecaca;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-size: 0.8rem;
}
.pill-tr {
  background: #78350f;
  color: #fde68a;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-size: 0.8rem;
}
.pill-ok {
  background: #14532d;
  color: #bbf7d0;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-size: 0.8rem;
}
"""


def extract_defined_css_classes(css_text: str = REPORT_CSS) -> set[str]:
    """Return every CSS class selector defined in REPORT_CSS."""
    return set(re.findall(r"\.([a-zA-Z0-9_-]+)\b", css_text))


def extract_used_html_classes(html_text: str) -> set[str]:
    """Return every CSS class token referenced in HTML class attributes."""
    used: set[str] = set()
    for m in re.findall(r'class="([^"]+)"', html_text):
        for tok in m.split():
            used.add(tok)
    return used


def _kpi(label: str, val: str, cls: str) -> str:
    return (
        '<div class="kpi-box">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="{cls}">{val}</div>'
        "</div>"
    )


def render_html_report(summary: AuditSummary) -> str:
    """Render standalone dark-mode HTML audit report with slice and query breakdowns."""
    b_cls = "verdict-badge-pass" if summary.gate_passed else "verdict-badge-block"
    b_txt = "GATE PASSED" if summary.gate_passed else "GATE BLOCKED: FALSE-PASS REGRESSIONS"

    kpis = "".join([
        _kpi("Evaluated Records", str(summary.total_records), "kpi-value"),
        _kpi("Naive Pass (>=0.65)", str(summary.naive_pass_count), "kpi-value"),
        _kpi("True Regressions", str(summary.true_regression_count), "kpi-danger"),
        _kpi("False-Pass Hidden", str(summary.false_pass_regression_count), "kpi-danger"),
        _kpi("Resolution Floor", f"{summary.resolution_floor_pct:.2f}%", "kpi-value"),
    ])

    s_rows = "".join(
        "<tr>"
        f"<td>{html.escape(s.slice_name)}</td>"
        f"<td>{s.record_count}</td>"
        f"<td>{s.naive_pass_count}</td>"
        f"<td>{s.true_regression_count}</td>"
        f"<td>{s.false_pass_count}</td>"
        f"<td>{s.mean_grounded_recall:.3f}</td>"
        f"<td>{s.mean_delta:+.4f}</td>"
        "</tr>"
        for s in summary.slices
    )

    q_rows = []
    for it in summary.items:
        if it.false_pass_regression:
            p_cls, p_txt = "pill-fp", "FALSE_PASS"
        elif it.true_regression:
            p_cls, p_txt = "pill-tr", "TRUE_REG"
        else:
            p_cls, p_txt = "pill-ok", "OK"
        q_rows.append(
            "<tr>"
            f"<td>{html.escape(it.query_id)}</td>"
            f"<td>{html.escape(it.slice_name)}</td>"
            f"<td>{it.overlap_score:.3f}</td>"
            f"<td>{it.grounded_recall:.3f}</td>"
            f"<td>{it.delta:+.3f}</td>"
            f'<td><span class="{p_cls}">{p_txt}</span></td>'
            "</tr>"
        )

    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8"/>'
        "<title>rag-regression-auditor Report</title>"
        f"<style>{REPORT_CSS}</style></head><body>"
        '<div class="header-card">'
        "<h1>rag-regression-auditor: Offline Audit Report</h1>"
        f'<span class="{b_cls}">{b_txt}</span>'
        f'<div class="kpi-row">{kpis}</div></div>'
        '<section class="section-card"><h2>Slice Breakdown</h2>'
        '<table class="audit-table"><thead><tr>'
        "<th>Slice</th><th>Queries</th><th>Naive Pass</th><th>True Reg</th>"
        "<th>False-Pass</th><th>Mean Recall</th><th>Mean Delta</th></tr></thead>"
        f"<tbody>{s_rows}</tbody></table></section>"
        '<section class="section-card"><h2>Per-Query Findings</h2>'
        '<table class="audit-table"><thead><tr>'
        "<th>Query ID</th><th>Slice</th><th>Overlap</th><th>Recall</th>"
        "<th>Delta</th><th>Status</th></tr></thead>"
        f"<tbody>{''.join(q_rows)}</tbody></table></section>"
        "</body></html>"
    )

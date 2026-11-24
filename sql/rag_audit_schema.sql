-- Relational schema and slice-level diagnostic queries for RAG regression audits.
CREATE TABLE IF NOT EXISTS rag_audit_runs (
    run_id TEXT PRIMARY KEY,
    total_records INTEGER NOT NULL,
    naive_pass_count INTEGER NOT NULL,
    true_regression_count INTEGER NOT NULL,
    false_pass_regression_count INTEGER NOT NULL,
    resolution_floor_pct REAL NOT NULL,
    gate_passed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_audit_items (
    run_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    slice_name TEXT NOT NULL,
    baseline_score REAL NOT NULL,
    candidate_score REAL NOT NULL,
    overlap_score REAL NOT NULL,
    grounded_recall REAL NOT NULL,
    delta REAL NOT NULL,
    false_pass_regression INTEGER NOT NULL,
    failure_reason TEXT NOT NULL,
    PRIMARY KEY (run_id, query_id)
);

-- Rank slices by hidden false-pass regressions where naive lexical overlap passed.
SELECT
    slice_name,
    COUNT(*) AS total_queries,
    SUM(false_pass_regression) AS false_pass_count,
    ROUND(AVG(grounded_recall), 4) AS mean_grounded_recall,
    ROUND(AVG(delta), 4) AS mean_delta
FROM rag_audit_items
GROUP BY slice_name
ORDER BY false_pass_count DESC, mean_delta ASC;

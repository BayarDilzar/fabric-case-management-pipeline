-- Question 6: can the figures be trusted? One row per extract, from its latest successful run:
-- rows loaded into Bronze, values fixed, duplicate rows removed and rows quarantined, for the four source tables.
-- nb_load_gold copies these from dq.reconciliation, dq.rule_results and ops.run_log in lh_silver.
CREATE OR ALTER VIEW reporting.data_trust_by_extract AS
SELECT
    extract_id,
    rows_loaded,
    values_fixed,
    rows_removed,
    rows_quarantined,
    run_id,
    run_started_at,
    -- The newest successful run of any extract, repeated on every row: when the data was last loaded.
    MAX(run_started_at) OVER () AS last_successful_load
FROM dbo.fact_extract_load;

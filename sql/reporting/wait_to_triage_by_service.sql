-- Question 3: how long people wait from referral to triage, by service and for all services.
-- Only triaged episodes have a wait. The threshold is wait_threshold_days in report_settings,
-- 21 days unless nb_load_gold is run with another value. It is a local target, not a national standard.
CREATE OR ALTER VIEW reporting.wait_to_triage_by_service AS
WITH waits AS (
    SELECT s.service_name, f.wait_days, f.is_seen_within_threshold
    FROM dbo.fact_episode AS f
    JOIN dbo.dim_service AS s ON s.service_code = f.service_code
    WHERE f.wait_days IS NOT NULL
    UNION ALL
    -- The same waits again under one name, for the all-services row.
    SELECT 'All services', wait_days, is_seen_within_threshold
    FROM dbo.fact_episode
    WHERE wait_days IS NOT NULL
)
-- A median cannot be added up from the service rows, so each group is computed on its own rows.
-- PERCENTILE_CONT is a window function here, so DISTINCT keeps one row per service.
SELECT DISTINCT
    service_name,
    COUNT(*) OVER (PARTITION BY service_name) AS triaged_episodes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_days) OVER (PARTITION BY service_name) AS median_wait_days,
    -- The average of a 1 or 0 flag is the share of episodes seen within the threshold.
    AVG(CASE WHEN is_seen_within_threshold = 1 THEN 1.0 ELSE 0.0 END) OVER (PARTITION BY service_name) AS share_seen_within_threshold,
    (SELECT wait_threshold_days FROM dbo.report_settings) AS wait_threshold_days
FROM waits;

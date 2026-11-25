-- Question 4: what share of discharges are planned completions, by service and for all services.
-- A planned completion is discharge reason COMPLETED. Open episodes have not been discharged and are left out.
CREATE OR ALTER VIEW reporting.planned_completions_by_service AS
SELECT
    COALESCE(s.service_name, 'All services') AS service_name,  -- ROLLUP leaves the name empty on its total row
    COUNT(*) AS discharges,
    SUM(CASE WHEN f.is_planned_completion = 1 THEN 1 ELSE 0 END) AS planned_completions,
    -- The average of a 1 or 0 flag is the share of discharges that were planned completions.
    AVG(CASE WHEN f.is_planned_completion = 1 THEN 1.0 ELSE 0.0 END) AS planned_completion_share
FROM dbo.fact_episode AS f
JOIN dbo.dim_service AS s ON s.service_code = f.service_code
WHERE f.is_open = 0
GROUP BY ROLLUP (s.service_name);

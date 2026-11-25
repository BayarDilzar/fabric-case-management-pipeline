-- Question 1: how many people are in treatment now, by service.
-- "In treatment" means an episode with no discharge date on the reporting date,
-- which is the cut-off of the latest loaded extract, not today.
CREATE OR ALTER VIEW reporting.people_in_treatment_by_service AS
SELECT
    s.service_name,
    -- Count people, not episodes. The rules allow only one open episode per client.
    COUNT(DISTINCT f.client_id) AS people_in_treatment,
    r.reporting_date
FROM dbo.fact_episode AS f
JOIN dbo.dim_service AS s ON s.service_code = f.service_code
CROSS JOIN dbo.report_settings AS r  -- one row, so this only adds the reporting date
WHERE f.is_open = 1
GROUP BY s.service_name, r.reporting_date;

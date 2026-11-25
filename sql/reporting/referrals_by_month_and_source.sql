-- Question 2: how many new referrals arrive each month, and from which sources.
-- Each episode starts with one referral, so one episode is one referral.
CREATE OR ALTER VIEW reporting.referrals_by_month_and_source AS
SELECT
    d.month_start,                      -- first day of the referral month
    rs.referral_source_label AS referral_source,
    COUNT(*) AS referrals
FROM dbo.fact_episode AS f
JOIN dbo.dim_date AS d ON d.calendar_date = f.referral_date
JOIN dbo.dim_referral_source AS rs ON rs.referral_source = f.referral_source
GROUP BY d.month_start, rs.referral_source_label;

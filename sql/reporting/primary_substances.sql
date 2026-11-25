-- Question 5: which primary substances people present with.
-- Every episode is one presentation, so the share is out of all episodes.
CREATE OR ALTER VIEW reporting.primary_substances AS
SELECT
    sb.substance_label AS primary_substance,
    COUNT(*) AS episodes,
    -- SUM(COUNT(*)) OVER () is the total of all groups, so this is each group's share of the total.
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS share_of_episodes
FROM dbo.fact_episode AS f
JOIN dbo.dim_substance AS sb ON sb.primary_substance = f.primary_substance
GROUP BY sb.substance_label;

# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "429d9211-4452-441f-9a73-d314301863a4",
# META       "default_lakehouse_name": "lh_gold",
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224"
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# pl_load_extract passes its run_id. That run counts as loaded here although its run log row is written after
# this step, so the data trust figures and the reporting date include it. wait_threshold_days is the triage
# target the reports measure against; it is a local choice, not a national standard.
run_id = ""
wait_threshold_days = "21"

# CELL ********************

import re

if run_id and not re.fullmatch(r"\d{8}T\d{6}Z", run_id):
    raise ValueError(f"run_id must look like 20261122T200000Z, not '{run_id}'.")
if not re.fullmatch(r"\d{1,3}", wait_threshold_days):
    raise ValueError(f"wait_threshold_days must be a whole number of days, not '{wait_threshold_days}'.")

# Gold is rebuilt in full on every run from Silver, so it always matches Silver. Silver and the run log are
# read by name from lh_silver; Gold tables go in dbo of the attached lakehouse.
# The latest loaded run of each extract: Succeeded in the run log, or the run calling this notebook, whose Silver
# step has just finished. Made from a DataFrame, because a view written as SQL text cannot name a lakehouse table.
spark.sql(f"""
    SELECT extract_id, max(run_id) AS run_id
    FROM (SELECT extract_id, run_id FROM lh_silver.ops.run_log WHERE status = 'Succeeded'
          UNION ALL
          SELECT DISTINCT extract_id, run_id FROM lh_silver.dq.reconciliation WHERE run_id = '{run_id}')
    GROUP BY extract_id
""").createOrReplaceTempView("loads")
if spark.table("loads").isEmpty():
    raise ValueError("No extract has loaded into Silver yet, so there is nothing to build Gold from.")

# CELL ********************

# The reporting date is the cut-off of the latest loaded extract, never today, so results repeat.
spark.sql(f"""
CREATE OR REPLACE TABLE dbo.report_settings USING DELTA AS
SELECT CAST(max(extract_id) AS DATE) AS reporting_date,
       {wait_threshold_days} AS wait_threshold_days,
       current_timestamp() AS built_at,
       nullif('{run_id}', '') AS built_by_run_id
FROM loads
""")

# One row per day from the first referral to the reporting date, for monthly charts.
spark.sql("""
CREATE OR REPLACE TABLE dbo.dim_date USING DELTA AS
SELECT d AS calendar_date, year(d) AS year, month(d) AS month,
       CAST(date_trunc('MONTH', d) AS DATE) AS month_start, date_format(d, 'yyyy-MM') AS year_month
FROM (SELECT explode(sequence((SELECT min(referral_date) FROM lh_silver.dbo.episodes),
                              (SELECT reporting_date FROM dbo.report_settings), INTERVAL 1 DAY)) AS d)
""")

spark.sql("""
CREATE OR REPLACE TABLE dbo.dim_service USING DELTA AS
SELECT service_code, service_name, local_authority_code FROM lh_silver.dbo.services
""")

# One small dimension per code list a question needs, so each relationship in the model is a plain one-to-many.
spark.sql("""
CREATE OR REPLACE TABLE dbo.dim_referral_source USING DELTA AS
SELECT code AS referral_source, label AS referral_source_label FROM lh_silver.dbo.code_lists WHERE list_name = 'referral_source'
""")
spark.sql("""
CREATE OR REPLACE TABLE dbo.dim_substance USING DELTA AS
SELECT code AS primary_substance, label AS substance_label FROM lh_silver.dbo.code_lists WHERE list_name = 'substance'
""")
# A planned completion is discharge_reason COMPLETED, the spec's successful completion.
spark.sql("""
CREATE OR REPLACE TABLE dbo.dim_discharge_reason USING DELTA AS
SELECT code AS discharge_reason, label AS discharge_reason_label, code = 'COMPLETED' AS is_planned_completion
FROM lh_silver.dbo.code_lists WHERE list_name = 'discharge_reason'
""")

# Age band at the client's first referral in Silver. A client whose only episode was quarantined has none.
spark.sql("""
CREATE OR REPLACE TABLE dbo.dim_client USING DELTA AS
SELECT c.client_id, c.sex, s.label AS sex_label, c.birth_year,
       CASE WHEN f.first_referral IS NULL THEN 'Not known'
            WHEN year(f.first_referral) - c.birth_year < 25 THEN '18 to 24'
            WHEN year(f.first_referral) - c.birth_year < 35 THEN '25 to 34'
            WHEN year(f.first_referral) - c.birth_year < 45 THEN '35 to 44'
            WHEN year(f.first_referral) - c.birth_year < 55 THEN '45 to 54'
            WHEN year(f.first_referral) - c.birth_year < 65 THEN '55 to 64'
            ELSE '65 and over' END AS age_band_at_first_referral
FROM lh_silver.dbo.clients c
LEFT JOIN (SELECT client_id, min(referral_date) AS first_referral FROM lh_silver.dbo.episodes GROUP BY client_id) f
       ON f.client_id = c.client_id
LEFT JOIN lh_silver.dbo.code_lists s ON s.list_name = 'sex' AND s.code = c.sex
""")

# CELL ********************

# One row per Silver episode. Open episodes are measured to the reporting date. wait_days and
# is_seen_within_threshold stay empty for an episode not yet triaged, so it never counts as a wait.
spark.sql("""
CREATE OR REPLACE TABLE dbo.fact_episode USING DELTA AS
SELECT e.episode_id, e.client_id, e.service_code, e.referral_source, e.primary_substance, e.discharge_reason,
       e.referral_date, e.triage_date, e.discharge_date,
       datediff(e.triage_date, e.referral_date) AS wait_days,
       datediff(coalesce(e.discharge_date, s.reporting_date), e.referral_date) AS length_of_stay_days,
       e.discharge_date IS NULL AS is_open,
       coalesce(e.discharge_reason = 'COMPLETED', false) AS is_planned_completion,
       datediff(e.triage_date, e.referral_date) <= s.wait_threshold_days AS is_seen_within_threshold
FROM lh_silver.dbo.episodes e
CROSS JOIN dbo.report_settings s
""")

# Data trust: one row per loaded extract, from its latest loaded run. Counts cover the four source tables;
# the reference tables load with every extract and are left out. The start time is read from the run id.
spark.sql("""
CREATE OR REPLACE TABLE dbo.fact_extract_load USING DELTA AS
SELECT l.extract_id, l.run_id,
       to_timestamp(concat(substr(l.run_id, 1, 8), substr(l.run_id, 10, 6)), 'yyyyMMddHHmmss') AS run_started_at,
       r.rows_loaded, coalesce(f.values_fixed, 0) AS values_fixed, r.rows_removed, r.rows_quarantined
FROM loads l
JOIN (SELECT run_id, sum(bronze_rows) AS rows_loaded, sum(duplicates_removed) AS rows_removed, sum(quarantined) AS rows_quarantined
      FROM lh_silver.dq.reconciliation
      WHERE table_name IN ('clients', 'episodes', 'interventions', 'reviews')
      GROUP BY run_id) r ON r.run_id = l.run_id
LEFT JOIN (SELECT run_id, sum(rows_failed) AS values_fixed FROM lh_silver.dq.rule_results WHERE action = 'fixed' GROUP BY run_id) f
       ON f.run_id = l.run_id
""")

# CELL ********************

# Gold must hold every Silver episode and client once; a lost or doubled row stops the run.
counts = spark.sql("""
SELECT (SELECT count(*) FROM dbo.fact_episode) AS fact_episode, (SELECT count(DISTINCT episode_id) FROM dbo.fact_episode) AS fact_keys,
       (SELECT count(*) FROM lh_silver.dbo.episodes) AS silver_episodes,
       (SELECT count(*) FROM dbo.dim_client) AS dim_client, (SELECT count(*) FROM lh_silver.dbo.clients) AS silver_clients
""").first()
print(counts.asDict())
if not counts.fact_episode == counts.fact_keys == counts.silver_episodes or counts.dim_client != counts.silver_clients:
    raise ValueError(f"Gold does not match Silver: {counts.asDict()}")
spark.sql("SELECT * FROM dbo.report_settings").show(truncate=False)
spark.sql("SELECT * FROM dbo.fact_extract_load ORDER BY extract_id").show(truncate=False)

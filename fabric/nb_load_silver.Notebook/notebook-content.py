# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a1056192-5bb5-437c-865c-2de615388ce8",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224"
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# Set when the notebook is run. It is empty by default, so a run without it fails instead of guessing.
extract_id = ""

# CELL ********************

import re
from datetime import datetime, timezone

if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", extract_id):
    raise ValueError(f"extract_id must be an extract date such as 2026-10-25, not '{extract_id}'.")

# Silver tables go in dbo and the data quality tables in dq, in the attached lakehouse.
SILVER = "dbo"
DQ = "dq"
# Runs go one at a time, so the start time in UTC is enough to tell them apart.
run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# One view per Bronze table, holding only this extract. Python puts the checked extract_id into the query,
# because spark.sql named parameters failed on this runtime. The views are made from DataFrames because a
# view made from SQL text cannot name another lakehouse here. Every query below reads these views.
SOURCES = {"clients": extract_id, "episodes": extract_id, "interventions": extract_id, "reviews": extract_id,
           "services": "reference", "code_lists": "reference"}
for table, tag in SOURCES.items():
    spark.sql(f"SELECT * FROM lh_bronze.dbo.{table} WHERE _extract_id = '{tag}'").createOrReplaceTempView(f"bronze_{table}")
spark.sql(f"SELECT '{run_id}' AS run_id, '{extract_id}' AS extract_id, DATE'{extract_id}' AS cut_off").createOrReplaceTempView("run")

# Stop before any write if the extract is not in Bronze.
empty = [table for table in SOURCES if spark.table(f"bronze_{table}").isEmpty()]
if empty:
    raise ValueError(f"No Bronze rows for extract_id '{extract_id}' in: {', '.join(empty)}. Load the extract into Bronze first.")

# CELL ********************

# Every rule, its action and the text used as the quarantine reason. A row's rule ids are listed in the
# order the checks run: missing, unreadable type, invalid code, orphan, business rules, quarantined parent.
spark.sql("""
CREATE OR REPLACE TEMP VIEW rules AS
SELECT * FROM VALUES
    ('clients', 'DQ_CLI_DUP_EXACT', 'Exact copy of another row with the same client_id. One copy is kept.', 'removed'),
    ('clients', 'DQ_CLI_DUP_VERSION', 'Older version of a client_id. The row with the latest last_modified_at is kept.', 'removed'),
    ('clients', 'DQ_CLI_TRIM', 'Spaces trimmed from client_id, birth_year, local_authority_code or last_modified_at.', 'fixed'),
    ('clients', 'DQ_CLI_CODE_CASE', 'sex written in lower case or with spaces, so it was trimmed and upper-cased.', 'fixed'),
    ('clients', 'DQ_CLI_MISSING_REQUIRED', 'A required field is empty: client_id, birth_year, sex or last_modified_at.', 'quarantined'),
    ('clients', 'DQ_CLI_INVALID_TYPE', 'birth_year is not a whole number, or last_modified_at is not a timestamp.', 'quarantined'),
    ('clients', 'DQ_CLI_INVALID_CODE', 'sex is not in its code list.', 'quarantined'),

    ('episodes', 'DQ_EPI_DUP_EXACT', 'Exact copy of another row with the same episode_id. One copy is kept.', 'removed'),
    ('episodes', 'DQ_EPI_DUP_VERSION', 'Older version of an episode_id. The row with the latest last_modified_at is kept.', 'removed'),
    ('episodes', 'DQ_EPI_TRIM', 'Spaces trimmed from episode_id, client_id, a date or last_modified_at.', 'fixed'),
    ('episodes', 'DQ_EPI_CODE_CASE', 'service_code, referral_source, primary_substance or discharge_reason written in lower case or with spaces, so it was trimmed and upper-cased.', 'fixed'),
    ('episodes', 'DQ_EPI_DATE_FORMAT', 'referral_date, triage_date or discharge_date written as DD/MM/YYYY or YYYYMMDD, read as a date.', 'fixed'),
    ('episodes', 'DQ_EPI_MISSING_REQUIRED', 'A required field is empty: episode_id, client_id, service_code, referral_date, referral_source, primary_substance or last_modified_at.', 'quarantined'),
    ('episodes', 'DQ_EPI_INVALID_TYPE', 'A date is not a real date in an accepted format, or last_modified_at is not a timestamp.', 'quarantined'),
    ('episodes', 'DQ_EPI_INVALID_CODE', 'service_code is not in services, or referral_source, primary_substance or discharge_reason is not in its code list.', 'quarantined'),
    ('episodes', 'DQ_EPI_ORPHAN_CLIENT', 'client_id is not in clients.', 'quarantined'),
    ('episodes', 'DQ_EPI_DISCHARGE_BEFORE_REFERRAL', 'discharge_date is before referral_date (rule R07).', 'quarantined'),
    ('episodes', 'DQ_EPI_FUTURE_DATE', 'A date is after the extract cut-off (rule R10).', 'quarantined'),
    ('episodes', 'DQ_EPI_CLIENT_QUARANTINED', 'The client of this episode is quarantined.', 'quarantined'),

    ('interventions', 'DQ_INT_DUP_EXACT', 'Exact copy of another row with the same intervention_id. One copy is kept.', 'removed'),
    ('interventions', 'DQ_INT_DUP_VERSION', 'Older version of an intervention_id. The row with the latest last_modified_at is kept.', 'removed'),
    ('interventions', 'DQ_INT_TRIM', 'Spaces trimmed from intervention_id, episode_id, a date or last_modified_at.', 'fixed'),
    ('interventions', 'DQ_INT_CODE_CASE', 'intervention_type written in lower case or with spaces, so it was trimmed and upper-cased.', 'fixed'),
    ('interventions', 'DQ_INT_DATE_FORMAT', 'start_date or end_date written as DD/MM/YYYY or YYYYMMDD, read as a date.', 'fixed'),
    ('interventions', 'DQ_INT_MISSING_REQUIRED', 'A required field is empty: intervention_id, episode_id, intervention_type, start_date or last_modified_at.', 'quarantined'),
    ('interventions', 'DQ_INT_INVALID_TYPE', 'A date is not a real date in an accepted format, or last_modified_at is not a timestamp.', 'quarantined'),
    ('interventions', 'DQ_INT_INVALID_CODE', 'intervention_type is not in its code list.', 'quarantined'),
    ('interventions', 'DQ_INT_ORPHAN_EPISODE', 'episode_id is not in episodes.', 'quarantined'),
    ('interventions', 'DQ_INT_END_BEFORE_START', 'end_date is before start_date (rule R08).', 'quarantined'),
    ('interventions', 'DQ_INT_FUTURE_DATE', 'A date is after the extract cut-off (rule R10).', 'quarantined'),
    ('interventions', 'DQ_INT_EPISODE_QUARANTINED', 'The episode of this intervention is quarantined.', 'quarantined'),

    ('reviews', 'DQ_REV_DUP_EXACT', 'Exact copy of another row with the same review_id. One copy is kept.', 'removed'),
    ('reviews', 'DQ_REV_DUP_VERSION', 'Older version of a review_id. The row with the latest last_modified_at is kept.', 'removed'),
    ('reviews', 'DQ_REV_TRIM', 'Spaces trimmed from review_id, episode_id, review_date, a score or last_modified_at.', 'fixed'),
    ('reviews', 'DQ_REV_CODE_CASE', 'review_type written in lower case or with spaces, so it was trimmed and upper-cased.', 'fixed'),
    ('reviews', 'DQ_REV_DATE_FORMAT', 'review_date written as DD/MM/YYYY or YYYYMMDD, read as a date.', 'fixed'),
    ('reviews', 'DQ_REV_MISSING_REQUIRED', 'A required field is empty: review_id, episode_id, review_date, review_type or last_modified_at.', 'quarantined'),
    ('reviews', 'DQ_REV_INVALID_TYPE', 'review_date is not a real date in an accepted format, a score is not a whole number, or last_modified_at is not a timestamp.', 'quarantined'),
    ('reviews', 'DQ_REV_INVALID_CODE', 'review_type is not in its code list.', 'quarantined'),
    ('reviews', 'DQ_REV_ORPHAN_EPISODE', 'episode_id is not in episodes.', 'quarantined'),
    ('reviews', 'DQ_REV_DAYS_RANGE', 'days_used_last_28 is outside 0 to 28 (rule R09).', 'quarantined'),
    ('reviews', 'DQ_REV_QOL_RANGE', 'quality_of_life is outside 0 to 20 (rule R09).', 'quarantined'),
    ('reviews', 'DQ_REV_FUTURE_DATE', 'review_date is after the extract cut-off (rule R10).', 'quarantined'),
    ('reviews', 'DQ_REV_EPISODE_QUARANTINED', 'The episode of this review is quarantined.', 'quarantined')
AS rules(table_name, rule_id, rule_description, action)
""")

# Reference tables: trimmed text, no rules, because they are what the checks compare against.
spark.sql("""
CREATE OR REPLACE TEMP VIEW silver_services AS
SELECT trim(service_code) AS service_code, trim(service_name) AS service_name,
       trim(local_authority_code) AS local_authority_code, _extract_id
FROM bronze_services
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW silver_code_lists AS
SELECT trim(list_name) AS list_name, trim(code) AS code, trim(label) AS label, _extract_id
FROM bronze_code_lists
""")

# One row holding the valid codes for each code field.
spark.sql("""
CREATE OR REPLACE TEMP VIEW valid_codes AS
SELECT *
FROM (SELECT collect_set(service_code) AS service_code FROM silver_services)
CROSS JOIN (
    SELECT collect_set(CASE WHEN list_name = 'sex' THEN code END) AS sex,
           collect_set(CASE WHEN list_name = 'referral_source' THEN code END) AS referral_source,
           collect_set(CASE WHEN list_name = 'substance' THEN code END) AS primary_substance,
           collect_set(CASE WHEN list_name = 'discharge_reason' THEN code END) AS discharge_reason,
           collect_set(CASE WHEN list_name = 'intervention_type' THEN code END) AS intervention_type,
           collect_set(CASE WHEN list_name = 'review_type' THEN code END) AS review_type
    FROM silver_code_lists
)
""")

# CELL ********************

# Step 1, typed: trim every value, upper-case codes, read dates written in any of the three accepted formats,
# and keep the original Bronze row as a struct for the checks and the quarantine. The try_ functions give
# null for a value that cannot be read, and the checks below turn that null into a rule failure.
spark.sql("""
CREATE OR REPLACE TEMP VIEW typed_clients AS
SELECT nullif(trim(client_id), '') AS client_id,
       try_cast(trim(birth_year) AS INT) AS birth_year,
       nullif(upper(trim(sex)), '') AS sex,
       nullif(trim(local_authority_code), '') AS local_authority_code,
       try_to_timestamp(trim(last_modified_at), 'yyyy-MM-dd HH:mm:ss') AS last_modified_at,
       struct(b.*) AS bronze
FROM bronze_clients b
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW typed_episodes AS
SELECT nullif(trim(episode_id), '') AS episode_id,
       nullif(trim(client_id), '') AS client_id,
       nullif(upper(trim(service_code)), '') AS service_code,
       CAST(coalesce(try_to_timestamp(trim(referral_date), 'yyyy-MM-dd'),
                     try_to_timestamp(trim(referral_date), 'dd/MM/yyyy'),
                     try_to_timestamp(trim(referral_date), 'yyyyMMdd')) AS DATE) AS referral_date,
       nullif(upper(trim(referral_source)), '') AS referral_source,
       nullif(upper(trim(primary_substance)), '') AS primary_substance,
       CAST(coalesce(try_to_timestamp(trim(triage_date), 'yyyy-MM-dd'),
                     try_to_timestamp(trim(triage_date), 'dd/MM/yyyy'),
                     try_to_timestamp(trim(triage_date), 'yyyyMMdd')) AS DATE) AS triage_date,
       CAST(coalesce(try_to_timestamp(trim(discharge_date), 'yyyy-MM-dd'),
                     try_to_timestamp(trim(discharge_date), 'dd/MM/yyyy'),
                     try_to_timestamp(trim(discharge_date), 'yyyyMMdd')) AS DATE) AS discharge_date,
       nullif(upper(trim(discharge_reason)), '') AS discharge_reason,
       try_to_timestamp(trim(last_modified_at), 'yyyy-MM-dd HH:mm:ss') AS last_modified_at,
       struct(b.*) AS bronze
FROM bronze_episodes b
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW typed_interventions AS
SELECT nullif(trim(intervention_id), '') AS intervention_id,
       nullif(trim(episode_id), '') AS episode_id,
       nullif(upper(trim(intervention_type)), '') AS intervention_type,
       CAST(coalesce(try_to_timestamp(trim(start_date), 'yyyy-MM-dd'),
                     try_to_timestamp(trim(start_date), 'dd/MM/yyyy'),
                     try_to_timestamp(trim(start_date), 'yyyyMMdd')) AS DATE) AS start_date,
       CAST(coalesce(try_to_timestamp(trim(end_date), 'yyyy-MM-dd'),
                     try_to_timestamp(trim(end_date), 'dd/MM/yyyy'),
                     try_to_timestamp(trim(end_date), 'yyyyMMdd')) AS DATE) AS end_date,
       try_to_timestamp(trim(last_modified_at), 'yyyy-MM-dd HH:mm:ss') AS last_modified_at,
       struct(b.*) AS bronze
FROM bronze_interventions b
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW typed_reviews AS
SELECT nullif(trim(review_id), '') AS review_id,
       nullif(trim(episode_id), '') AS episode_id,
       CAST(coalesce(try_to_timestamp(trim(review_date), 'yyyy-MM-dd'),
                     try_to_timestamp(trim(review_date), 'dd/MM/yyyy'),
                     try_to_timestamp(trim(review_date), 'yyyyMMdd')) AS DATE) AS review_date,
       nullif(upper(trim(review_type)), '') AS review_type,
       try_cast(trim(days_used_last_28) AS INT) AS days_used_last_28,
       try_cast(trim(quality_of_life) AS INT) AS quality_of_life,
       try_to_timestamp(trim(last_modified_at), 'yyyy-MM-dd HH:mm:ss') AS last_modified_at,
       struct(b.*) AS bronze
FROM bronze_reviews b
""")

# CELL ********************

# Step 2, ranked: number the rows of each business key, newest last_modified_at first. Row 1 is kept.
# same_as_kept says whether a removed row is an exact copy of the kept row or an older version of it.
# The same query runs for each table, so Python fills in the table and key names.
RANKED = """
CREATE OR REPLACE TEMP VIEW ranked_{table} AS
SELECT *,
       -- A row with no key is not a copy of other rows with no key, so each one stands alone.
       CASE WHEN {key} IS NULL THEN 1 ELSE row_number() OVER newest_first END AS copy_number,
       to_json(bronze) = first_value(to_json(bronze)) OVER newest_first AS same_as_kept
FROM typed_{table}
WINDOW newest_first AS (PARTITION BY {key} ORDER BY last_modified_at DESC NULLS LAST, to_json(bronze))
"""
TABLES = {"clients": ("client_id", "CLI"), "episodes": ("episode_id", "EPI"),
          "interventions": ("intervention_id", "INT"), "reviews": ("review_id", "REV")}
for table, (key, _) in TABLES.items():
    spark.sql(RANKED.format(table=table, key=key))

# CELL ********************

# Step 3, checked: the kept row of each key, with the fix rules it needed and the quarantine rules it failed.
# A row with any failed rule is quarantined once, listing all of them. Parents are checked first, so a child
# can see whether its parent is quarantined. filter(array(...)) keeps only the rules that applied.
spark.sql("""
CREATE OR REPLACE TEMP VIEW checked_clients AS
SELECT c.*,
       filter(array(
           IF(c.bronze.client_id <> trim(c.bronze.client_id) OR c.bronze.birth_year <> trim(c.bronze.birth_year)
              OR c.bronze.local_authority_code <> trim(c.bronze.local_authority_code)
              OR c.bronze.last_modified_at <> trim(c.bronze.last_modified_at), 'DQ_CLI_TRIM', NULL),
           IF(c.bronze.sex <> c.sex AND array_contains(v.sex, c.sex), 'DQ_CLI_CODE_CASE', NULL)
       ), rule -> rule IS NOT NULL) AS fixed_rules,
       filter(array(
           IF(c.client_id IS NULL OR coalesce(trim(c.bronze.birth_year), '') = '' OR c.sex IS NULL
              OR coalesce(trim(c.bronze.last_modified_at), '') = '', 'DQ_CLI_MISSING_REQUIRED', NULL),
           IF((trim(c.bronze.birth_year) <> '' AND c.birth_year IS NULL)
              OR (trim(c.bronze.last_modified_at) <> '' AND c.last_modified_at IS NULL), 'DQ_CLI_INVALID_TYPE', NULL),
           IF(NOT array_contains(v.sex, c.sex), 'DQ_CLI_INVALID_CODE', NULL)
       ), rule -> rule IS NOT NULL) AS failed_rules
FROM ranked_clients c
CROSS JOIN valid_codes v
WHERE c.copy_number = 1
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW checked_episodes AS
SELECT e.*,
       filter(array(
           IF(e.bronze.episode_id <> trim(e.bronze.episode_id) OR e.bronze.client_id <> trim(e.bronze.client_id)
              OR e.bronze.referral_date <> trim(e.bronze.referral_date) OR e.bronze.triage_date <> trim(e.bronze.triage_date)
              OR e.bronze.discharge_date <> trim(e.bronze.discharge_date)
              OR e.bronze.last_modified_at <> trim(e.bronze.last_modified_at), 'DQ_EPI_TRIM', NULL),
           IF((e.bronze.service_code <> e.service_code AND array_contains(v.service_code, e.service_code))
              OR (e.bronze.referral_source <> e.referral_source AND array_contains(v.referral_source, e.referral_source))
              OR (e.bronze.primary_substance <> e.primary_substance AND array_contains(v.primary_substance, e.primary_substance))
              OR (e.bronze.discharge_reason <> e.discharge_reason AND array_contains(v.discharge_reason, e.discharge_reason)),
              'DQ_EPI_CODE_CASE', NULL),
           IF((NOT trim(e.bronze.referral_date) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND e.referral_date IS NOT NULL)
              OR (NOT trim(e.bronze.triage_date) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND e.triage_date IS NOT NULL)
              OR (NOT trim(e.bronze.discharge_date) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND e.discharge_date IS NOT NULL),
              'DQ_EPI_DATE_FORMAT', NULL)
       ), rule -> rule IS NOT NULL) AS fixed_rules,
       filter(array(
           IF(e.episode_id IS NULL OR e.client_id IS NULL OR e.service_code IS NULL
              OR coalesce(trim(e.bronze.referral_date), '') = '' OR e.referral_source IS NULL
              OR e.primary_substance IS NULL OR coalesce(trim(e.bronze.last_modified_at), '') = '',
              'DQ_EPI_MISSING_REQUIRED', NULL),
           IF((trim(e.bronze.referral_date) <> '' AND e.referral_date IS NULL)
              OR (trim(e.bronze.triage_date) <> '' AND e.triage_date IS NULL)
              OR (trim(e.bronze.discharge_date) <> '' AND e.discharge_date IS NULL)
              OR (trim(e.bronze.last_modified_at) <> '' AND e.last_modified_at IS NULL), 'DQ_EPI_INVALID_TYPE', NULL),
           IF(NOT array_contains(v.service_code, e.service_code) OR NOT array_contains(v.referral_source, e.referral_source)
              OR NOT array_contains(v.primary_substance, e.primary_substance)
              OR NOT array_contains(v.discharge_reason, e.discharge_reason), 'DQ_EPI_INVALID_CODE', NULL),
           IF(e.client_id IS NOT NULL AND p.client_id IS NULL, 'DQ_EPI_ORPHAN_CLIENT', NULL),
           IF(e.discharge_date < e.referral_date, 'DQ_EPI_DISCHARGE_BEFORE_REFERRAL', NULL),
           IF(greatest(e.referral_date, e.triage_date, e.discharge_date) > r.cut_off, 'DQ_EPI_FUTURE_DATE', NULL),
           IF(size(p.failed_rules) > 0, 'DQ_EPI_CLIENT_QUARANTINED', NULL)
       ), rule -> rule IS NOT NULL) AS failed_rules
FROM ranked_episodes e
CROSS JOIN valid_codes v
CROSS JOIN run r
LEFT JOIN checked_clients p ON p.client_id = e.client_id
WHERE e.copy_number = 1
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW checked_interventions AS
SELECT i.*,
       filter(array(
           IF(i.bronze.intervention_id <> trim(i.bronze.intervention_id) OR i.bronze.episode_id <> trim(i.bronze.episode_id)
              OR i.bronze.start_date <> trim(i.bronze.start_date) OR i.bronze.end_date <> trim(i.bronze.end_date)
              OR i.bronze.last_modified_at <> trim(i.bronze.last_modified_at), 'DQ_INT_TRIM', NULL),
           IF(i.bronze.intervention_type <> i.intervention_type AND array_contains(v.intervention_type, i.intervention_type),
              'DQ_INT_CODE_CASE', NULL),
           IF((NOT trim(i.bronze.start_date) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND i.start_date IS NOT NULL)
              OR (NOT trim(i.bronze.end_date) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND i.end_date IS NOT NULL),
              'DQ_INT_DATE_FORMAT', NULL)
       ), rule -> rule IS NOT NULL) AS fixed_rules,
       filter(array(
           IF(i.intervention_id IS NULL OR i.episode_id IS NULL OR i.intervention_type IS NULL
              OR coalesce(trim(i.bronze.start_date), '') = '' OR coalesce(trim(i.bronze.last_modified_at), '') = '',
              'DQ_INT_MISSING_REQUIRED', NULL),
           IF((trim(i.bronze.start_date) <> '' AND i.start_date IS NULL)
              OR (trim(i.bronze.end_date) <> '' AND i.end_date IS NULL)
              OR (trim(i.bronze.last_modified_at) <> '' AND i.last_modified_at IS NULL), 'DQ_INT_INVALID_TYPE', NULL),
           IF(NOT array_contains(v.intervention_type, i.intervention_type), 'DQ_INT_INVALID_CODE', NULL),
           IF(i.episode_id IS NOT NULL AND p.episode_id IS NULL, 'DQ_INT_ORPHAN_EPISODE', NULL),
           IF(i.end_date < i.start_date, 'DQ_INT_END_BEFORE_START', NULL),
           IF(greatest(i.start_date, i.end_date) > r.cut_off, 'DQ_INT_FUTURE_DATE', NULL),
           IF(size(p.failed_rules) > 0, 'DQ_INT_EPISODE_QUARANTINED', NULL)
       ), rule -> rule IS NOT NULL) AS failed_rules
FROM ranked_interventions i
CROSS JOIN valid_codes v
CROSS JOIN run r
LEFT JOIN checked_episodes p ON p.episode_id = i.episode_id
WHERE i.copy_number = 1
""")
spark.sql("""
CREATE OR REPLACE TEMP VIEW checked_reviews AS
SELECT w.*,
       filter(array(
           IF(w.bronze.review_id <> trim(w.bronze.review_id) OR w.bronze.episode_id <> trim(w.bronze.episode_id)
              OR w.bronze.review_date <> trim(w.bronze.review_date)
              OR w.bronze.days_used_last_28 <> trim(w.bronze.days_used_last_28)
              OR w.bronze.quality_of_life <> trim(w.bronze.quality_of_life)
              OR w.bronze.last_modified_at <> trim(w.bronze.last_modified_at), 'DQ_REV_TRIM', NULL),
           IF(w.bronze.review_type <> w.review_type AND array_contains(v.review_type, w.review_type), 'DQ_REV_CODE_CASE', NULL),
           IF(NOT trim(w.bronze.review_date) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND w.review_date IS NOT NULL,
              'DQ_REV_DATE_FORMAT', NULL)
       ), rule -> rule IS NOT NULL) AS fixed_rules,
       filter(array(
           IF(w.review_id IS NULL OR w.episode_id IS NULL OR coalesce(trim(w.bronze.review_date), '') = ''
              OR w.review_type IS NULL OR coalesce(trim(w.bronze.last_modified_at), '') = '',
              'DQ_REV_MISSING_REQUIRED', NULL),
           IF((trim(w.bronze.review_date) <> '' AND w.review_date IS NULL)
              OR (trim(w.bronze.days_used_last_28) <> '' AND w.days_used_last_28 IS NULL)
              OR (trim(w.bronze.quality_of_life) <> '' AND w.quality_of_life IS NULL)
              OR (trim(w.bronze.last_modified_at) <> '' AND w.last_modified_at IS NULL), 'DQ_REV_INVALID_TYPE', NULL),
           IF(NOT array_contains(v.review_type, w.review_type), 'DQ_REV_INVALID_CODE', NULL),
           IF(w.episode_id IS NOT NULL AND p.episode_id IS NULL, 'DQ_REV_ORPHAN_EPISODE', NULL),
           IF(w.days_used_last_28 NOT BETWEEN 0 AND 28, 'DQ_REV_DAYS_RANGE', NULL),
           IF(w.quality_of_life NOT BETWEEN 0 AND 20, 'DQ_REV_QOL_RANGE', NULL),
           IF(w.review_date > r.cut_off, 'DQ_REV_FUTURE_DATE', NULL),
           IF(size(p.failed_rules) > 0, 'DQ_REV_EPISODE_QUARANTINED', NULL)
       ), rule -> rule IS NOT NULL) AS failed_rules
FROM ranked_reviews w
CROSS JOIN valid_codes v
CROSS JOIN run r
LEFT JOIN checked_episodes p ON p.episode_id = w.episode_id
WHERE w.copy_number = 1
""")

# CELL ********************

# Every write goes through this one function. M2 rebuilds Silver in full; M3 swaps the Silver overwrite for a merge.
# It uses the DataFrame writer because Spark SQL has no single statement that replaces only one extract's rows.
def write(table, query, mode="overwrite", replace_where=None):
    writer = spark.sql(query).write.format("delta").mode(mode)
    if replace_where:
        writer = writer.option("replaceWhere", replace_where)
    writer.saveAsTable(table)


for schema in {SILVER, DQ}:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {DQ}.rule_results (
    run_id STRING, extract_id STRING, table_name STRING, rule_id STRING, rule_description STRING,
    rows_checked BIGINT, rows_failed BIGINT, action STRING) USING DELTA
""")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {DQ}.quarantine (
    run_id STRING, extract_id STRING, source_table STRING, business_key STRING, rule_ids STRING, reason STRING,
    bronze_row STRING) USING DELTA
""")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {DQ}.reconciliation (
    run_id STRING, extract_id STRING, table_name STRING, bronze_rows BIGINT, duplicates_removed BIGINT,
    quarantined BIGINT, silver_rows BIGINT) USING DELTA
""")

# CELL ********************

# Silver: the kept rows that failed no rule, typed, with the extract they came from and the run that wrote them.
for table in TABLES:
    write(f"{SILVER}.{table}", f"""
        SELECT * EXCEPT (bronze, copy_number, same_as_kept, fixed_rules, failed_rules),
               bronze._extract_id AS _extract_id, (SELECT run_id FROM run) AS _run_id
        FROM checked_{table}
        WHERE size(failed_rules) = 0
    """)
for table in ["services", "code_lists"]:
    write(f"{SILVER}.{table}", f"SELECT *, (SELECT run_id FROM run) AS _run_id FROM silver_{table}")

# Quarantine: one row per rejected record, with every rule it failed and the original Bronze row as JSON.
# ignoreNullFields is off so the JSON still shows an empty field as null. A rebuild replaces this extract's rows.
QUARANTINE = """
SELECT r.run_id, r.extract_id, '{table}' AS source_table, c.{key} AS business_key,
       concat_ws(',', c.failed_rules) AS rule_ids,
       concat_ws('; ', transform(c.failed_rules, rule -> t.descriptions[rule])) AS reason,
       to_json(c.bronze, map('ignoreNullFields', 'false')) AS bronze_row
FROM checked_{table} c
CROSS JOIN run r
CROSS JOIN (SELECT map_from_entries(collect_list(struct(rule_id, rule_description))) AS descriptions FROM rules) t
WHERE size(c.failed_rules) > 0
"""
write(f"{DQ}.quarantine", " UNION ALL ".join(QUARANTINE.format(table=t, key=k) for t, (k, _) in TABLES.items()),
      replace_where=f"extract_id = '{extract_id}'")

# Rule results: one row per rule for this run, including rules that found nothing.
# Duplicate rules check every Bronze row; the other rules check the rows left after duplicates are removed.
HITS = """
SELECT '{table}' AS table_name, IF(same_as_kept, 'DQ_{prefix}_DUP_EXACT', 'DQ_{prefix}_DUP_VERSION') AS rule_id
FROM ranked_{table} WHERE copy_number > 1
UNION ALL SELECT '{table}', explode(fixed_rules) FROM checked_{table}
UNION ALL SELECT '{table}', explode(failed_rules) FROM checked_{table}
"""
CHECKED = "SELECT '{table}' AS table_name, (SELECT count(*) FROM bronze_{table}) AS bronze_rows, (SELECT count(*) FROM checked_{table}) AS kept_rows"
hits = " UNION ALL ".join(HITS.format(table=t, prefix=p) for t, (_, p) in TABLES.items())
checked = " UNION ALL ".join(CHECKED.format(table=t) for t in TABLES)
write(f"{DQ}.rule_results", f"""
    WITH hits AS ({hits}),
    counts AS (SELECT table_name, rule_id, count(*) AS rows_failed FROM hits GROUP BY table_name, rule_id),
    checked AS ({checked})
    SELECT r.run_id, r.extract_id, u.table_name, u.rule_id, u.rule_description,
           CASE WHEN u.action = 'removed' THEN k.bronze_rows ELSE k.kept_rows END AS rows_checked,
           coalesce(c.rows_failed, 0) AS rows_failed, u.action
    FROM rules u
    JOIN checked k ON k.table_name = u.table_name
    LEFT JOIN counts c ON c.table_name = u.table_name AND c.rule_id = u.rule_id
    CROSS JOIN run r
""", mode="append")

# CELL ********************

# Reconciliation: each count is read back from where it was stored, so a lost or extra row shows as a gap.
# Bronze rows = Silver rows + quarantined + duplicates removed, for every table.
RECONCILE = f"""
SELECT r.run_id, r.extract_id, '{{table}}' AS table_name,
       (SELECT count(*) FROM bronze_{{table}}) AS bronze_rows,
       (SELECT coalesce(sum(rows_failed), 0) FROM {DQ}.rule_results
        WHERE run_id = r.run_id AND table_name = '{{table}}' AND action = 'removed') AS duplicates_removed,
       (SELECT count(*) FROM {DQ}.quarantine WHERE run_id = r.run_id AND source_table = '{{table}}') AS quarantined,
       (SELECT count(*) FROM {SILVER}.{{table}}) AS silver_rows
FROM run r
"""
write(f"{DQ}.reconciliation", " UNION ALL ".join(RECONCILE.format(table=t) for t in SOURCES), mode="append")

spark.sql(f"""
SELECT table_name, bronze_rows, duplicates_removed, quarantined, silver_rows
FROM {DQ}.reconciliation WHERE run_id = (SELECT run_id FROM run)
""").show(truncate=False)
spark.sql(f"""
SELECT table_name, rule_id, rows_checked, rows_failed, action
FROM {DQ}.rule_results WHERE run_id = (SELECT run_id FROM run) AND rows_failed > 0
ORDER BY table_name, rule_id
""").show(100, truncate=False)

unbalanced = spark.sql(f"""
SELECT table_name FROM {DQ}.reconciliation
WHERE run_id = (SELECT run_id FROM run) AND bronze_rows <> silver_rows + quarantined + duplicates_removed
""").collect()
if unbalanced:
    raise ValueError(f"Reconciliation does not balance for: {', '.join(row.table_name for row in unbalanced)}")

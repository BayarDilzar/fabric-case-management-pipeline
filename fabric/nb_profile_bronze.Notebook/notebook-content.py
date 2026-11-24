# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "381f57db-79ac-4c76-8ad3-61256c09907f",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224"
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# Set when the notebook is run. It is empty by default, so a run without it fails instead of guessing.
extract_id = ""

# CELL ********************

import re

if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", extract_id):
    raise ValueError(f"extract_id must be an extract date such as 2026-10-25, not '{extract_id}'.")

# One view per Bronze table, holding only this extract. Python puts the checked extract_id into the query,
# because spark.sql named parameters failed on this runtime. The views are made from DataFrames because a
# view made from SQL text cannot name another lakehouse here. Every query below reads these views.
SOURCES = {"clients": extract_id, "episodes": extract_id, "interventions": extract_id, "reviews": extract_id,
           "services": "reference", "code_lists": "reference"}
for table, tag in SOURCES.items():
    spark.sql(f"SELECT * FROM lh_bronze.dbo.{table} WHERE _extract_id = '{tag}'").createOrReplaceTempView(f"bronze_{table}")

empty = [table for table in SOURCES if spark.table(f"bronze_{table}").isEmpty()]
if empty:
    raise ValueError(f"No Bronze rows for extract_id '{extract_id}' in: {', '.join(empty)}. Load the extract into Bronze first.")

# CELL ********************

# 1. Every column: rows, nulls, blanks, values with spaces at either end, distinct values.
# UNPIVOT turns each row into one row per column, so one query covers a whole table.
# Python only supplies each table's column names, which differ per table.
COLUMN_PROFILE = """
SELECT '{table}' AS table_name, column_name,
       count(*) AS row_count,
       count_if(value IS NULL) AS nulls,
       count_if(trim(value) = '') AS blanks,
       count_if(value <> trim(value)) AS untrimmed,
       count(DISTINCT value) AS distinct_values
FROM (SELECT {columns} FROM bronze_{table})
UNPIVOT INCLUDE NULLS (value FOR column_name IN ({columns}))
GROUP BY column_name
"""
queries = []
for table in SOURCES:
    columns = ", ".join(c for c in spark.table(f"bronze_{table}").columns if not c.startswith("_"))
    queries.append(COLUMN_PROFILE.format(table=table, columns=columns))
spark.sql(" UNION ALL ".join(queries) + " ORDER BY table_name, column_name").show(100, truncate=False)

# CELL ********************

# 2. Duplicates on the business key. An exact copy repeats every column; another version has the same key
# but different values.
DUPLICATES = """
SELECT '{table}' AS table_name, '{key}' AS business_key,
       count(*) AS keys_with_copies,
       coalesce(sum(copies - 1), 0) AS extra_rows,
       coalesce(sum(copies - versions), 0) AS extra_exact_copies,
       coalesce(sum(versions - 1), 0) AS extra_other_versions
FROM (
    SELECT {key}, count(*) AS copies, count(DISTINCT to_json(struct(*))) AS versions
    FROM bronze_{table}
    WHERE {key} IS NOT NULL
    GROUP BY {key}
    HAVING count(*) > 1
)
"""
KEYS = {"clients": "client_id", "episodes": "episode_id", "interventions": "intervention_id", "reviews": "review_id"}
spark.sql(" UNION ALL ".join(DUPLICATES.format(table=t, key=k) for t, k in KEYS.items())).show(truncate=False)

# CELL ********************

# 3. Date and timestamp formats. Dates should be YYYY-MM-DD and timestamps YYYY-MM-DD HH:MM:SS.
spark.sql("""
WITH date_values AS (
    SELECT 'episodes' AS table_name, 'referral_date' AS column_name, 'YYYY-MM-DD' AS expected, referral_date AS value FROM bronze_episodes
    UNION ALL SELECT 'episodes', 'triage_date', 'YYYY-MM-DD', triage_date FROM bronze_episodes
    UNION ALL SELECT 'episodes', 'discharge_date', 'YYYY-MM-DD', discharge_date FROM bronze_episodes
    UNION ALL SELECT 'interventions', 'start_date', 'YYYY-MM-DD', start_date FROM bronze_interventions
    UNION ALL SELECT 'interventions', 'end_date', 'YYYY-MM-DD', end_date FROM bronze_interventions
    UNION ALL SELECT 'reviews', 'review_date', 'YYYY-MM-DD', review_date FROM bronze_reviews
    UNION ALL SELECT 'clients', 'last_modified_at', 'YYYY-MM-DD HH:MM:SS', last_modified_at FROM bronze_clients
    UNION ALL SELECT 'episodes', 'last_modified_at', 'YYYY-MM-DD HH:MM:SS', last_modified_at FROM bronze_episodes
    UNION ALL SELECT 'interventions', 'last_modified_at', 'YYYY-MM-DD HH:MM:SS', last_modified_at FROM bronze_interventions
    UNION ALL SELECT 'reviews', 'last_modified_at', 'YYYY-MM-DD HH:MM:SS', last_modified_at FROM bronze_reviews
),
labelled AS (
    SELECT table_name, column_name, expected,
           CASE
               WHEN value RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND try_to_timestamp(value, 'yyyy-MM-dd') IS NOT NULL THEN 'YYYY-MM-DD'
               WHEN value RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$'
                    AND try_to_timestamp(value, 'yyyy-MM-dd HH:mm:ss') IS NOT NULL THEN 'YYYY-MM-DD HH:MM:SS'
               WHEN value RLIKE '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' THEN 'DD/MM/YYYY'
               WHEN value RLIKE '^[0-9]{8}$' THEN 'YYYYMMDD'
               ELSE 'other'
           END AS format_found
    FROM date_values
    WHERE value IS NOT NULL
)
SELECT table_name, column_name, expected, format_found, count(*) AS row_count
FROM labelled
GROUP BY table_name, column_name, expected, format_found
ORDER BY table_name, column_name, format_found
""").show(100, truncate=False)

# CELL ********************

# 4. Codes not in the reference tables, as written. Values are shown in brackets so spaces are visible.
# valid_after_fix says whether trimming and upper-casing would turn the value into a listed code.
spark.sql("""
WITH reference_codes AS (
    SELECT list_name, code FROM bronze_code_lists
    UNION ALL SELECT 'service', service_code FROM bronze_services
),
code_values AS (
    SELECT 'clients' AS table_name, 'sex' AS column_name, 'sex' AS list_name, sex AS value FROM bronze_clients
    UNION ALL SELECT 'episodes', 'service_code', 'service', service_code FROM bronze_episodes
    UNION ALL SELECT 'episodes', 'referral_source', 'referral_source', referral_source FROM bronze_episodes
    UNION ALL SELECT 'episodes', 'primary_substance', 'substance', primary_substance FROM bronze_episodes
    UNION ALL SELECT 'episodes', 'discharge_reason', 'discharge_reason', discharge_reason FROM bronze_episodes
    UNION ALL SELECT 'interventions', 'intervention_type', 'intervention_type', intervention_type FROM bronze_interventions
    UNION ALL SELECT 'reviews', 'review_type', 'review_type', review_type FROM bronze_reviews
)
SELECT v.table_name, v.column_name, concat('[', v.value, ']') AS value_as_written,
       fixed.code IS NOT NULL AS valid_after_fix, count(*) AS row_count
FROM code_values v
LEFT JOIN reference_codes exact ON exact.list_name = v.list_name AND exact.code = v.value
LEFT JOIN reference_codes fixed ON fixed.list_name = v.list_name AND fixed.code = upper(trim(v.value))
WHERE v.value IS NOT NULL AND exact.code IS NULL
GROUP BY ALL
ORDER BY table_name, column_name, valid_after_fix, value_as_written
""").show(100, truncate=False)

# CELL ********************

# 5. Orphan foreign keys: a parent key that is not in the parent table of the same extract.
spark.sql("""
SELECT 'episodes.client_id to clients' AS foreign_key, count(*) AS orphan_rows, count(DISTINCT e.client_id) AS missing_parents
FROM bronze_episodes e LEFT ANTI JOIN bronze_clients c ON c.client_id = e.client_id
WHERE e.client_id IS NOT NULL
UNION ALL
SELECT 'episodes.service_code to services', count(*), count(DISTINCT e.service_code)
FROM bronze_episodes e LEFT ANTI JOIN bronze_services s ON s.service_code = e.service_code
WHERE e.service_code IS NOT NULL
UNION ALL
SELECT 'interventions.episode_id to episodes', count(*), count(DISTINCT i.episode_id)
FROM bronze_interventions i LEFT ANTI JOIN bronze_episodes e ON e.episode_id = i.episode_id
WHERE i.episode_id IS NOT NULL
UNION ALL
SELECT 'reviews.episode_id to episodes', count(*), count(DISTINCT r.episode_id)
FROM bronze_reviews r LEFT ANTI JOIN bronze_episodes e ON e.episode_id = r.episode_id
WHERE r.episode_id IS NOT NULL
""").show(truncate=False)
